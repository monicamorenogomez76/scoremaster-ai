#!/bin/sh
# Copy of the database (Render's free one expires 30 days after it was created, ~2026-11-06).
# Usage: scripts/backup_db.sh [file name]   → backups/<file>, by default scoremaster-YYYY-MM-DD-HHMM.dump
# Before: in Render, database → Access Control, allow your IP; afterwards, remove it again.
set -eu
cd "$(dirname "$0")/.."
. scripts/db_url.sh
name=${1:-scoremaster-$(date +%Y-%m-%d-%H%M).dump}
mkdir -p backups
PGURL=$(pg_url "$(db_url)")
export PGURL
pg sh -c 'pg_dump "$PGURL" --format=custom --no-owner --no-privileges --file="/backups/'"$name"'"'
echo "Copia guardada en backups/$name. Filas copiadas:"
pg sh -c 'psql "$PGURL" --no-psqlrc --quiet --tuples-only --command "$0"' "$COUNTS_SQL"
