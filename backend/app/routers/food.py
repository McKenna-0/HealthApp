import base64
import json as _json
import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..db import get_db
from ..services import food, food_lookup
from ..services.food_lookup import _parse_serving_grams
from ..timeutil import iso_now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/food", tags=["food"])


@router.get("/search", response_model=list[schemas.FoodCacheOut])
def search(
    q: str = Query(min_length=2),
    source: str = Query(default="auto", pattern="^(auto|off|usda|cache)$"),
    db: Session = Depends(get_db),
):
    if source == "cache":
        return food_lookup.search_cache(db, q)
    if source == "auto":
        # OFF first (faster, better branded/packaged coverage), then USDA (generic/whole)
        off_rows = food_lookup.search_and_cache(db, q, "off")
        usda_rows = food_lookup.search_and_cache(db, q, "usda")
        # Merge: OFF first, then USDA items not already present
        seen_ids = {r.id for r in off_rows}
        rows = list(off_rows) + [r for r in usda_rows if r.id not in seen_ids]
        return rows or food_lookup.search_cache(db, q)
    rows = food_lookup.search_and_cache(db, q, source)
    return rows or food_lookup.search_cache(db, q)


@router.post("/log", response_model=schemas.FoodLogOut)
def add_log(body: schemas.FoodLogIn, db: Session = Depends(get_db)):
    try:
        return food.log_manual_entry(
            db,
            date=body.date,
            meal=body.meal,
            food_cache_id=body.food_cache_id,
            description=body.description,
            quantity_g=body.quantity_g,
            calories=body.calories,
            ts=body.ts,
        )
    except food.FoodNotFound as exc:
        raise HTTPException(404, str(exc))
    except food.FoodInvalid as exc:
        raise HTTPException(422, str(exc))


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


@router.get("/recent", response_model=list[schemas.RecentFoodOut])
def recent_foods(limit: int = Query(default=15, ge=1, le=50), db: Session = Depends(get_db)):
    """Most recently logged cached foods (distinct, newest first), with the
    last-used quantity and meal so the UI can offer one-tap re-logging."""
    rows = db.execute(
        select(models.FoodLog.food_cache_id, func.max(models.FoodLog.ts).label("last"))
        .where(models.FoodLog.food_cache_id.isnot(None))
        .group_by(models.FoodLog.food_cache_id)
        .order_by(func.max(models.FoodLog.ts).desc())
        .limit(limit)
    ).all()
    ids = [r[0] for r in rows]
    last_ts = {r[0]: r[1] for r in rows}
    items = {f.id: f for f in db.scalars(select(models.FoodCache).where(models.FoodCache.id.in_(ids)))}
    out = []
    for i in ids:
        if i not in items:
            continue
        last_log = db.scalar(
            select(models.FoodLog)
            .where(models.FoodLog.food_cache_id == i, models.FoodLog.ts == last_ts[i])
            .limit(1)
        )
        entry = schemas.RecentFoodOut.model_validate(items[i]).model_dump()
        entry["last_quantity_g"] = last_log.quantity_g if last_log else None
        entry["last_meal"] = last_log.meal if last_log else None
        out.append(entry)
    return out


@router.get("/favorites", response_model=list[schemas.FoodCacheOut])
def favorites(db: Session = Depends(get_db)):
    return db.scalars(
        select(models.FoodCache).where(models.FoodCache.is_favorite == 1).order_by(models.FoodCache.name)
    ).all()


@router.post("/favorite/{cache_id}", response_model=schemas.FoodCacheOut)
def toggle_favorite(cache_id: int, db: Session = Depends(get_db)):
    item = db.get(models.FoodCache, cache_id)
    if not item:
        raise HTTPException(404, "Not found")
    item.is_favorite = 0 if item.is_favorite else 1
    db.commit()
    return item


@router.get("/custom", response_model=list[schemas.FoodCacheOut])
def list_custom(db: Session = Depends(get_db)):
    return db.scalars(
        select(models.FoodCache).where(models.FoodCache.api_source == "custom").order_by(models.FoodCache.name)
    ).all()


