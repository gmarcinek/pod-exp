# syntax=docker/dockerfile:1.7

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — frontend build (Vite/React)
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY frontend/ ./
RUN npm run build


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — Piper TTS (Linux x86_64) download
# ─────────────────────────────────────────────────────────────────────────────
FROM debian:bookworm-slim AS piper-fetch

ARG PIPER_VERSION=2023.11.14-2
ARG PIPER_ARCH=x86_64

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl tar \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/piper \
    && curl -fsSL -o /tmp/piper.tar.gz \
    "https://github.com/rhasspy/piper/releases/download/${PIPER_VERSION}/piper_linux_${PIPER_ARCH}.tar.gz" \
    && tar -xzf /tmp/piper.tar.gz -C /opt/piper --strip-components=1 \
    && rm /tmp/piper.tar.gz \
    && chmod +x /opt/piper/piper


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — Python runtime
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Piper potrzebuje libstdc++ i espeak-ng do fonemizacji
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    libstdc++6 \
    libgomp1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

# Kod aplikacji
COPY *.py ./
COPY agents/ ./agents/
COPY tools/ ./tools/
COPY templates/ ./templates/
COPY static/ ./static/
COPY scripts/ ./scripts/

# Frontend build z etapu 1
COPY --from=frontend-build /frontend/dist ./frontend/dist

# Piper z etapu 2
COPY --from=piper-fetch /opt/piper /opt/piper

ENV PIPER_EXECUTABLE=/opt/piper/piper \
    PIPER_MODEL_DIR=/app/piper_models \
    PIPER_DEFAULT_MODEL=pl_PL-darkman-medium \
    OLLAMA_BASE_URL=http://host.docker.internal:11434/v1 \
    PORT=5000

# Katalogi montowane jako wolumeny (utworzone, by uniknąć błędów przy starcie)
RUN mkdir -p /app/debates /app/editorial-data /app/piper_models

EXPOSE 5000

# gunicorn z gthread — działa dobrze ze streamingiem SSE; --timeout 0 = brak limitu
CMD ["gunicorn", \
    "--bind", "0.0.0.0:5000", \
    "--workers", "1", \
    "--threads", "8", \
    "--worker-class", "gthread", \
    "--timeout", "0", \
    "--access-logfile", "-", \
    "--error-logfile", "-", \
    "app:app"]
