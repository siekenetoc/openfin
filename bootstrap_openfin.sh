#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-.}"

echo "[*] Initialisiere OpenFin Verzeichnisstruktur in: $(realpath "$PROJECT_DIR")"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# 1. Docker Bind-Mount Verzeichnisse (Datenbank, Cache, Medien, Logs)
mkdir -p \
  ./docker-data/postgres \
  ./docker-data/redis \
  ./docker-data/static \
  ./docker-data/media/cms \
  ./docker-data/media/statements \
  ./docker-data/media/invoices \
  ./docker-data/media/sepa_xml \
  ./docker-data/playwright_profiles \
  ./docker-data/logs/django \
  ./docker-data/logs/celery \
  ./docker-data/logs/playwright

# 2. Lokale Asset-Pipeline (Zero-CDN Node.js Build)
mkdir -p \
  ./static/src/css \
  ./static/src/js \
  ./static/src/fonts \
  ./static/dist

# 3. Pflicht-Dokumentationsdateien als Anker für den Coding Agent anlegen
for doc in INTERVIEW.md PLAN.md README.md MANUAL.md; do
  if [ ! -f "./$doc" ]; then
    touch "./$doc"
    echo "[+] Datei angelegt: $doc"
  fi
done

# 4. .gitignore erzeugen (Schutz vor versehentlichem Commit von Bankdaten/DB-Files)
if [ ! -f "./.gitignore" ]; then
cat << 'EOF' > ./.gitignore
# Persistente Docker Bind-Mounts (niemals ins Repo pushen!)
/docker-data/

# Lokale Umgebungsvariablen & Secrets
.env
.env.*
!.env.example

# Python / Django
__pycache__/
*.py[cod]
*.sqlite3
.pytest_cache/
.coverage
htmlcov/
.venv/
venv/

# Node.js (Assets werden lokal nach /static/dist/ kompiliert)
node_modules/
npm-debug.log*
EOF
  echo "[+] .gitignore mit Schutz für /docker-data/ und .env erstellt."
fi

# 5. Berechtigungen sauber auf den aktuellen Host-User setzen
chown -R "$(id -u):$(id -g)" ./docker-data ./static
chmod -R 750 ./docker-data

echo "[✓] Struktur erfolgreich angelegt. Aktuelle UID/GID für Docker: $(id -u):$(id -g)"
