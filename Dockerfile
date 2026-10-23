# syntax=docker/dockerfile:1
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock .
# Optional CA mount supports managed environments without weakening TLS.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements.lock
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app app \
    && mkdir /app/reports /app/state && chown app:app /app/reports /app/state
COPY --chmod=444 collector.py backfill.py analysis.py storage.py bybit.py health.py ./
USER app
CMD ["python", "-u", "collector.py"]

FROM runtime AS test
USER root
COPY requirements-test.lock .
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements-test.lock
COPY --chown=app:app tests ./tests
USER app
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
