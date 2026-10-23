#!/usr/bin/env bash
# Restore only into a newly created disposable database, never market.
set -euo pipefail
cd "$(dirname "$0")/.."
backup="${1:?Pass path to a backup dump}"
[ -r "$backup" ]
docker compose exec -T db createdb -U market restore_test
trap 'docker compose exec -T db dropdb -U market restore_test' EXIT
docker compose exec -T db pg_restore --exit-on-error --no-owner -U market -d restore_test < "$backup"
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U market -d restore_test -c 'SELECT count(*) FROM candles;'
