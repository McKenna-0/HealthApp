"""Food search against Open Food Facts + USDA FoodData Central, with a
read-through cache in the food_cache table."""

import json
import logging
import re

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..timeutil import iso_now

logger = logging.getLogger(__name__)

# Fields to request from OFF product endpoint
_OFF_PRODUCT_FIELDS = (
    "code,product_name,product_name_en,generic_name,brands,"
    "nutriments,serving_quantity,serving_size,"
    "nutriscore_grade,nova_group,ecoscore_grade,nova_groups_tags,ingredients_text"
)


def _extract_off_kcal(n: dict) -> float | None:
    """Extract kcal/100g from OFF nutriments, trying multiple keys."""
    kcal = n.get("energy-kcal_100g")
    if kcal is not None:
        return float(kcal)
    kj = n.get("energy-kj_100g")
    if kj is not None:
        return round(float(kj) / 4.184, 1)
    energy = n.get("energy_100g")
    if energy is not None:
        return float(energy)
    return None


def _extract_off_name(p: dict, fallback: str | None = None) -> str | None:
    """Get the best product name from OFF product data."""
    return p.get("product_name") or p.get("product_name_en") or p.get("generic_name") or fallback


def _parse_serving_grams(serving_size: str | None) -> float | None:
    """Parse grams from OFF serving_size text like '58g', '1 egg (58g)', '125 ml'."""
    if not serving_size:
        return None
    # Try to find grams pattern
    m = re.search(r'(\d+\.?\d*)\s*g(?:rams?)?(?:\b|$)', serving_size, re.IGNORECASE)
    if m:
        return float(m.group(1))
    # Try ml (approximate 1ml = 1g for liquids)
    m = re.search(r'(\d+\.?\d*)\s*ml\b', serving_size, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None

OFF_SEARCH_URL = "https://search.openfoodfacts.org/search"
OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{code}"
USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
USDA_FOOD_URL = "https://api.nal.usda.gov/fdc/v1/food/{fdc_id}"
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
                    params={"fields": _OFF_PRODUCT_FIELDS},
                )
                p_resp.raise_for_status()
            except httpx.HTTPError:
                continue
            p = p_resp.json().get("product", {})
            item = _off_product_to_item(p, fallback_name=h.get("product_name"),
                                        fallback_brands=h.get("brands"))
            if item:
                out.append(item)
    return out


