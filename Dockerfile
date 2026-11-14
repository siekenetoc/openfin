FROM python:3.12-slim-bookworm

# Build-Argumente für nahtloses Host-Bind-Mount Mapping
ARG UID=1000
ARG GID=1000

# Python- & Playwright-Umgebungsvariablen
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# 1. System-Abhängigkeiten für PostgreSQL, FinTS/XML (lxml/sepaxml), Crypto & Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    pkg-config \
    curl \
    git \
    gettext \
    libpq-dev \
    postgresql-client \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    libwebp-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. Non-Root User & Gruppe exakt passend zur Host-UID/GID anlegen
RUN groupadd -g "${GID}" -o openfin && \
    useradd -m -u "${UID}" -g "${GID}" -o -s /bin/bash openfin && \
    mkdir -p /app /ms-playwright && \
    chown -R "${UID}:${GID}" /app /ms-playwright

# 3. Python-Abhängigkeiten installieren
COPY --chown=${UID}:${GID} requirements.txt /app/requirements.txt
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r /app/requirements.txt

# 4. Playwright OS-Abhängigkeiten (als root) und Chromium-Binary (für den User) installieren
RUN playwright install-deps chromium && \
    chown -R "${UID}:${GID}" /ms-playwright

# Wechsel auf den unprivilegierten Host-User für die Browser-Installation
USER ${UID}:${GID}
RUN playwright install chromium

# 5. Applikationscode kopieren
COPY --chown=${UID}:${GID} . /app

EXPOSE 8000
