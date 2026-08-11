"""Food log writes.

Extracted from the food router so a confirmed AI write-proposal creates exactly
the row the UI would have created - same macro derivation, same defaults. The
router keeps its HTTP status codes by mapping the two exceptions below."""

from sqlalchemy.orm import Session

from .. import models
from ..timeutil import iso_now


class FoodError(Exception):
    """Base for problems with a food entry the caller can fix."""


class FoodNotFound(FoodError):
    """A referenced cache item doesn't exist."""


class FoodInvalid(FoodError):
    """The entry is internally inconsistent, e.g. no calories and no item."""


def compute_entry(
    db: Session,
    food_cache_id: int | None = None,
    description: str | None = None,
    quantity_g: float | None = None,
    calories: float | None = None,
) -> dict:
    """Resolve calories/macros either from a cache item + grams, or from
    free-text kcal. Macros are only known in the first case."""
    if food_cache_id is not None:
        item = db.get(models.FoodCache, food_cache_id)
        if not item:
            raise FoodNotFound("food_cache_id not found")
        if quantity_g is None:
            raise FoodInvalid("quantity_g required when using a food item")
        factor = quantity_g / 100.0
        return {
            "description": description or item.name,
            "quantity_g": quantity_g,
            "calories": round((item.kcal_per_100g or 0) * factor, 1),
            "protein_g": round(item.protein_g * factor, 1) if item.protein_g is not None else None,
            "carbs_g": round(item.carbs_g * factor, 1) if item.carbs_g is not None else None,
            "fat_g": round(item.fat_g * factor, 1) if item.fat_g is not None else None,
        }

    if calories is None:
        raise FoodInvalid("calories required for free-text entries")
    return {
        "description": description,
        "quantity_g": quantity_g,
        "calories": calories,
        "protein_g": None,
        "carbs_g": None,
        "fat_g": None,
    }


def log_manual_entry(
    db: Session,
    date: str,
    meal: str,
    food_cache_id: int | None = None,
    description: str | None = None,
    quantity_g: float | None = None,
    calories: float | None = None,
    ts: str | None = None,
) -> models.FoodLog:
    computed = compute_entry(
        db,
        food_cache_id=food_cache_id,
        description=description,
        quantity_g=quantity_g,
        calories=calories,
    )
    row = models.FoodLog(
        date=date,
        ts=ts or iso_now(),
        meal=meal,
        food_cache_id=food_cache_id,
        **computed,
    )
    db.add(row)
    db.commit()
    return row
