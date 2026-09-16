"""MyFitnessPal food diary sync via direct HTTP scraping.

The python-myfitnesspal library uses cloudscraper which gets blocked by
Cloudflare.  Plain httpx with the user's cookie header works reliably.
"""

import html
import logging
import re
from datetime import date, timedelta

import httpx
from sqlalchemy import delete
from sqlalchemy.orm import Session

from .. import models
from ..timeutil import iso_now

logger = logging.getLogger(__name__)

MFP_DIARY_URL = "https://www.myfitnesspal.com/food/diary"
MFP_MEALS = ["Breakfast", "Lunch", "Dinner", "Snacks"]
MFP_MEAL_MAP = {
    "Breakfast": "breakfast",
    "Lunch": "lunch",
    "Dinner": "dinner",
    "Snacks": "snack",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _cookie_dict(raw: str) -> dict[str, str]:
    """Parse a cookie header string into a dict for httpx."""
    cleaned = raw.strip().strip("'\"")
    if cleaned.lower().startswith("cookie:"):
        cleaned = cleaned[7:].strip()

    cookies: dict[str, str] = {}
    for pair in cleaned.split(";"):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        name, value = pair.split("=", 1)
        cookies[name.strip()] = value.strip()
    return cookies


def _fetch_diary(cookies: dict[str, str], day: date) -> str:
    """Fetch the MFP diary HTML for a single date."""
    r = httpx.get(
        MFP_DIARY_URL,
        params={"date": day.isoformat()},
        cookies=cookies,
        headers=_HEADERS,
        follow_redirects=True,
        timeout=30,
    )
    if r.status_code == 403:
        raise PermissionError("MFP returned 403 — cookie may be expired")
    if "login" in str(r.url):
        raise PermissionError("MFP redirected to login — cookie expired")
    r.raise_for_status()
    return r.text


def _parse_diary(page_html: str) -> dict[str, list[dict]]:
    """Parse food entries from MFP diary HTML.

    Returns ``{meal_key: [{name, calories, protein_g, carbs_g, fat_g}, ...]}``.
    """
    result: dict[str, list[dict]] = {}

    for meal_name in MFP_MEALS:
        meal_key = MFP_MEAL_MAP[meal_name]
        # Find the meal header row
        header_pat = rf'<td[^>]*class="first alt"[^>]*>\s*{meal_name}\s*</td>'
        header_match = re.search(header_pat, page_html)
        if not header_match:
            continue

        start = header_match.end()
        # Section ends at the total row (class="bottom" or "total")
        total_match = re.search(r'<tr[^>]*class="(?:bottom|total)"', page_html[start:])
        end = start + total_match.start() if total_match else start + 10000
        section = page_html[start:end]

        entries = re.findall(
            r'<a[^>]*class="js-show-edit-food"[^>]*>([^<]+)</a>.*?'  # name
            r'<td>(\d+)</td>.*?'  # calories
            r'<span class="macro-value">(\d+)</span>.*?'  # carbs
            r'<span class="macro-value">(\d+)</span>.*?'  # fat
            r'<span class="macro-value">(\d+)</span>',  # protein
            section,
            re.DOTALL,
        )

        items = []
        for name, cals, carbs, fat, protein in entries:
            items.append({
                "name": html.unescape(name.strip()),
                "calories": float(cals),
                "protein_g": float(protein),
                "carbs_g": float(carbs),
                "fat_g": float(fat),
            })
        result[meal_key] = items

    return result


# ── Public API ──────────────────────────────────────────────────────


def sync_date(db: Session, cookies: dict[str, str], day: date) -> int:
    """Sync MFP diary for a single date. Returns count of inserted entries."""
    page = _fetch_diary(cookies, day)
    parsed = _parse_diary(page)

    # Delete existing MFP entries for this date, then insert fresh
    db.execute(
        delete(models.FoodLog).where(
            models.FoodLog.date == day.isoformat(),
            models.FoodLog.source == "myfitnesspal",
        )
    )

    count = 0
    for meal_key, items in parsed.items():
        for item in items:
            db.add(models.FoodLog(
                date=day.isoformat(),
                ts=iso_now(),
                meal=meal_key,
                description=item["name"],
                food_cache_id=None,
                quantity_g=None,
                calories=item["calories"],
                protein_g=item["protein_g"],
                carbs_g=item["carbs_g"],
                fat_g=item["fat_g"],
                logging_complete_day=0,
                source="myfitnesspal",
            ))
            count += 1

    db.commit()
    return count


def sync_range(db: Session, start: date, end: date) -> dict:
    """Sync MFP diary for a date range. Returns summary."""
    row = db.get(models.UserSetting, "mfp_cookie")
    if not row or not row.value:
        raise ValueError("MFP cookie not configured")

    cookies = _cookie_dict(row.value)
    total = 0
    errors: list[str] = []
    day = start
    while day <= end:
        try:
            n = sync_date(db, cookies, day)
            total += n
        except Exception as exc:
            db.rollback()
            errors.append(f"{day}: {exc}")
            logger.warning("MFP sync failed for %s: %s", day, exc)
        day += timedelta(days=1)

    # Detect cookie expiry from auth-related errors
    status = "ok"
    if errors:
        err_text = "; ".join(errors[:3])
        if any(kw in err_text.lower() for kw in ("login", "auth", "403", "expired", "permission")):
            status = "cookie_expired"
        else:
            status = "error"

    _set_setting(db, "mfp_last_sync_at", iso_now())
    _set_setting(db, "mfp_last_sync_status", status)
    _set_setting(db, "mfp_last_sync_error", "; ".join(errors[:3]) if errors else "")
    db.commit()

    return {"entries_synced": total, "errors": errors}


def check_cookie(db: Session) -> bool:
    """Test whether the stored cookie is still valid."""
    try:
        row = db.get(models.UserSetting, "mfp_cookie")
        if not row or not row.value:
            return False
        cookies = _cookie_dict(row.value)
        _fetch_diary(cookies, date.today())
        return True
    except Exception:
        return False


def _set_setting(db: Session, key: str, value: str):
    row = db.get(models.UserSetting, key)
    if row:
        row.value = value
    else:
        db.add(models.UserSetting(key=key, value=value))
