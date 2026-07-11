"""Food search against Open Food Facts + USDA FoodData Central, with a
read-through cache in the food_cache table."""

import json
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..timeutil import iso_now

logger = logging.getLogger(__name__)

OFF_SEARCH_URL = "https://search.openfoodfacts.org/search"
OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{code}"
USDA_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
HEADERS = {"User-Agent": "PersonalHealthApp/0.1 (self-hosted single user)"}


def _search_off(query: str, limit: int = 8) -> list[dict]:
    # Two-step: search-a-licious returns hits without nutriments, so fetch
    # each product's nutrition from the v2 product endpoint.
    with httpx.Client(headers=HEADERS, timeout=15) as client:
        resp = client.get(
            OFF_SEARCH_URL,
            params={"q": query, "page_size": limit, "fields": "code,product_name,brands"},
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", [])

        out = []
        for h in hits:
            code = h.get("code")
            if not code:
                continue
            try:
                p_resp = client.get(
                    OFF_PRODUCT_URL.format(code=code),
                    params={"fields": "code,product_name,brands,nutriments,serving_quantity"},
                )
                p_resp.raise_for_status()
            except httpx.HTTPError:
                continue
            p = p_resp.json().get("product", {})
            n = p.get("nutriments", {})
            kcal = n.get("energy-kcal_100g")
            name = p.get("product_name") or h.get("product_name")
            if not name or kcal is None:
                continue
            brands = p.get("brands") or h.get("brands")
            if isinstance(brands, list):
                brands = ", ".join(brands)
            out.append(
                {
                    "api_source": "off",
                    "external_id": str(code),
                    "name": name,
                    "brand": brands,
                    "kcal_per_100g": kcal,
                    "protein_g": n.get("proteins_100g"),
                    "carbs_g": n.get("carbohydrates_100g"),
                    "fat_g": n.get("fat_100g"),
                    "serving_size_g": _to_float(p.get("serving_quantity")),
                    "raw_json": json.dumps(p),
                }
            )
    return out


def _to_float(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


_USDA_NUTRIENTS = {"Energy": "kcal_per_100g", "Protein": "protein_g",
                   "Carbohydrate, by difference": "carbs_g",
                   "Total lipid (fat)": "fat_g"}


def _search_usda(query: str, limit: int = 10) -> list[dict]:
    if not settings.usda_api_key:
        return []
    resp = httpx.get(
        USDA_URL,
        params={
            "api_key": settings.usda_api_key,
            "query": query,
            "pageSize": limit,
            "dataType": "Foundation,SR Legacy,Branded",
        },
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    out = []
    for f in resp.json().get("foods", []):
        item = {
            "api_source": "usda",
            "external_id": str(f.get("fdcId")),
            "name": f.get("description", ""),
            "brand": f.get("brandName"),
            "kcal_per_100g": None,
            "protein_g": None,
            "carbs_g": None,
            "fat_g": None,
            "serving_size_g": _to_float(f.get("servingSize")),
            "raw_json": json.dumps(f),
        }
        for n in f.get("foodNutrients", []):
            key = _USDA_NUTRIENTS.get(n.get("nutrientName"))
            if key and n.get("unitName") in ("KCAL", "G"):
                item[key] = n.get("value")
        if item["name"] and item["kcal_per_100g"] is not None:
            out.append(item)
    return out


def search_and_cache(db: Session, query: str, source: str = "off") -> list[models.FoodCache]:
    """Search the external API, upsert hits into food_cache, return cache rows."""
    try:
        hits = _search_usda(query) if source == "usda" else _search_off(query)
    except httpx.HTTPError as exc:
        logger.warning("Food search failed (%s): %s", source, exc)
        hits = []

    rows: list[models.FoodCache] = []
    for h in hits:
        existing = db.scalar(
            select(models.FoodCache).where(
                models.FoodCache.api_source == h["api_source"],
                models.FoodCache.external_id == h["external_id"],
            )
        )
        if existing:
            for k, v in h.items():
                setattr(existing, k, v)
            existing.cached_at = iso_now()
            rows.append(existing)
        else:
            row = models.FoodCache(**h, cached_at=iso_now())
            db.add(row)
            rows.append(row)
    db.commit()
    return rows


def _off_product_to_item(p: dict) -> dict | None:
    n = p.get("nutriments", {})
    kcal = n.get("energy-kcal_100g")
    name = p.get("product_name")
    if not name or kcal is None:
        return None
    brands = p.get("brands")
    if isinstance(brands, list):
        brands = ", ".join(brands)
    return {
        "api_source": "off",
        "external_id": str(p.get("code")),
        "name": name,
        "brand": brands,
        "kcal_per_100g": kcal,
        "protein_g": n.get("proteins_100g"),
        "carbs_g": n.get("carbohydrates_100g"),
        "fat_g": n.get("fat_100g"),
        "serving_size_g": _to_float(p.get("serving_quantity")),
        "raw_json": json.dumps(p),
    }


def lookup_barcode(db: Session, code: str) -> models.FoodCache | None:
    """Direct product lookup by barcode via OFF v2, upserted into food_cache."""
    cached = db.scalar(
        select(models.FoodCache).where(
            models.FoodCache.api_source == "off",
            models.FoodCache.external_id == code,
        )
    )
    if cached:
        return cached
    try:
        resp = httpx.get(
            OFF_PRODUCT_URL.format(code=code),
            params={"fields": "code,product_name,brands,nutriments,serving_quantity"},
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Barcode lookup failed for %s: %s", code, exc)
        return None
    item = _off_product_to_item(resp.json().get("product", {}) or {})
    if not item:
        return None
    row = models.FoodCache(**item, cached_at=iso_now())
    db.add(row)
    db.commit()
    return row


def search_cache(db: Session, query: str, limit: int = 10) -> list[models.FoodCache]:
    return db.scalars(
        select(models.FoodCache)
        .where(models.FoodCache.name.ilike(f"%{query}%"))
        .limit(limit)
    ).all()
