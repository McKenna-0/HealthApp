from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..services import food_lookup
from ..timeutil import iso_now

router = APIRouter(prefix="/api/food", tags=["food"])


@router.get("/search", response_model=list[schemas.FoodCacheOut])
def search(
    q: str = Query(min_length=2),
    source: str = Query(default="off", pattern="^(off|usda|cache)$"),
    db: Session = Depends(get_db),
):
    if source == "cache":
        return food_lookup.search_cache(db, q)
    rows = food_lookup.search_and_cache(db, q, source)
    return rows or food_lookup.search_cache(db, q)


def _compute_entry(body: schemas.FoodLogIn, db: Session) -> dict:
    """Resolve calories/macros either from a cache item + grams or free-text kcal."""
    if body.food_cache_id is not None:
        item = db.get(models.FoodCache, body.food_cache_id)
        if not item:
            raise HTTPException(404, "food_cache_id not found")
        if body.quantity_g is None:
            raise HTTPException(422, "quantity_g required when using a food item")
        factor = body.quantity_g / 100.0
        return {
            "description": body.description or item.name,
            "quantity_g": body.quantity_g,
            "calories": round((item.kcal_per_100g or 0) * factor, 1),
            "protein_g": round(item.protein_g * factor, 1) if item.protein_g is not None else None,
            "carbs_g": round(item.carbs_g * factor, 1) if item.carbs_g is not None else None,
            "fat_g": round(item.fat_g * factor, 1) if item.fat_g is not None else None,
        }
    if body.calories is None:
        raise HTTPException(422, "calories required for free-text entries")
    return {
        "description": body.description,
        "quantity_g": body.quantity_g,
        "calories": body.calories,
        "protein_g": None,
        "carbs_g": None,
        "fat_g": None,
    }


@router.post("/log", response_model=schemas.FoodLogOut)
def add_log(body: schemas.FoodLogIn, db: Session = Depends(get_db)):
    computed = _compute_entry(body, db)
    row = models.FoodLog(
        date=body.date,
        ts=iso_now(),
        meal=body.meal,
        food_cache_id=body.food_cache_id,
        **computed,
    )
    db.add(row)
    db.commit()
    return row


@router.get("/log", response_model=list[schemas.FoodLogOut])
def list_log(
    date: str | None = None,
    start: str | None = None,
    end: str | None = None,
    db: Session = Depends(get_db),
):
    q = select(models.FoodLog)
    if date:
        q = q.where(models.FoodLog.date == date)
    if start:
        q = q.where(models.FoodLog.date >= start)
    if end:
        q = q.where(models.FoodLog.date <= end)
    return db.scalars(q.order_by(models.FoodLog.date, models.FoodLog.ts)).all()


@router.put("/log/{log_id}", response_model=schemas.FoodLogOut)
def update_log(log_id: int, body: schemas.FoodLogUpdate, db: Session = Depends(get_db)):
    row = db.get(models.FoodLog, log_id)
    if not row:
        raise HTTPException(404, "Not found")
    updates = body.model_dump(exclude_unset=True)
    complete = updates.pop("logging_complete_day", None)
    quantity = updates.pop("quantity_g", None)
    for k, v in updates.items():
        setattr(row, k, v)
    if quantity is not None:
        row.quantity_g = quantity
        if row.food_cache_id and (item := db.get(models.FoodCache, row.food_cache_id)):
            factor = quantity / 100.0
            row.calories = round((item.kcal_per_100g or 0) * factor, 1)
            row.protein_g = round(item.protein_g * factor, 1) if item.protein_g is not None else None
            row.carbs_g = round(item.carbs_g * factor, 1) if item.carbs_g is not None else None
            row.fat_g = round(item.fat_g * factor, 1) if item.fat_g is not None else None
    if complete is not None:
        # day-complete flag applies to every entry on that date
        db.query(models.FoodLog).filter(models.FoodLog.date == row.date).update(
            {"logging_complete_day": complete}
        )
    db.commit()
    return row


@router.delete("/log/{log_id}")
def delete_log(log_id: int, db: Session = Depends(get_db)):
    row = db.get(models.FoodLog, log_id)
    if not row:
        raise HTTPException(404, "Not found")
    db.delete(row)
    db.commit()
    return {"deleted": log_id}


@router.get("/summary")
def summary(start: str, end: str, db: Session = Depends(get_db)):
    rows = db.execute(
        select(
            models.FoodLog.date,
            func.sum(models.FoodLog.calories),
            func.sum(models.FoodLog.protein_g),
            func.sum(models.FoodLog.carbs_g),
            func.sum(models.FoodLog.fat_g),
            func.min(models.FoodLog.logging_complete_day),
        )
        .where(models.FoodLog.date >= start, models.FoodLog.date <= end)
        .group_by(models.FoodLog.date)
        .order_by(models.FoodLog.date)
    ).all()
    return [
        {
            "date": r[0],
            "calories": round(r[1] or 0, 1),
            "protein_g": round(r[2], 1) if r[2] is not None else None,
            "carbs_g": round(r[3], 1) if r[3] is not None else None,
            "fat_g": round(r[4], 1) if r[4] is not None else None,
            "complete": bool(r[5]),
        }
        for r in rows
    ]
