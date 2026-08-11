"""AI report generation and Q&A over the composed data summary."""

import json
import logging

from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..timeutil import iso_now
from . import ai_client
from .ai_summary import compose_summary

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an evidence-based health and fitness analyst reviewing one person's \
self-tracked data: a Garmin wearable (sleep, HRV, resting heart rate, steps, stress, workouts), \
a food log, manually logged bloodwork, and subjective context logs (alcohol, caffeine, mood, illness).

Ground every observation in the specific numbers provided in the data summary and show your reasoning. \
Structure your report with these sections:

1. **Headline** — 2-3 sentence overall picture.
2. **What's going well** — specific positives with numbers.
3. **Notable or concerning patterns** — flag explicitly, state severity and your confidence.
4. **Recommendations** — concrete, actionable, prioritized (max 5).
5. **Data quality notes** — gaps, incomplete logging days, small sample caveats.

Rules:
- Be honest about uncertainty: correlations in 7-30 days of single-person data are weak evidence; say so.
- Do not cite specific studies, journals, or statistics you cannot verify. Speak from well-established \
general principles (e.g. protein intake for muscle retention, sleep's effect on recovery, alcohol's \
effect on HRV) only.
- Wearable calorie, HRV and sleep-stage values are estimates; treat them as directional.
- Never invent data that is not in the summary. If something is missing, note it rather than guessing.
- For blood markers outside their reference range, recommend discussing with a doctor rather than \
self-treating. You are not a physician.
- End with one line: "*This is automated analysis of self-tracked data, not medical advice.*"
"""

def generate_report(db: Session, kind: str = "on_demand", days: int = 30) -> models.AIReport:
    summary = compose_summary(db, days)
    row = models.AIReport(
        created_at=iso_now(),
        kind=kind,
        model=settings.ai_model,
        period_start=summary["period"]["start"],
        period_end=summary["period"]["end"],
        report_md="",
        summary_json=json.dumps(summary),
        status="ok",
    )
    try:
        report = ai_client.chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": "Here is my health data summary for the period "
                    f"{summary['period']['start']} to {summary['period']['end']} (JSON):\n\n"
                    + json.dumps(summary, indent=1)
                    + "\n\nPlease write my health report.",
                },
            ]
        )
        row.report_md = report
    except Exception as exc:  # noqa: BLE001 - stored, never raised to scheduler
        logger.exception("AI report generation failed")
        row.status = "error"
        row.error = f"{type(exc).__name__}: {exc}"
    db.add(row)
    db.commit()
    return row
