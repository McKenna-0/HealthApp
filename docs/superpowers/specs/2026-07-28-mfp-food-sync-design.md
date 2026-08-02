# MyFitnessPal Food Diary Sync

## Context

Food logging in the health app has too much friction compared to MyFitnessPal (MFP). The user already logs food daily in MFP and wants to keep doing so. Rather than competing with MFP's mature food database and UX, we sync MFP diary entries into the health app so they appear in the dashboard, analytics, and calorie tracking.

**Problem:** The app's food search (OFF + USDA) has spotty coverage for branded items, barcode lookups often miss, and serving sizes default to 100g. MFP handles all of this well.

**Solution:** Add a one-way sync from MFP into the health app's `FoodLog` table, running on a daily schedule. The user pastes their MFP browser cookies into a settings page; the backend uses the `python-myfitnesspal` library to scrape diary data.

## Design

### Authentication Flow

MFP has no public API. The `python-myfitnesspal` library scrapes the MFP website using browser cookies. Since the app runs on a Pi (not the user's browser machine), automatic cookie extraction won't work. Instead:

1. User logs into `myfitnesspal.com` in any browser
2. Opens DevTools > Console, runs `document.cookie`, copies the result
3. Pastes the full cookie string into the health app's Settings > MFP section
4. Backend parses the cookie string into an `http.cookiejar.CookieJar` and passes it to `myfitnesspal.Client(cookiejar=...)`
5. When cookies expire (typically weeks later), the sync fails gracefully and the UI shows a "cookie expired" warning

### Data Flow

```
MFP website
  -> python-myfitnesspal Client.get_date()
  -> Day.meals[].entries[] (name, calories, protein, carbs, fat)
  -> upsert into FoodLog with source="myfitnesspal"
```

MFP entries are stored as free-text food log entries (no `food_cache_id`). Each entry gets: description (food name from MFP), calories, protein_g, carbs_g, fat_g, meal type, date. This matches the existing "quick add" pattern.

### Backend Changes

#### 1. Model: add `source` column to `FoodLog`

`backend/app/models.py` — Add `source` field:

```python
source: Mapped[str] = mapped_column(Text, default="manual")  # manual | myfitnesspal
```

The existing `_add_missing_columns()` in `db.py` will auto-ALTER TABLE with `DEFAULT 'manual'` for existing rows.

Also add a unique index for idempotent MFP upserts (in `db.py`'s `_add_missing_columns`):

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_foodlog_mfp
ON food_log(date, meal, description, source)
WHERE source = 'myfitnesspal'
```

Using a partial index (WHERE source='myfitnesspal') so the constraint only applies to synced entries — manual entries can have duplicate descriptions.

#### 2. New service: `backend/app/services/mfp_sync.py`

Core sync logic, separate from the biometric DataSource pipeline (MFP syncs food, not metrics):

- `sync_date(db, day)` — Fetches one day's diary via python-myfitnesspal, upserts entries into FoodLog
- `sync_range(db, start, end)` — Iterates days, calls sync_date, logs results to UserSetting keys
- `check_cookie(db)` — Tests cookie validity by fetching today's diary
- `get_mfp_client(db)` — Reads cookie string from `UserSetting(key="mfp_cookie")`, constructs CookieJar, returns `myfitnesspal.Client`

Meal name mapping: MFP's "Breakfast"/"Lunch"/"Dinner"/"Snacks" -> our "breakfast"/"lunch"/"dinner"/"snack".

Sync strategy: **delete-then-insert** per date. `sync_date` deletes all `source='myfitnesspal'` rows for the date, then inserts fresh entries. This cleanly handles edits, renames, and deletions in MFP without orphaned rows. The partial unique index is a defensive safety net against bugs creating duplicates.

#### 3. New router: `backend/app/routers/mfp.py`

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/mfp/status` | Cookie status, last sync time/status/error |
| `PUT` | `/api/mfp/cookie` | Store cookie string, validate immediately |
| `DELETE` | `/api/mfp/cookie` | Clear cookie, disable sync |
| `POST` | `/api/mfp/sync` | Manual sync trigger, `?days=3` param |

UserSetting keys used:
- `mfp_cookie` — the raw cookie string
- `mfp_last_sync_at` — ISO timestamp
- `mfp_last_sync_status` — "ok" | "error" | "cookie_expired"
- `mfp_last_sync_error` — error message (truncated)

#### 4. Scheduler: `backend/app/scheduler.py`

Add `_run_mfp_sync()` job at 22:00 daily (after dinner is likely logged). Syncs last 2 days. Skips silently if no cookie is configured. Also runs on startup catch-up if cookie exists and last sync > 12h ago.

#### 5. Schema updates: `backend/app/schemas.py`

- `FoodLogOut`: add `source: str = "manual"`
- New: `MfpStatusOut(enabled, cookie_set, last_sync_at, last_sync_status, last_sync_error)`

#### 6. Register router: `backend/app/main.py`

Add `from .routers import mfp` and `app.include_router(mfp.router)`.

#### 7. Dependency: `backend/pyproject.toml`

Add `"myfitnesspal"` to dependencies.

### Frontend Changes

#### 1. Settings page MFP card: `frontend/src/pages/SettingsPage.tsx`

New section in settings with:
- Status indicator (green/amber/gray dot)
- Password-masked textarea for cookie string
- "Save & Test" button (PUT cookie, then validate)
- "Sync Now" button (POST sync)
- "Disconnect" button (DELETE cookie)
- Last sync timestamp and status
- Setup instructions: "1. Log into myfitnesspal.com 2. Open DevTools Console 3. Run document.cookie 4. Paste below"

#### 2. MFP badge on food entries: `frontend/src/components/MealCard.tsx`

Small "MFP" label next to entries where `source === "myfitnesspal"`, styled subtly (muted text, smaller font).

#### 3. Types: `frontend/src/api/types.ts`

Add `source?: string` to `FoodLogRow`. Add `MfpStatus` interface.

### Files Modified

| File | Change |
|------|--------|
| `backend/app/models.py` | Add `source` column to FoodLog |
| `backend/app/db.py` | Add partial unique index for MFP dedup |
| `backend/app/schemas.py` | Add `source` to FoodLogOut, add MfpStatusOut |
| `backend/app/main.py` | Register mfp router |
| `backend/app/scheduler.py` | Add MFP sync job |
| `backend/pyproject.toml` | Add myfitnesspal dependency |
| `frontend/src/api/types.ts` | Add source to FoodLogRow, add MfpStatus |
| `frontend/src/pages/SettingsPage.tsx` | Add MFP connection card |
| `frontend/src/components/MealCard.tsx` | Add MFP source badge |

### Files Created

| File | Purpose |
|------|---------|
| `backend/app/services/mfp_sync.py` | Core sync logic |
| `backend/app/routers/mfp.py` | MFP API endpoints |

### Edge Cases

- **Empty MFP day:** No entries synced, no error — this is normal
- **Unknown meal name:** Log warning, skip entry (MFP occasionally has custom meal names on premium)
- **Unicode food names:** Handled natively by SQLite TEXT columns
- **Cookie expires mid-sync:** Per-day try/except, partial sync is fine, status set to "cookie_expired"
- **User logs food both in MFP and manually:** Both coexist — different `source` values, no conflict
- **User edits MFP entry after sync:** Next sync's delete-then-insert picks up the change

### Verification

1. **Backend unit test:** Mock python-myfitnesspal Client, verify sync_date creates correct FoodLog rows
2. **Manual E2E:** Configure real MFP cookie, trigger sync via `POST /api/mfp/sync`, verify entries appear in `GET /api/food/log?date=...`
3. **Cookie expiry:** Clear cookie, verify sync fails gracefully and status shows "cookie_expired"
4. **Frontend:** Verify MFP card shows status correctly, entries show MFP badge, dashboard calorie totals include synced entries
5. **Idempotency:** Sync same day twice, verify no duplicate entries
6. **Scheduler:** Verify MFP sync runs at 22:00 and on startup catch-up