@router.post("/custom", response_model=schemas.FoodCacheOut)
def add_custom(body: schemas.CustomFoodIn, db: Session = Depends(get_db)):
    factor = 1.0
    if body.per_serving:
        if not body.serving_size_g:
            raise HTTPException(422, "serving_size_g required when per_serving is true")
        factor = 100.0 / body.serving_size_g
    row = models.FoodCache(
        api_source="custom",
        external_id=str(uuid.uuid4()),
        name=body.name,
        brand=body.brand,
        kcal_per_100g=round(body.kcal * factor, 1),
        protein_g=round(body.protein_g * factor, 1) if body.protein_g is not None else None,
        carbs_g=round(body.carbs_g * factor, 1) if body.carbs_g is not None else None,
        fat_g=round(body.fat_g * factor, 1) if body.fat_g is not None else None,
        serving_size_g=body.serving_size_g,
        cached_at=iso_now(),
    )
    db.add(row)
    db.commit()
    return row


@router.delete("/custom/{cache_id}")
def delete_custom(cache_id: int, db: Session = Depends(get_db)):
    item = db.get(models.FoodCache, cache_id)
    if not item or item.api_source != "custom":
        raise HTTPException(404, "Custom food not found")
    db.delete(item)
    db.commit()
    return {"deleted": cache_id}


@router.post("/copy-day", response_model=list[schemas.FoodLogOut])
def copy_day(body: schemas.CopyDayIn, db: Session = Depends(get_db)):
    q = select(models.FoodLog).where(models.FoodLog.date == body.from_date)
    if body.meal:
        q = q.where(models.FoodLog.meal == body.meal)
    src_rows = db.scalars(q).all()
    if not src_rows:
        raise HTTPException(404, f"Nothing logged on {body.from_date}")
    new_rows = []
    for r in src_rows:
        row = models.FoodLog(
            date=body.to_date,
            ts=iso_now(),
            meal=r.meal,
            food_cache_id=r.food_cache_id,
            description=r.description,
            quantity_g=r.quantity_g,
            calories=r.calories,
            protein_g=r.protein_g,
            carbs_g=r.carbs_g,
            fat_g=r.fat_g,
        )
        db.add(row)
        new_rows.append(row)
    db.commit()
    return new_rows


@router.get("/barcode/{code}")
def barcode(code: str, db: Session = Depends(get_db)):
    if not code.isdigit() or not 6 <= len(code) <= 14:
        raise HTTPException(422, "Invalid barcode")
    item = food_lookup.lookup_barcode(db, code)
    if not item:
        return {"found": False, "code": code}
    return {"found": True, "item": schemas.FoodCacheOut.model_validate(item).model_dump()}


@router.get("/cache/{cache_id}", response_model=schemas.FoodCacheOut)
def get_cache_item(cache_id: int, db: Session = Depends(get_db)):
    item = db.get(models.FoodCache, cache_id)
    if not item:
        raise HTTPException(404, "Not found")
    return item


@router.get("/cache/{cache_id}/servings", response_model=list[schemas.ServingOption])
def get_servings(cache_id: int, db: Session = Depends(get_db)):
    item = db.get(models.FoodCache, cache_id)
    if not item:
        raise HTTPException(404, "Not found")
    options: list[dict] = []
    # Default serving from the item — show as first option when available
    if item.serving_size_g and item.serving_size_g > 0:
        label = item.serving_size_text or f"{item.serving_size_g:g}g (1 serving)"
        options.append({"label": label, "grams": item.serving_size_g})
    # Parse additional portions from raw_json
    if item.raw_json:
        try:
            p = _json.loads(item.raw_json)
            # USDA foodPortions (e.g. "1 large", "1 medium", "1 cup")
            for portion in p.get("foodPortions", []):
                gw = portion.get("gramWeight")
                if not gw:
                    continue
                gw = float(gw)
                desc = portion.get("portionDescription") or portion.get("modifier") or ""
                amt = portion.get("amount")
                if amt and desc:
                    lbl = f"{amt} {desc}" if amt != 1 else desc
                elif desc:
                    lbl = desc
                else:
                    lbl = f"{gw:g}g"
                lbl = f"{lbl} ({gw:g}g)"
                options.append({"label": lbl, "grams": gw})
            # OFF serving_size / serving_quantity
            ss = p.get("serving_size") or ""
            sq = p.get("serving_quantity")
            if ss and sq:
                options.append({"label": ss, "grams": float(sq)})
            elif ss and not sq:
                # Parse grams from serving_size text as fallback
                parsed_g = _parse_serving_grams(ss)
                if parsed_g and parsed_g > 0:
                    lbl = ss if not ss.replace(".", "").replace(" ", "").isdigit() else f"{ss} (1 serving)"
                    if not options:
                        # No serving option yet — make this the first/default
                        options.insert(0, {"label": lbl, "grams": parsed_g})
                    else:
                        options.append({"label": lbl, "grams": parsed_g})
        except (ValueError, TypeError, KeyError):
            pass
    # Always include 100g and 1g
    options.append({"label": "100g", "grams": 100})
    options.append({"label": "1g", "grams": 1})
    # De-duplicate by grams
    seen: set[float] = set()
    deduped = []
    for o in options:
        if o["grams"] not in seen:
            seen.add(o["grams"])
            deduped.append(o)
    return deduped