def _to_float(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


_USDA_MACROS = {"Energy": "kcal_per_100g", "Protein": "protein_g",
                "Carbohydrate, by difference": "carbs_g",
                "Total lipid (fat)": "fat_g"}

_USDA_MICROS = {
    "Calcium, Ca": "calcium_mg",
    "Iron, Fe": "iron_mg",
    "Potassium, K": "potassium_mg",
    "Sodium, Na": "sodium_mg",
    "Vitamin A, RAE": "vitamin_a_mcg",
    "Vitamin C, total ascorbic acid": "vitamin_c_mg",
    "Vitamin D (D2 + D3)": "vitamin_d_mcg",
    "Vitamin B-6": "vitamin_b6_mg",
    "Vitamin B-12": "vitamin_b12_mcg",
    "Magnesium, Mg": "magnesium_mg",
    "Zinc, Zn": "zinc_mg",
    "Phosphorus, P": "phosphorus_mg",
    "Folate, total": "folate_mcg",
    "Fiber, total dietary": "fiber_g",
    "Sugars, total including NLEA": "sugar_g",
    "Cholesterol": "cholesterol_mg",
    "Fatty acids, total saturated": "saturated_fat_g",
    "Fatty acids, total trans": "trans_fat_g",
}


def _extract_usda_nutrients(nutrients: list[dict]) -> tuple[dict, dict]:
    """Extract macros and micronutrients from USDA foodNutrients array."""
    macros: dict = {"kcal_per_100g": None, "protein_g": None, "carbs_g": None, "fat_g": None}
    micros: dict = {}
    for n in nutrients:
        name = n.get("nutrient", n).get("name", n.get("nutrientName", ""))
        value = n.get("amount", n.get("value"))
        if value is None:
            continue
        macro_key = _USDA_MACROS.get(name)
        if macro_key:
            macros[macro_key] = value
        micro_key = _USDA_MICROS.get(name)
        if micro_key:
            micros[micro_key] = round(value, 2)
    return macros, micros


def _extract_usda_portions(food_data: dict) -> tuple[float | None, str | None]:
    """Extract the best default serving from foodPortions."""
    portions = food_data.get("foodPortions", [])
    if not portions:
        ss = _to_float(food_data.get("servingSize"))
        return ss, food_data.get("servingSizeUnit")
    best = portions[0]
    g = _to_float(best.get("gramWeight"))
    desc = best.get("portionDescription") or best.get("modifier") or ""
    amount = best.get("amount")
    if amount and desc:
        label = f"{amount} {desc}" if amount != 1 else desc
    elif desc:
        label = desc
    else:
        label = f"{g}g" if g else None
    return g, label


def _search_usda(query: str, limit: int = 8) -> list[dict]:
    if not settings.usda_api_key:
        return []
    # Step 1: search
    resp = httpx.get(
        USDA_SEARCH_URL,
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
    foods = resp.json().get("foods", [])

    # Step 2: fetch full details for top hits (portions + full nutrients)
    # Only fetch detail for the top 3 to keep latency low; rest use search data
    out = []
    with httpx.Client(headers=HEADERS, timeout=10) as client:
        for idx, f in enumerate(foods):
            fdc_id = f.get("fdcId")
            if not fdc_id:
                continue
            detail = f
            if idx < 3:
                try:
                    detail_resp = client.get(
                        USDA_FOOD_URL.format(fdc_id=fdc_id),
                        params={"api_key": settings.usda_api_key},
                    )
                    detail_resp.raise_for_status()
                    detail = detail_resp.json()
                except httpx.HTTPError:
                    pass

            nutrients = detail.get("foodNutrients", f.get("foodNutrients", []))
            macros, micros = _extract_usda_nutrients(nutrients)
            serving_g, serving_text = _extract_usda_portions(detail)

            name = detail.get("description") or f.get("description", "")
            if not name or macros["kcal_per_100g"] is None:
                continue

            out.append({
                "api_source": "usda",
                "external_id": str(fdc_id),
                "name": name,
                "brand": f.get("brandName"),
                "kcal_per_100g": macros["kcal_per_100g"],
                "protein_g": macros["protein_g"],
                "carbs_g": macros["carbs_g"],
                "fat_g": macros["fat_g"],
                "serving_size_g": serving_g,
                "serving_size_text": serving_text,
                "micronutrients_json": json.dumps(micros) if micros else None,
                "raw_json": json.dumps(detail),
            })
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


def _off_product_to_item(p: dict, fallback_name: str | None = None,
                          fallback_brands: str | None = None) -> dict | None:
    n = p.get("nutriments", {})
    kcal = _extract_off_kcal(n)
    name = _extract_off_name(p, fallback=fallback_name)
    if not name or kcal is None:
        return None
    brands = p.get("brands") or fallback_brands
    if isinstance(brands, list):
        brands = ", ".join(brands)
    # Serving size: try serving_quantity first, then parse from serving_size text
    serving_g = _to_float(p.get("serving_quantity"))
    if serving_g is None:
        serving_g = _parse_serving_grams(p.get("serving_size"))
    return {
        "api_source": "off",
        "external_id": str(p.get("code")),
        "name": name,
        "brand": brands,
        "kcal_per_100g": kcal,
        "protein_g": n.get("proteins_100g"),
        "carbs_g": n.get("carbohydrates_100g"),
        "fat_g": n.get("fat_100g"),
        "serving_size_g": serving_g,
        "serving_size_text": p.get("serving_size"),
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
            params={"fields": _OFF_PRODUCT_FIELDS},
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
