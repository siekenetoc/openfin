# INTERVIEW.md – Phase 0: Klärungsfragen, Entscheidungen & Annahmen

**Projekt:** OpenFin – Multi-Tenant Enterprise Banking, PSP & ERP-Reconciliation Hub
**Datum:** 2026-11-14
**Status:** Interview protokolliert. Da die Anweisung lautete, nach dem Interview **ohne weitere Rückfragen** vollständig autonom weiterzuarbeiten, wurden nicht beantwortete Punkte mit dokumentierten, produktionsnahen Defaults belegt. Alle Defaults sind zentral in `.env.example` bzw. `config/settings/base.py` änderbar.

---

## 1. Pflichtfragen aus der Spezifikation

### F1 – GitHub Deploy-Token / SSH-Zugriff
**Frage:** Welchen GitHub Deploy-Token (PAT bzw. SSH-Key) und welches Repository soll ich für den Account `siekenetoc` verwenden?

**Antwort / Entscheidung:**
- **Kein Token übermittelt.** Es wurden keine Credentials in das Repository geschrieben.
- Lokales Git-Repository wurde initialisiert und exakt konfiguriert:
  - `user.name = siekenetoc`
  - `user.email = siekenet.oc@sieke-net.com`
- Als Remote-Name ist `origin` vorbereitet. Die Remote-URL wird **nicht** geraten.
- **Repository-Name (Annahme):** `Banking-OpenFIN` (entspricht dem lokalen Verzeichnisnamen).
- **Push-Status:** Alle Meilensteine werden lokal committet. Der Push zu GitHub ist blockiert, bis ein Token/SSH-Key und die exakte Remote-URL vorliegen.
- **Sicherheitshinweis:** Tokens niemals in `.env.example`, `docker-compose.yml` oder Commits ablegen. Empfohlen: `git remote add origin git@github.com:siekenetoc/Banking-OpenFIN.git` oder HTTPS mit Credential-Helper.

### F2 – Host-Ports für Webserver / Reverse-Proxy
**Frage:** Welche Ports und welche Bind-IP sollen im lokalen Netzwerk verwendet werden?

**Antwort / Entscheidung (Default):**
- `BIND_IP=127.0.0.1` (nur lokal erreichbar; für LAN-Betrieb auf `0.0.0.0` ändern)
- `WEB_PORT=8045` → Django/Gunicorn intern `8000`
- PostgreSQL und Redis werden **nicht** nach außen veröffentlicht (nur im Docker-Netz `openfin_net`).
- Ein separater Reverse-Proxy ist nicht Teil des Compose-Stacks; Caddy/Nginx/Traefik kann vorgeschaltet werden. `CSRF_TRUSTED_ORIGINS` ist entsprechend vorbereitet.

### F3 – Optionale Endpunkte (LLM, SMTP, Paperless-ngx)
**Frage:** Welche konkreten URLs/Zugänge sollen für lokale LLM-API, SMTP-Relay und Paperless-ngx verwendet werden?

**Antwort / Entscheidung (Defaults, in `.env.example` dokumentiert):**
- **Local LLM:** `http://192.168.178.20:4000/v1` (OpenAI-kompatibel, z. B. LiteLLM/vLLM), Modell `qwen-2.5-coder-32b`
- **SMTP:** `smtp.dein-mailserver.de:587`, TLS, Absender `billing@deine-domain.de`
- **Paperless-ngx:** `http://192.168.178.10:8000/api`
- Alle Werte sind Dummy-Defaults. Mandantenspezifische Secrets werden verschlüsselt im Tenant-Schema gespeichert; die `.env`-Werte dienen nur als Fallback.
- **FinTS-Produktregistrierungsnummer:** Placeholder `CHANGE_ME_FINTS_PRODUCT_ID`; für echte Bankverbindungen ist eine bei der Deutschen Kreditwirtschaft registrierte Produkt-ID erforderlich.

---

## 2. Zusätzliche Architekturentscheidungen

| Thema | Entscheidung | Begründung |
|---|---|---|
| Mandanten-Isolation | `django-tenants`, ein PostgreSQL-Schema pro Tenant (`tenant_<slug>`), `public` für Stammdaten/CMS/Plattform-Admin | Vorgabe der Spezifikation |
| CMS-Schema | `ContentPage` liegt im `public`-Schema und besitzt optionalen Tenant-FK; `tenant=NULL` = global, sonst mandantenspezifisch | Globale AGB/Impressum möglich, ohne Tenant-Duplikate |
| Benutzer | Custom User im Shared-Schema mit optionalem Tenant-FK und `is_platform_admin` | Zentraler Login, Tenant-Zuordnung, Plattform-Admin |
| Verschlüsselung | Eigene `EncryptedTextField`/`EncryptedCharField` auf Basis von `cryptography.Fernet` (AES-128-CBC + HMAC, Fernet-Standard) | Keine Abhängigkeit von unmaintainten Drittanbieter-Feldern; Schlüsselrotation vorbereitet |
| Assets | Tailwind CLI + esbuild; Quill lokal; Inter/JetBrains Mono als lokale WOFF2 | Zero-CDN-Policy |
| FinTS | `python-fints`-Adapter mit injizierbarem Mock-Client; TAN-Dialog-State Base64-verschlüsselt in Redis + DB | Testbarkeit ohne echte Bank; PSD2/SCA-fähig |
| Reconciliation | 3 Stufen, Konfidenz 0–100; Postgres `pg_trgm`, Fallback `rapidfuzz`/`difflib` | Produktion: Trigram; Tests auch ohne Extension lauffähig |
| SEPA | Eigener PAIN.008.001.02/PAIN.001.001.03-Generator via lxml, schema-nah und testbar | Volle Kontrolle, keine versteckten Defaults |
| ERPNext | REST-Client + signierte Webhooks (HMAC-SHA256) | Idempotenz und Sicherheit |
| DATEV | EXTF v700 CSV mit BOM, Semikolon, SKR-Konten pro Tenant | Excel-/DATEV-kompatibel |
| KI | OpenAI-kompatibler Client; Text-to-SQL nur lesend, Whitelist, LIMIT | Kein destruktives SQL |
| Tests | `pytest` + `pytest-django`, Postgres-Testdatenbank, Tenant-Fixtures | Vorgabe Self-Testing |

## 3. Nicht beantwortete Punkte / bewusste Annahmen

1. **GitHub-Remote:** unbekannt, daher kein Push. Lokale Commits vorhanden.
2. **Produktivdomain:** `*.openfin.local` bzw. `localhost` für Demo. Tenant-Domains werden über `core.Domain` verwaltet.
3. **Banking-Zugänge:** keine echten FinTS-Zugänge vorhanden; Mock-Dialoge und Adapter für den Produktivbetrieb.
4. **Zahlungsprovider-Keys:** keine echten Keys; Test-/Dummy-Konfiguration, Webhook-Signaturprüfung implementiert.
5. **Steuerberater-/Mandantennummern (DATEV):** Platzhalter pro Tenant konfigurierbar (`DATEVAdvisorConfig`).
6. **Rechtliche Texte:** Standardseiten werden mit neutralen Mustertexten geseedet und sind vor Produktivgang juristisch zu prüfen.

## 4. Freigabe-Status

Das Interview gilt mit diesen dokumentierten Defaults als abgeschlossen. Die Umsetzung erfolgt autonom gemäß Meilensteinplan; alle Abweichungen und Annahmen werden in `PLAN.md` fortgeschrieben.
