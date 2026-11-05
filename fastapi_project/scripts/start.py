"""Create local database credentials once and start PostgreSQL + API with Docker."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description="Start the telecom API and its own PostgreSQL database")
    parser.add_argument("--port", type=int, default=8000, help="Local API port (default: 8000)")
    parser.add_argument("--cloud", action="store_true", help="Use the managed cloud CA bundle for the build")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")

    subprocess.run(["docker", "compose", "version"], check=True)
    credentials = ROOT / ".env.docker"
    if not credentials.exists():
        # Exclusive creation preserves existing database credentials on repeat runs.
        fd = os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write("TELECOM_DB_PASSWORD=" + secrets.token_hex(32) + "\n")
        print("Created .env.docker with a random database password.", flush=True)

    environment = os.environ.copy()
    environment["TELECOM_API_PORT"] = str(args.port)
    command = ["docker", "compose", "--env-file", str(credentials), "-f", "compose.yaml"]
    if args.cloud:
        command += ["-f", "compose.cloud.yaml"]
        environment.setdefault("BUILDX_CONFIG", "/workspace/buildx")
    subprocess.run(command + ["up", "-d", "--build", "--wait", "--wait-timeout", "120"],
                   cwd=ROOT, env=environment, check=True)

    # Test both API/database access and the generated documentation after healthchecks.
    opener = build_opener(ProxyHandler({}))
    base = f"http://127.0.0.1:{args.port}/api/v1"
    for path in ("/tarifs", "/clients", "/openapi.json"):
        with opener.open(base + path, timeout=10) as response:
            json.load(response)
    print(f"API and PostgreSQL are ready. Swagger: {base}/docs")


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Startup failed: {exc}", file=sys.stderr)
        sys.exit(1)
