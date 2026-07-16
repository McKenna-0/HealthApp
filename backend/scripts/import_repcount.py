"""Import a RepCount CSV export (one row per set) into the app database.

Usage:  uv run python scripts/import_repcount.py <path-to-csv> [--dry-run]
                                                 [--no-bodyweight]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal, init_db  # noqa: E402
from app.services.repcount_import import import_csv_file  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", help="Path to the RepCount export CSV")
    parser.add_argument("--dry-run", action="store_true", help="Report only; roll back")
    parser.add_argument(
        "--no-bodyweight", action="store_true", help="Skip importing the Bodyweight column"
    )
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        stats = import_csv_file(
            db,
            args.csv_path,
            dry_run=args.dry_run,
            import_bodyweight=not args.no_bodyweight,
        )
    finally:
        db.close()

    if args.dry_run:
        print("DRY RUN - nothing was written\n")
    print(stats.summary())


if __name__ == "__main__":
    main()