_NOVA_LABELS = {
    1: "Unprocessed or minimally processed",
    2: "Processed culinary ingredients",
    3: "Processed foods",
    4: "Ultra-processed foods",
}


@router.get("/cache/{cache_id}/nutrients")
def get_nutrients(cache_id: int, db: Session = Depends(get_db)):
    item = db.get(models.FoodCache, cache_id)
    if not item:
        raise HTTPException(404, "Not found")
    micros = _json.loads(item.micronutrients_json) if item.micronutrients_json else {}
    # Extract food quality scores from raw_json (OFF products)
    scores: dict = {}
    if item.raw_json:
        try:
            p = _json.loads(item.raw_json)
            ns = p.get("nutriscore_grade")
            if ns:
                scores["nutriscore_grade"] = ns.lower()
            nova = p.get("nova_group")
            if nova is not None:
                nova = int(nova)
                scores["nova_group"] = nova
                scores["nova_group_label"] = _NOVA_LABELS.get(nova, "")
            eco = p.get("ecoscore_grade")
            if eco and eco != "not-applicable":
                scores["ecoscore_grade"] = eco.lower()
            ingredients = p.get("ingredients_text")
            if ingredients:
                scores["ingredients_text"] = ingredients
        except (ValueError, TypeError, KeyError):
            pass
    return {
        "kcal_per_100g": item.kcal_per_100g,
        "protein_g": item.protein_g,
        "carbs_g": item.carbs_g,
        "fat_g": item.fat_g,
        "micronutrients": micros,
        "scores": scores,
    }


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


_OCR_PROMPT = """Extract the nutrition facts from this food label image.
Return ONLY valid JSON with these fields (use null if not visible):
{
  "name": "product name if visible",
  "serving_size_g": number or null,
  "serving_size_text": "e.g. 1 cup (240ml)",
  "calories": number,
  "protein_g": number,
  "carbs_g": number,
  "fat_g": number,
  "fiber_g": number or null,
  "sugar_g": number or null,
  "sodium_mg": number or null,
  "saturated_fat_g": number or null,
  "per_serving": true
}
All values should be PER SERVING as shown on the label.
Return ONLY the JSON object, no markdown or explanation."""


@router.post("/ocr-label")
async def ocr_label(image: UploadFile = File(...)):
    """Parse a nutrition label photo using a vision model."""
    if not settings.ai_api_key:
        raise HTTPException(503, "AI API key not configured")

    content = await image.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "Image too large (max 10MB)")

    media_type = image.content_type or "image/jpeg"
    b64 = base64.b64encode(content).decode()

    import httpx
    try:
        resp = httpx.post(
            f"{settings.ai_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.ai_api_key}"},
            json={
                "model": settings.ai_vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": _OCR_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{b64}",
                                },
                            },
                        ],
                    }
                ],
                "max_tokens": 500,
            },
            timeout=30,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("OCR vision API error: %s", exc)
        raise HTTPException(502, "Vision API request failed")

    raw_text = resp.json()["choices"][0]["message"]["content"]
    # Strip markdown fences if present
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        parsed = _json.loads(text)
    except _json.JSONDecodeError:
        logger.warning("OCR response not valid JSON: %s", raw_text[:200])
        raise HTTPException(422, "Could not parse nutrition data from image")

    return {"ocr": parsed}
