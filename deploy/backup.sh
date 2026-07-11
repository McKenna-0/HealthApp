#!/usr/bin/env bash
# Nightly SQLite backup: consistent .backup snapshot (WAL-safe), keep 14.
set -euo pipefail

DB="/home/pi/health-app/backend/data/health.db"
BACKUP_DIR="/home/pi/health-app/backups"
KEEP=14

mkdir -p "$BACKUP_DIR"
STAMP=$(date +%F)
sqlite3 "$DB" ".backup '$BACKUP_DIR/health-$STAMP.db'"

# rotate
ls -1t "$BACKUP_DIR"/health-*.db | tail -n +$((KEEP + 1)) | xargs -r rm --

echo "Backup complete: health-$STAMP.db ($(ls -1 "$BACKUP_DIR" | wc -l) kept)"
