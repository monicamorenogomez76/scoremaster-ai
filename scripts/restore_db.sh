#!/bin/sh
# Restores a copy made with backup_db.sh into an empty database (a new one in Neon, or a local one).
# Usage: scripts/restore_db.sh backups/<file>.dump   (asks for the URL of the database to restore into)
set -eu
cd "$(dirname "$0")/.."
. scripts/db_url.sh
file=${1:?Indica el archivo de copia: scripts/restore_db.sh backups/<archivo>.dump}
[ -f "$file" ] || { echo "No existe $file" >&2; exit 1; }
case "$file" in backups/*) ;; *) echo "La copia debe estar en backups/" >&2; exit 1 ;; esac
PGURL=$(pg_url "$(db_url)")
export PGURL
pg sh -c 'pg_restore --dbname="$PGURL" --clean --if-exists --no-owner --no-privileges --exit-on-error "/backups/'"$(basename "$file")"'"'
echo "Copia restaurada. Filas en la base de destino:"
pg sh -c 'psql "$PGURL" --no-psqlrc --quiet --tuples-only --command "$0"' "$COUNTS_SQL"
