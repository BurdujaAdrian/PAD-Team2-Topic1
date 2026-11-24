#!/usr/bin/env bash
# Run from CPR before starting the new service API for the first time.
set -euo pipefail
cd "$(dirname "$0")/.."
service=${1:-}
case "$service" in zombie|resource) ;; *) echo 'Usage: scripts/import-service-database.sh zombie|resource' >&2; exit 2;; esac
compose=(docker compose --profile legacy-databases)
"${compose[@]}" stop "$service-api"
"${compose[@]}" up -d --wait "$service-db" "$service-db-1" "$service-db-2" "$service-db-3"
count=$("${compose[@]}" exec -T "$service-db-1" sh -c 'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -h 127.0.0.1 -U "$POSTGRESQL_USERNAME" -d "$POSTGRESQL_DATABASE" -Atc "SELECT count(*) FROM pg_tables WHERE schemaname = '\''public'\''"')
if [[ "$count" != 0 ]]; then
    echo 'Target database is not empty. Refusing to overwrite it; API remains stopped.' >&2
    exit 1
fi
mkdir -p backups
backup=$(mktemp "backups/$service.XXXXXX")
chmod 600 "$backup"
"${compose[@]}" exec -T "$service-db" sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup"
"${compose[@]}" exec -T "$service-db-1" sh -c 'PGOPTIONS="-c synchronous_commit=on" PGPASSWORD="$POSTGRESQL_PASSWORD" pg_restore -h 127.0.0.1 -U "$POSTGRESQL_USERNAME" -d "$POSTGRESQL_DATABASE" --no-owner --no-privileges --single-transaction' < "$backup"
echo "Imported $service. Backup retained at $backup. Old volume is untouched."
echo "Start the new image with: docker compose up -d $service-api"
