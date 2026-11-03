# syntax=docker/dockerfile:1.7
# ---------- Stage 1: build wheels (keeps compilers/pip cache out of the final image)
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ---------- Stage 2: runtime
FROM python:3.12-slim AS runtime

# Injected by CI (git commit SHA) so the running app can show which build it is.
ARG APP_VERSION=dev

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_VERSION=${APP_VERSION}

LABEL org.opencontainers.image.title="student-portal" \
      org.opencontainers.image.description="Student Information System (Flask) deployed to Amazon EKS via GitOps" \
      org.opencontainers.image.version="${APP_VERSION}"

# Dedicated non-root user (fixed UID so Kubernetes runAsNonRoot can verify it)
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* \
 && rm -rf /wheels

COPY --chown=app:app gunicorn.conf.py ./
COPY --chown=app:app app ./app

USER 10001
EXPOSE 8080

# Docker-level health check (Kubernetes uses its own probes defined in k8s/deployment.yaml)
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2).status == 200 else 1)"

CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:create_app()"]
