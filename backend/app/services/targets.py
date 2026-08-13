"""Resolve the effective nutrition targets for a single day.

Active calories burned on a day are added on top of the configured calorie
allowance (the MyFitnessPal model): eat 2200 + whatever you moved for. When
macros are configured as a percentage of calories, the gram targets are
derived from that combined total, so they grow with activity too.

Every target is split into ``base`` (from the configured allowance) and
``bonus`` (earned from active calories) so the UI can draw them as separate
segments.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models

# kcal per gram, used to turn a % of calories into a gram target
KCAL_PER_G = {"protein": 4.0, "carbs": 4.0, "fat": 9.0}

_NUMERIC_KEYS = {
    "calorie_target",
    "protein_target_g",
    "carbs_target_g",
    "fat_target_g",
    "protein_target_pct",
    "carbs_target_pct",
    "fat_target_pct",
}


def _settings(db: Session) -> dict[str, float | str | None]:
    out: dict[str, float | str | None] = {"macro_mode": "grams"}
    for row in db.scalars(select(models.UserSetting)):
        if row.key in _NUMERIC_KEYS:
            out[row.key] = float(row.value) if row.value else None
        elif row.key == "macro_mode":
            out[row.key] = row.value or "grams"
    return out


def active_calories(db: Session, date: str) -> float:
    """Active (non-BMR) calories burned on ``date``; 0 when not yet synced."""
    row = db.get(models.DailyMetrics, date)
    return float(row.calories_active or 0) if row is not None else 0.0


def _component(base: float | None, bonus: float, digits: int = 0) -> dict:
    """A target split into its configured base and its activity-earned bonus."""
    if base is None:
        return {"base": None, "bonus": 0.0, "target": None}
    base_r = round(base, digits)
    bonus_r = round(bonus, digits)
    return {"base": base_r, "bonus": bonus_r, "target": round(base_r + bonus_r, digits)}


def resolve(db: Session, date: str) -> dict:
    s = _settings(db)
    cal_base = s.get("calorie_target")
    active = active_calories(db, date)
    # No calorie goal means nothing to add the bonus to.
    cal_bonus = active if cal_base else 0.0

    macros: dict[str, dict] = {}
    percent_mode = s.get("macro_mode") == "percent"
    for macro, kcal_per_g in KCAL_PER_G.items():
        pct = s.get(f"{macro}_target_pct")
        if percent_mode and cal_base and pct:
            macros[macro] = _component(
                cal_base * pct / 100 / kcal_per_g,
                cal_bonus * pct / 100 / kcal_per_g,
            )
        else:
            # Gram targets are absolute — activity does not move them.
            macros[macro] = _component(s.get(f"{macro}_target_g"), 0.0)

    return {
        "date": date,
        "macro_mode": "percent" if percent_mode else "grams",
        "active_calories": round(active),
        "calories": _component(cal_base, cal_bonus),
        **macros,
    }
