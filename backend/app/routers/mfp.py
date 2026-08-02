from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..services.mfp_sync import check_cookie, sync_range
from ..timeutil import today_local

router = APIRouter(prefix="/api/mfp", tags=["mfp"])


def _get_setting(db: Session, key: str) -> str | None:
    row = db.get(models.UserSetting, key)
    return row.value if row else None


@router.get("/status", response_model=schemas.MfpStatusOut)
def mfp_status(db: Session = Depends(get_db)):
    cookie = _get_setting(db, "mfp_cookie")
    return schemas.MfpStatusOut(
        cookie_set=bool(cookie),
        last_sync_at=_get_setting(db, "mfp_last_sync_at"),
        last_sync_status=_get_setting(db, "mfp_last_sync_status"),
        last_sync_error=_get_setting(db, "mfp_last_sync_error"),
    )


@router.put("/cookie")
def set_cookie(body: schemas.MfpCookieIn, db: Session = Depends(get_db)):
    row = db.get(models.UserSetting, "mfp_cookie")
    if row:
        row.value = body.cookie
    else:
        db.add(models.UserSetting(key="mfp_cookie", value=body.cookie))
    db.commit()

    valid = check_cookie(db)
    return {"saved": True, "valid": valid}


@router.delete("/cookie")
def delete_cookie(db: Session = Depends(get_db)):
    for key in ("mfp_cookie", "mfp_last_sync_at", "mfp_last_sync_status", "mfp_last_sync_error"):
        row = db.get(models.UserSetting, key)
        if row:
            db.delete(row)
    db.commit()
    return {"deleted": True}


@router.post("/sync")
def trigger_sync(days: int = Query(default=3, ge=1, le=30), db: Session = Depends(get_db)):
    from datetime import timedelta

    end = today_local()
    start = end - timedelta(days=days - 1)
    result = sync_range(db, start, end)
    return result
