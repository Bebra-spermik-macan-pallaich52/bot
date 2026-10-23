#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
venv_path="${CPL_VENV:-/workspace/venvs/crypto-pattern-lab}"
python3 -m venv "$venv_path"
"$venv_path/bin/python" -m pip install -r requirements-dev.lock
"$venv_path/bin/python" -m pip check
# Generate only a local database password; never replace an existing .env.
"$venv_path/bin/python" - <<'PY'
from pathlib import Path
import secrets
p = Path('.env')
if not p.exists():
    template = Path('.env.example').read_text()
    with p.open('x') as f:
        f.write(template.replace('replace_with_a_long_random_password', secrets.token_urlsafe(32)))
    p.chmod(0o600)
PY
