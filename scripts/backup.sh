#!/usr/bin/env bash
# Use cron/systemd on the server; copy backups off-host separately.
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
mkdir -p backups
file="backups/market-$(date -u +%Y%m%dT%H%M%SZ).dump"
[ ! -e "$file" ]
trap 'rm -f "$file.partial"' EXIT
docker compose exec -T db pg_dump -U market -d market -Fc > "$file.partial"
[ -s "$file.partial" ]
mv "$file.partial" "$file"
echo "$file"
