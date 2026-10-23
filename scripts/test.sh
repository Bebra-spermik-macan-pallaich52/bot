#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
args=(-p "${CPL_TEST_PROJECT:-crypto-pattern-lab-tests}" -f compose.test.yaml)
if [ -n "${CPL_TEST_OVERRIDE:-}" ]; then
    args+=(-f "$CPL_TEST_OVERRIDE")
fi
trap 'docker compose "${args[@]}" down' EXIT
docker compose "${args[@]}" up --build --abort-on-container-exit --exit-code-from tests
