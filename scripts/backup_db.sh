#!/bin/sh
# Copy of the database (Neon, or any PostgreSQL 17).
# Usage: scripts/backup_db.sh [file name]   → backups/<file>, by default scoremaster-YYYY-MM-DD-HHMM.dump
set -eu
cd "$(dirname "$0")/.."
. scripts/db_url.sh
name=${1:-scoremaster-$(date +%Y-%m-%d-%H%M).dump}
mkdir -p backups
PGURL=$(pg_url "$(db_url)")
export PGURL
# pg_dump creates its file before connecting: a failed copy must not leave an empty .dump behind
# (2026-10-14, IP not yet allowed in Render). Written as .partial and renamed only when complete.
partial="$name.partial"
trap 'rm -f "backups/$partial"' EXIT
pg sh -c 'pg_dump "$PGURL" --format=custom --no-owner --no-privileges --file="/backups/'"$partial"'"'
mv "backups/$partial" "backups/$name"
trap - EXIT
echo "Copia guardada en backups/$name. Filas copiadas:"
pg sh -c 'psql "$PGURL" --no-psqlrc --quiet --tuples-only --command "$0"' "$COUNTS_SQL"
