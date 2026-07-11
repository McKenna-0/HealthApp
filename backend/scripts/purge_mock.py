"""Purge mock-source rows now that real Garmin data flows.

Takes a .backup snapshot first, then deletes:
  - daily_metrics / sleep / activities / weight_log / sync_log rows with source='mock'
  - seeded mock food logs   (description LIKE 'Mock %', no food_cache link)
  - seeded mock context logs (fingerprints from seed_mock.py)

Usage:  uv run python scripts/purge_mock.py --yes
"""

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402


def main(confirmed: bool) -> None:
    db_path = settings.db_path
    if not db_path.exists():
        print(f"No database at {db_path}")
        return

    backup_path = db_path.parent / f"health-pre-purge-{datetime.now():%Y%m%d-%H%M%S}.db"
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(backup_path)
    src.backup(dst)
    dst.close()
    print(f"Backup written to {backup_path}")

    deletions = [
        ("daily_metrics", "source='mock'"),
        ("sleep", "source='mock'"),
        ("activities", "source='mock'"),
        ("weight_log", "source='mock'"),
        ("sync_log", "source='mock'"),
        ("food_log", "description LIKE 'Mock %' AND food_cache_id IS NULL"),
        ("context_log", "note IN ('mock drinks','mock cold')"),
        ("context_log", "type='caffeine' AND ts LIKE '%T08:00:00'"),
    ]

    cur = src.cursor()
    for table, where in deletions:
        count = cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]
        print(f"{table:15s} WHERE {where}: {count} rows")
        if confirmed and count:
            cur.execute(f"DELETE FROM {table} WHERE {where}")

    if confirmed:
        src.commit()
        print("Purged.")
    else:
        print("\nDry run only - re-run with --yes to delete.")
    src.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="actually delete")
    main(parser.parse_args().yes)
