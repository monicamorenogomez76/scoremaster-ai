# Shared by backup_db.sh and restore_db.sh: the database URL from DATABASE_URL_EXTERNAL or asked without
# echoing it, so it never stays in the shell history. Render gives it in Connections → External Database URL.
db_url() {
  if [ -n "${DATABASE_URL_EXTERNAL:-}" ]; then
    printf '%s' "$DATABASE_URL_EXTERNAL"
    return
  fi
  printf 'URL de la base de datos (no se muestra): ' >&2
  stty -echo 2>/dev/null || true
  read -r url
  stty echo 2>/dev/null || true
  printf '\n' >&2
  printf '%s' "$url"
}

# Rows of the main tables: compare them before and after a restore.
COUNTS_SQL="select 'users' as tabla, count(*) from users
union all select 'works', count(*) from works
union all select 'analyses', count(*) from analyses
union all select 'rehearsals', count(*) from rehearsals
union all select 'concerts', count(*) from concerts
union all select 'evaluation_campaigns', count(*) from evaluation_campaigns
union all select 'evaluation_ratings', count(*) from evaluation_ratings
union all select 'evaluation_llm_reviews', count(*) from evaluation_llm_reviews
order by 1"

# The URL as the PostgreSQL tools in the container understand it: without SQLAlchemy's «+psycopg», and a
# database on this computer (Compose) reached as host.docker.internal.
pg_url() {
  printf '%s' "$1" | sed -e 's#^postgresql+psycopg://#postgresql://#' \
    -e 's#@127\.0\.0\.1:#@host.docker.internal:#' -e 's#@localhost:#@host.docker.internal:#'
}

# PostgreSQL client tools in Docker: nothing to install. Version 18 (2026-11-17): a new Neon project runs 18, which the tools of
# 17 refuse to copy; the newer tools copy and restore 17 as well.
pg() {
  docker run --rm -i -e PGURL="$PGURL" -v "$PWD/backups:/backups" postgres:18 "$@"
}
