# syntax=docker/dockerfile:1
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements.txt
RUN useradd --uid 10001 --create-home app
COPY --chown=app:app app ./app
USER app
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:main_app", "--host", "0.0.0.0", "--port", "8000"]
