from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..db import get_db
from ..services import ai_client, ai_report

router = APIRouter(prefix="/api/ai", tags=["ai"])


class ChatIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    history: list[dict] = Field(default_factory=list, max_length=12)


def _report_out(r: models.AIReport, include_body: bool = True) -> dict:
    return {
        "id": r.id,
        "created_at": r.created_at,
        "kind": r.kind,
        "model": r.model,
        "period_start": r.period_start,
        "period_end": r.period_end,
        "status": r.status,
        "error": r.error,
        **({"report_md": r.report_md} if include_body else {}),
    }


@router.get("/status")
def status():
    return {
        "configured": ai_client.is_configured(),
        "model": settings.ai_model if ai_client.is_configured() else None,
        "base_url": settings.ai_base_url,
    }


@router.post("/reports/generate")
def generate(days: int = Query(default=30, ge=7, le=90), db: Session = Depends(get_db)):
    if not ai_client.is_configured():
        raise HTTPException(400, "AI not configured - set AI_API_KEY in .env")
    row = ai_report.generate_report(db, kind="on_demand", days=days)
    if row.status == "error":
        raise HTTPException(502, row.error or "Generation failed")
    return _report_out(row)


@router.get("/reports")
def list_reports(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(models.AIReport).order_by(models.AIReport.id.desc()).limit(50)
    ).all()
    return [_report_out(r, include_body=False) for r in rows]


@router.get("/reports/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db)):
    row = db.get(models.AIReport, report_id)
    if not row:
        raise HTTPException(404, "Report not found")
    return _report_out(row)


@router.delete("/reports/{report_id}")
def delete_report(report_id: int, db: Session = Depends(get_db)):
    row = db.get(models.AIReport, report_id)
    if not row:
        raise HTTPException(404, "Report not found")
    db.delete(row)
    db.commit()
    return {"deleted": report_id}


@router.post("/chat")
def chat(body: ChatIn, db: Session = Depends(get_db)):
    if not ai_client.is_configured():
        raise HTTPException(400, "AI not configured - set AI_API_KEY in .env")
    try:
        answer = ai_report.answer_question(db, body.question, body.history)
    except ai_client.AInot_configured as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"AI request failed: {type(exc).__name__}: {exc}")
    return {"answer": answer}
