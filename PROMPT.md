# MASTER PROMPT & PROJEKTSPEZIFIKATION: "OpenFin" – Multi-Tenant Enterprise Banking, PSP & ERP-Reconciliation Hub

Du agierst als autonomer Senior Full-Stack Systemarchitekt und Lead Python/Django Engineer. Deine Aufgabe ist die vollständige Entwicklung einer selbst gehosteten, betriebssystemunabhängigen, mandantenfähigen Finanz-, Banking- und Billing-Plattform (StarMoney Business Äquivalent + Payment Service Provider + automatisierte ERPNext/DATEV-Reconciliation-Engine).

---

## 1. STRIKTE ARBEITSANWEISUNGEN & WORKFLOW-PROTOKOLL FÜR DEN AGENTEN

Halte dich zwingend und ohne Ausnahme an diesen Ablauf:

### 1.1 Phase 0: Analyse, Rückfragen & `INTERVIEW.md`
1. **Stelle zuerst deine Fragen:** Bevor du mit der eigentlichen Programmierung der Meilensteine beginnst, analysiere diese Spezifikation auf eventuelle Unklarheiten oder fehlende Umgebungsparameter.
2. **Pflichtfragen im Interview:** Frage mich zwingend nach:
   - Dem **GitHub Deploy-Token** (bzw. Personal Access Token / SSH-Key-Zugriff) und dem exakten **Repository-Namen** für den Account `siekenetoc`.
   - Gewünschten **Host-Ports** für den Webserver/Reverse-Proxy im lokalen Netzwerk.
   - Optionalen Endpunkten (z. B. lokale LLM-API-URL für vLLM/LiteLLM, Standard-SMTP-Relay, Paperless-ngx URL), sofern diese nicht als reine Dummy-Defaults in der `.env.example` angelegt werden sollen.
3. **Dokumentation des Interviews:** Schreibe alle deine Fragen und meine anschließenden Antworten vollständig und strukturiert in die Datei `INTERVIEW.md`.

### 1.2 Git- & GitHub-Konfiguration
1. Initialisiere ein lokales Git-Repository im Projektstammverzeichnis.
2. Konfiguriere Git lokal für dieses Repository exakt mit:
   - `git config user.name "siekenetoc"`
   - `git config user.email "siekenet.oc@sieke-net.com"`
3. Binde das von mir auf GitHub erzeugte Remote-Repository unter Verwendung des abgefragten Deploy-Tokens ein und pushe nach jedem abgeschlossenen und getesteten Meilenstein.

### 1.3 Lebende Dokumentation (Pflichtdateien)
Erzeuge zu Beginn und aktualisiere **nach jedem einzelnen Meilenstein** unaufgefordert die folgenden vier Dateien gemäß dem aktuellen Entwicklungsstand:
1. **`INTERVIEW.md`**: Vollständiges Protokoll aller initialen Klärungsfragen, Architekturentscheidungen und Antworten.
2. **`PLAN.md`**: Detaillierter technischer Architekturplan, Datenmodell-Spezifikation, Meilenstein-Roadmap und aktueller Fortschrittsstatus (inkl. abgehakter Tasks).
3. **`README.md`**: Technische Projektübersicht, Architektur-Diagramm (ASCII/Mermaid), Quickstart-Guide, `.env`-Konfiguration, Build-Anleitung und Test-Kommandos.
4. **`MANUAL.md`**: Vollumfängliche, praxisnahe Gebrauchsanweisung für Administratoren und Endanwender (Mandanten-Anlage, FinTS-Einrichtung, TAN-Freigaben, ERPNext-Webhook-Setup, SEPA-Einzug, CSV-Exporte, Triage-Shortcuts, CMS-Pflege).

### 1.4 Autonome Abarbeitung & Selbst-Testing
1. Sobald das initiale Interview (`INTERVIEW.md`) abgeschlossen ist und die Basisdokumente stehen, **arbeite alle Meilensteine nacheinander vollständig autonom und ohne weitere Rückfragen ab**.
2. **Zwingendes Self-Testing zwischen den Meilensteinen:** Bevor ein Meilenstein als erledigt markiert wird, musst du das System selbständig auf Vollfunktion testen:
   - Führe automatisierte Unit- und Integrationstests (`pytest` / `python manage.py test`) aus.
   - Prüfe, ob der Node.js Asset-Build fehlerfrei durchläuft.
   - Prüfe, ob alle Docker-Container sauber starten, Migrationen fehlerfrei durchlaufen und Endpunkte valide HTTP-Statuscodes liefern.
   - Behebe auftretende Fehler sofort eigenständig, bevor du die Dokumentation (`README.md`, `PLAN.md`, `MANUAL.md`, `INTERVIEW.md`) aktualisierst und zum nächsten Meilenstein übergehst.

---

## 2. HARTE TECHNISCHE LEITPLANKEN (TECH STACK & INFRASTRUKTUR)

1. **Docker Compose & Bind Mounts (Strikt):**
   - Das gesamte Projekt läuft als `docker-compose.yml` Setup (Services: `web` [Django/Gunicorn], `db` [PostgreSQL 16], `redis` [Redis 7], `celery_worker` [inkl. Playwright/Chromium], `celery_beat`, `node_builder` [Asset-Kompilierung]).
   - **Verwende ausschließlich Bind Mounts** (keine anonymen oder Named Docker Volumes!). Alle persistenten Daten müssen transparent im Projektverzeichnis unter `./docker-data/` liegen (z. B. `./docker-data/postgres`, `./docker-data/redis`, `./docker-data/media`, `./docker-data/static`, `./docker-data/logs`).
2. **Zero-CDN Policy (100 % Lokale Assets via Node.js):**
   - Es dürfen **keinerlei externe CDNs** (kein Tailwind CDN, kein unpkg, kein jsDelivr, kein Google Fonts CDN) im HTML eingebunden werden.
   - Richte eine lokale Node.js Build-Pipeline (`package.json`) ein, die folgende Assets lokal über `npm` installiert und in `./static/dist/` kompiliert/bündelt:
     - **Tailwind CSS** (inkl. `@tailwindcss/forms`, `@tailwindcss/typography`)
     - **Alpine.js** (inkl. `@alpinejs/persist`, `@alpinejs/focus`)
     - **htmx** (`htmx.org`)
     - **Lokale Webfonts** (z. B. Inter & JetBrains Mono als lokale `.woff2`-Dateien)
     - **Lokaler Rich-Text-Editor (RTF)** (z. B. Tiptap, Quill oder TinyMCE/CKEditor lokal gebündelt ohne Cloud-Key)
3. **Backend & Datenbank:**
   - **Python 3.12+** & **Django 5.x** + **Django REST Framework (DRF)** + `drf-spectacular` (OpenAPI/Swagger Dokumentation).
   - **PostgreSQL 16** mit automatisch per Migration aktivierter Extension `pg_trgm` (für Trigram-Fuzzy-Matching).
   - **Multi-Tenancy:** Implementierung über `django-tenants`. Jeder Mandant (z. B. Privat, Firma A, Firma B) erhält ein eigenes isoliertes PostgreSQL-Schema (`tenant_...`). Das `public`-Schema verwaltet die Mandanten-Stammdaten, Domains/Subdomains, das CMS und ein optionales globales Superuser-Aggregations-Dashboard.
4. **Sicherheit (Encryption at Rest):**
   - Sensible Zugangsdaten (FinTS-PINs, PayPal/Stripe/Wero API-Secrets, ERPNext-Keys, Amazon-Passwörter) dürfen **niemals im Klartext** in der Datenbank gespeichert werden.
   - Nutze `django-cryptography` (oder eine dedizierte AES-256/Fernet-Verschlüsselungsschicht auf Model-Field-Ebene), sodass Werte nur zur Laufzeit im RAM für den jeweiligen Task entschlüsselt werden.

---

## 3. FACHLICHE ARCHITEKTUR & FUNKTIONSUMFANG

### 3.1 Modul 1: CMS & Editierbare Einzelseiten (RTF + Images)
- Integriere ein schlankes, mandanten- und global-fähiges Content-Management-System für rechtliche und informative Einzelseiten:
  - Standardseiten: **AGB**, **Impressum**, **Datenschutzerklärung**, **Partner**, **Sonstige Disclaimer / Hinweise**.
  - Beliebig erweiterbar über ein Model `ContentPage` (Felder: `title`, `slug`, `content_html`, `header_image`, `is_published`, `show_in_footer`, `updated_at`).
- **RTF-Editor mit Bild-Upload:** Im Verwaltungsbereich (oder direkt inline für Admins) lassen sich diese Seiten über den lokal gebündelten WYSIWYG/RTF-Editor formatieren. Bilder können direkt per Drag-and-Drop oder Dateiauswahl hochgeladen werden, werden im lokalen Bind-Mount (`./docker-data/media/cms/`) gespeichert und sauber im Text gerendert.

### 3.2 Modul 2: Kern-Banking & FinTS/HBCI Engine (StarMoney-Äquivalenz)
- **Unterstützte Kontotypen (`BankAccount`):**
  - Girokonten, Tagesgeldkonten, Festgeldkonten (FinTS/HBCI)
  - Kreditkarten (via FinTS oder Playwright-Scraper)
  - Wertpapierdepots (Bestandsabruf + automatische Kursaktualisierung über Kurs-APIs)
  - Wallets & E-Commerce (PayPal, Amazon)
  - Offline-Konten (Barkasse / Kassenbuch für manuelle Buchungen)
- **FinTS-Integration (`python-fints`):**
  - Abruf von Kontosalden, Umsätzen (MT940 und CAMT.053) sowie elektronischen Kontoauszügen (PDFs).
  - **Zahlungsverkehr (Ausgangskorb):** Einzelüberweisungen, Sammelüberweisungen (PAIN.001 XML), Echtzeitüberweisungen, Terminüberweisungen, Daueraufträge (Abruf, Anlage, Änderung, Löschung) und SEPA-Lastschriftrückgaben.
- **Asynchrones PSD2 / SCA TAN-Handling (Celery + Redis State-Freezing):**
  - Wirft `python-fints` bei einem Hintergrund-Sync oder einer Überweisung eine `NeedTANResponse` (PushTAN, Decoupled TAN, chipTAN optisch/Flicker, photoTAN), darf der Task nicht abstürzen.
  - Der FinTS-Dialog-State (`client.deconstruct()`) wird Base64-kodiert in Redis/DB eingefroren, das Konto erhält das Flag `needs_tan = True` inkl. Challenge-Text/Grafik (z. B. Flicker-Code oder Matrix-Bild).
  - Im Frontend erscheint sofort via htmx-Polling/Alpine.js ein prominenter TAN-Freigabe-Dialog. Nach Bestätigung durch den User reanimiert ein Celery-Task den Dialog-State und schließt die Transaktion ab.
- **StarMoney-Komfortfunktionen:**
  - Automatische Empfängerverwaltung (Adressbuch aus vergangenen Buchungen).
  - Regelwerk zur automatischen Kategorisierung/Verschlagwortung, Kostenstellen-Zuweisung, Zahlungskalender und 30/60/90-Tage Cashflow-Prognose (Forecasting).

### 3.3 Modul 3: Externe Provider & Headless Scraping (PayPal, Amazon & Co.)
- **PayPal-Integration:** Anbindung über die offizielle PayPal REST API zum Abruf von Transaktionen, Gebühren, Währungen und Salden.
- **Amazon & Kreditkarten Scraper (Playwright):**
  - Kapselung einer modularen Scraper-Engine in Celery-Workern mit Headless Chromium (`playwright`).
  - Extraktion von Bestellhistorien, Einzelpositionen, Rechnungsbeträgen und automatischer Download der PDF-Rechnungen (Speicherung im Media-Bind-Mount), um Bankabbuchungen von Amazon exakt aufzuschlüsseln.

### 3.4 Modul 4: Aktiver Forderungseinzug & Payment Service Provider (PSP)
Die Plattform agiert als aktive Billing-Engine für wiederkehrende Verträge (z. B. IT-Wartungsverträge) und Einmalrechnungen:
- **SEPA-Lastschrifteinzug (`PAIN.008`):**
  - Verwaltung von SEPA-Mandaten (`SEPAMandate`: Mandatsreferenz, Signaturdatum, IBAN, BIC, Typ `CORE` [Basislastschrift] und `B2B` [Firmenlastschrift], Status `RCUR`/`FRST`).
  - Generierung valider `PAIN.008.001.02` XML-Dateien (z. B. via `sepaxml`) und direkter Upload an die Bank über FinTS (Batch-Einzug im Ausgangskorb) oder Download als XML/CSV.
  - **Automatisierte Pre-Notification:** Celery-Task versendet fristgerecht vor Fälligkeit Vorabankündigungs-Mails per SMTP an den Debitor.
- **Multi-Channel Payment Gateways (Stripe, PayPal, Wero):**
  - **Stripe:** Generierung von Checkout-Sessions / Payment Links via `stripe-python` für offene Rechnungen.
  - **PayPal Checkout:** Aktive Zahlungsanforderung via PayPal Orders API.
  - **Wero (EPI):** Schnittstellen-Architektur zur Generierung von Wero Account-to-Account (A2A) Zahlungslinks und QR-Codes für SEPA-Echtzeitzahlungen.
- **Incoming Payment Webhook-Gateway:**
  - Gesicherte DRF-Endpunkte (`/api/webhooks/payments/<provider>/`) mit kryptografischer Signaturprüfung.
  - Bei Zahlungseingang wird die verknüpfte Rechnung in ERPNext sofort auf ein Geldtransit-Konto ("Geldtransit Stripe/PayPal/Wero") verbucht; der spätere Sammel-Payout auf das Bankkonto wird automatisch gegen dieses Transitkonto ausgeglichen.

### 3.5 Modul 5: Enterprise Accounting (ERPNext / Frappe, DATEV, Paperless-ngx, Local AI)
- **Bidirektionale ERPNext (Frappe) Synchronisation:**
  - Model `ERPConfig` pro Mandant (`erp_base_url`, verschlüsselter `api_key`, `api_secret`, `webhook_secret`, Standard-Konten für Skonto und Geldtransit).
  - **Inbound Webhook (`/api/webhooks/erpnext/sales-invoice/`):** Empfängt neue Ausgangsrechnungen (`on_submit`) aus ERPNext und legt sie als `ExpectedPayment` an.
  - **Purchase Invoice Sync:** Holt freigegebene Lieferantenrechnungen aus ERPNext und legt sie unterschriftsreif als SEPA-Überweisung in den FinTS-Ausgangskorb.
  - **Outbound Reconciliation:** Erzeugt bei gematchtem Zahlungseingang vollautomatisch einen `Payment Entry` via Frappe REST API (`POST /api/resource/Payment Entry`) und setzt die Rechnung auf `Paid`.
- **DATEV-Integration:**
  - Export vorkontierter Buchungssätze im offiziellen DATEV-CSV/EXTF-Format sowie Vorbereitung der OAuth2-Schnittstelle für den DATEV Buchungsdatenservice / Rechnungsdatenservice 1.0 (inkl. Berater- und Mandantennummer pro Tenant).
- **Paperless-ngx Kopplung:**
  - REST-API-Client gleicht Buchungen anhand von Betrag, Datum und OCR-Text mit Dokumenten in einer lokalen Paperless-ngx Instanz ab und verlinkt das Beleg-PDF direkt an der Transaktion.
- **Local AI (vLLM / LiteLLM / OpenAI-kompatibler Client):**
  - Semantische Kategorisierung unklarer Verwendungszwecke.
  - Natural-Language-Query-Endpunkt ("Text-to-ORM/SQL") für Abfragen über das eigene Finanzarchiv.

### 3.6 Modul 6: Die 3-Stufen Reconciliation-Engine
Jede eingehende `BankTransaction` durchläuft asynchron eine dreistufige Matching-Pipeline gegen offene `ExpectedPayment`-Datensätze und erhält einen **Confidence Score (0 bis 100 %)**:
1. **Stufe 1 – Regex-Normalisierung & PostgreSQL Trigram-Fuzzy-Match:**
   - Bereinigung von Tippfehlern im Verwendungszweck (z. B. `Rg. 26/0042` -> `RE-2026-0042`).
   - Einsatz von `TrigramSimilarity` (`pg_trgm`) auf `invoice_id`, `customer_name` und `purpose`.
2. **Stufe 2 – Skonto- & Rundungstoleranz-Mathematik:**
   - Erkennt Abweichungen von exakt 2 %, 3 % (oder mandantenspezifischen Skontosätzen) innerhalb der Skontofrist.
   - Übergibt bei Verbuchung an ERPNext automatisch ein `deductions`-Array zur Ausbuchung der Differenz auf das konfigurierte Skontoaufwandskonto.
3. **Stufe 3 – Sammelüberweisungen (Subset Sum / Knapsack Solver):**
   - Identifiziert den Kunden anhand der Absender-IBAN (`BankPartner`-Mapping).
   - Prüft via Kombinatorik (`itertools.combinations`) über alle offenen Rechnungen dieses Kunden, ob eine Teilmenge exakt (oder abzgl. Skonto) die überwiesene Gesamtsumme ergibt, und splittet das `references`-Array im ERPNext `Payment Entry` entsprechend auf.
- **Triage-Eimer:**
  - **Score > 95 % (`AUTO_RECONCILED`):** Sofortige Dunkelverarbeitung und Verbuchung in ERPNext.
  - **Score 50–95 % (`NEEDS_REVIEW`):** Landet im interaktiven Triage-Dashboard.
  - **Score < 50 % (`UNMATCHED`):** Normale Kategorien-Regelverarbeitung ohne ERP-Bezug.

### 3.7 Modul 7: Frontend-UX (htmx + Alpine.js) & Universeller CSV-Export
- **Dark-Mode-First Financial UI:** Übersichtliches, reaktionsschnelles Interface mit Tailwind CSS.
- **Triage-Dashboard ("Inbox Zero" für `NEEDS_REVIEW`):**
  - Split-Row-Darstellung: Links reale FinTS-Bankdaten, rechts der ERPNext-Vorschlag inkl. Score-Badge und gelber/roter Hervorhebung von Skonto- oder Betragsdifferenzen.
  - **htmx One-Click-Approve:** Klick auf "Zuweisen" feuert `hx-post`, zeigt einen Lade-Spinner (`htmx-indicator`), verbucht in ERPNext und blendet die erledigte Zeile per `hx-swap="outerHTML"` flüssig aus.
  - **Alpine.js Keyboard-Navigation:** Tastatursteuerung (`J` / `K` oder Pfeiltasten zum Navigieren zwischen Klärungsfällen, `Enter` zum sofortigen Zuweisen des fokussierten Eintrags, `Esc` zum Aufklappen alternativer Vorschläge).
- **Collection-Dashboard (Forderungseinzug):**
  - Übersicht aller fälligen Rechnungen gruppiert nach Einzugsweg (SEPA-Lastschrift, Stripe, PayPal, Wero).
  - Batch-Auswahl per Alpine.js Checkbox-State zum gesammelten Einreichen von SEPA-PAIN.008-Batches oder Triggern von Payment-Links.
- **Universeller CSV-Export (Pflichtfunktion für alle Tabellen):**
  - Bei **allen** Zahlungseingängen (Bankumsätzen), offenen Positionen (ERP `ExpectedPayment`), SEPA-Einzügen, Depots und Buchungslisten muss eine leistungsfähige CSV-Export-Funktion integriert sein.
  - **Alpine.js Filter- & Selektions-State:** Jede Datentabelle besitzt einen Alpine.js State (`x-data="{ selectedIds: [], selectAll: false, dateFrom: '', dateTo: '', statusFilter: '' }"`). Nutzer können einzelne Zeilen per Checkbox markieren oder nach Zeitraum/Status filtern.
  - **Django Streaming CSV Backend:** Ein dedizierter Export-Endpunkt generiert über Pythons `csv`-Modul und `StreamingHttpResponse` (bzw. `HttpResponse(content_type='text/csv; charset=utf-8-sig')` inkl. BOM für saubere Umlaute in Excel/DATEV) sofort den Download der ausgewählten oder gefilterten Datensätze.

---

## 4. MEILENSTEIN-PLANUNG (AUTONOME ABARBEITUNG NACH INTERVIEW)

Arbeite nach Abschluss von Phase 0 (Interview) exakt diese Meilensteine ab. Teste nach jedem Meilenstein alle Funktionen automatisiert durch und aktualisiere `README.md`, `PLAN.md`, `INTERVIEW.md` und `MANUAL.md`:

- **Meilenstein 1: Repository, Docker-Bind-Mount-Infrastruktur, Node.js-Build & Multi-Tenant Core**
  - Git-Init (`siekenetoc`), Docker Compose mit strikten Bind-Mounts, PostgreSQL (`pg_trgm`), Redis, Celery, Node.js-Pipeline (Tailwind, Alpine.js, htmx, Fonts, lokaler RTF-Editor komplett ohne CDN).
  - Einrichtung von `django-tenants` (Public- & Tenant-Schemas), Custom User Model, Verschlüsselungs-Layer für Credentials, Basis-Layout & Tenant-Switcher.
  - *Self-Test & Doku-Update.*
- **Meilenstein 2: RTF-CMS für Einzelseiten & Medienverwaltung**
  - Implementierung des CMS-Moduls für AGB, Impressum, Datenschutzerklärung, Partner und Disclaimer.
  - Lokaler RTF-Editor mit Bild-Upload in den Media-Bind-Mount, automatisches Seeding der Standardseiten, Footer-Navigation.
  - *Self-Test & Doku-Update.*
- **Meilenstein 3: FinTS/HBCI Core, Kontenverwaltung & Asynchrones TAN-Handling**
  - Models für `BankAccount` (Giro, Tagesgeld, Festgeld, Kreditkarte, Depot, Barkasse), `BankTransaction`, `BankPartner`.
  - Integration von `python-fints`, MT940/CAMT-Parser, Celery-Sync-Tasks und der Redis-basierten PSD2-TAN-State-Machine (inkl. Frontend-Modal für PushTAN/chipTAN/photoTAN).
  - Überweisungen (Einzel, Sammel PAIN.001, Termin) und Daueraufträge im Ausgangskorb.
  - *Self-Test (mit Mock-FinTS-Dialogen) & Doku-Update.*
- **Meilenstein 4: Externe Provider (PayPal REST, Playwright Amazon/CC Scraper, Depot-Kurse)**
  - PayPal API-Client für Transaktionsabruf.
  - Playwright-Worker-Architektur für Amazon-Bestellungen/Rechnungs-PDFs und Nicht-FinTS-Kreditkarten.
  - Depot-Bewertungs-Sync & Cashflow-Forecasting (30/60/90 Tage).
  - *Self-Test & Doku-Update.*
- **Meilenstein 5: ERPNext/Frappe Integration & 3-Stufen Reconciliation-Engine**
  - `ERPConfig`, Webhook-Endpunkte für ERPNext Sales Invoices (`ExpectedPayment`) und Sync für Purchase Invoices.
  - Implementierung der 3-Stufen Matching-Engine (1. Regex + `pg_trgm` Trigram-Similarity, 2. Skonto-Mathematik + Deductions, 3. Subset-Sum/Knapsack-Solver via `itertools.combinations` für Sammelüberweisungen).
  - Automatischer Rückschrieb (`Payment Entry`) an ERPNext API.
  - *Self-Test (inkl. Unit-Tests für Fuzzy-Match, 2%/3% Skonto und Knapsack-Sammelüberweisungen) & Doku-Update.*
- **Meilenstein 6: Aktiver Forderungseinzug (SEPA PAIN.008) & Payment Gateways (Stripe, PayPal, Wero)**
  - SEPA-Mandatsverwaltung (`CORE` & `B2B`), `PAIN.008` XML-Generator, FinTS-Lastschrifteinreichung und SMTP Pre-Notification-Task.
  - Anbindung von Stripe, PayPal Checkout und Wero (QR/Payment-Links) inkl. Webhook-Listenern und Geldtransit-Verbuchung.
  - *Self-Test & Doku-Update.*
- **Meilenstein 7: DATEV-Export, Paperless-ngx Auto-Link & Local AI Integration**
  - DATEV-EXTF/CSV-Buchungsstapel-Generator & API-Vorbereitung.
  - Paperless-ngx REST-Abgleich zur automatischen Beleg-Verknüpfung.
  - Anbindung eines lokalen LLM-Endpunkts für KI-Kategorisierung und Text-to-SQL-Finanzabfragen.
  - *Self-Test & Doku-Update.*
- **Meilenstein 8: Triage-Dashboard, Collection-UI, Alpine.js Shortcuts & Universeller CSV-Export**
  - Bau des htmx/Alpine.js Triage-Dashboards (One-Click-Approve, Vim-Style Shortcuts `J`/`K`/`Enter`/`Esc`).
  - Bau des Collection-Dashboards für SEPA-Batches und Payment-Gateways.
  - Durchgängige Implementierung des Alpine.js-gestützten CSV-Streaming-Exports für alle Bankeingänge, offenen ERP-Positionen, SEPA-Einzüge und Kontoumsätze.
  - *Self-Test & Doku-Update.*
- **Meilenstein 9: End-to-End Systemprüfung, Security-Audit & Finalisierung der Dokumentation**
  - Kompletter Durchlauf aller Test-Suiten, Prüfung auf Zero-CDN-Einhaltung, Prüfung aller Bind-Mounts, Bereinigung und Komplettierung von `README.md`, `PLAN.md`, `INTERVIEW.md` und `MANUAL.md`, finaler Git-Commit & Push.

---

**START-ANWEISUNG:**
Bestätige kurz, dass du diesen Masterplan vollständig verstanden hast, und beginne **jetzt direkt mit Phase 0**, indem du mir deine präzisen Klärungsfragen (inklusive der Abfrage des GitHub-Repository-Namens und des Deploy-Tokens für `siekenetoc`) stellst, damit wir die `INTERVIEW.md` anlegen können.

---

Dieses Bootstrap-Skript (bootstrap_openfin.sh) legt die gesamte Bind-Mount-Struktur unter ./docker-data/, die Verzeichnisse für die lokale Node.js-Asset-Pipeline sowie eine passende .gitignore an.

Ein wichtiges Detail für PostgreSQL mit Bind-Mounts ist direkt berücksichtigt: Das Verzeichnis ./docker-data/postgres bleibt komplett leer (ohne .gitkeep), da der PostgreSQL-Container beim ersten Start (initdb) sonst mit dem Fehler abbricht, dass das Datenverzeichnis nicht leer ist.

``bash
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
```


Ausführung auf dem HostSpeichere das Skript im gewünschten Projektordner (oder übergebe den Pfad als Parameter) und führe es vor dem Start des Coding Agents einmalig aus:

```bash
chmod +x bootstrap_openfin.sh
./bootstrap_openfin.sh /pfad/zu/openfin
```

Damit der PostgreSQL- und der Celery/Playwright-Container später ohne Root-Rechte-Konflikte in ./docker-data/ schreiben können, sollte der Coding Agent in der docker-compose.yml die Variablen UID und GID des Host-Users durchreichen.


---

Das Grundgerüst für docker-compose.yml und .env.example bildet exakt die Verzeichnisstruktur aus dem Bootstrap-Skript ab. Zwei kritische Details für den produktiven Linux-Betrieb sind direkt integriert: Der PostgreSQL-Container erhält Lesezugriff auf /etc/passwd und /etc/group (damit initdb beim Ausführen unter deiner Host-UID nicht mit einem Lookup-Fehler abbricht), und der Celery-Worker erhält shm_size: '2gb' sowie ipc: host, damit Headless Chromium (Playwright) beim Scrapen großer DOM-Bäume wie Amazon nicht wegen Shared-Memory-Mangel abstürzt.


Datei docker-compose.yml:

services:
  db:
    image: postgres:16-bookworm
    container_name: openfin_db
    restart: unless-stopped
    user: "${UID:-1000}:${GID:-1000}"
    env_file:
      - .env
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-openfin}
      POSTGRES_USER: ${POSTGRES_USER:-openfin_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - ./docker-data/postgres:/var/lib/postgresql/data
      - /etc/passwd:/etc/passwd:ro
      - /etc/group:/etc/group:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-openfin_user} -d ${POSTGRES_DB:-openfin}"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - openfin_net

  redis:
    image: redis:7-bookworm
    container_name: openfin_redis
    restart: unless-stopped
    user: "${UID:-1000}:${GID:-1000}"
    command: redis-server --appendonly yes --dir /data
    volumes:
      - ./docker-data/redis:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - openfin_net

  node_builder:
    image: node:22-bookworm-slim
    container_name: openfin_node
    user: "${UID:-1000}:${GID:-1000}"
    working_dir: /app
    volumes:
      - ./package.json:/app/package.json
      - ./tailwind.config.js:/app/tailwind.config.js
      - ./static:/app/static
      - ./templates:/app/templates:ro
    command: sh -c "npm install && npm run build"
    networks:
      - openfin_net

  web:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        UID: ${UID:-1000}
        GID: ${GID:-1000}
    container_name: openfin_web
    restart: unless-stopped
    user: "${UID:-1000}:${GID:-1000}"
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "${BIND_IP:-127.0.0.1}:${WEB_PORT:-8045}:8000"
    volumes:
      - ./:/app
      - ./static:/app/static
      - ./docker-data/static:/app/staticfiles
      - ./docker-data/media:/app/media
      - ./docker-data/logs/django:/app/logs/django
    command: >
      sh -c "python manage.py migrate_schemas --shared &&
             python manage.py migrate_schemas &&
             python manage.py collectstatic --noinput &&
             gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 120"
    networks:
      - openfin_net

  celery_worker:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        UID: ${UID:-1000}
        GID: ${GID:-1000}
    container_name: openfin_celery_worker
    restart: unless-stopped
    user: "${UID:-1000}:${GID:-1000}"
    ipc: host
    shm_size: "2gb"
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./:/app
      - ./docker-data/media:/app/media
      - ./docker-data/playwright_profiles:/app/playwright_profiles
      - ./docker-data/logs/celery:/app/logs/celery
      - ./docker-data/logs/playwright:/app/logs/playwright
    command: celery -A config worker -l INFO --concurrency=4
    networks:
      - openfin_net

  celery_beat:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        UID: ${UID:-1000}
        GID: ${GID:-1000}
    container_name: openfin_celery_beat
    restart: unless-stopped
    user: "${UID:-1000}:${GID:-1000}"
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./:/app
      - ./docker-data/logs/celery:/app/logs/celery
    command: celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
    networks:
      - openfin_net

networks:
  openfin_net:
    driver: bridge
    
    
Datei .env.example:

# ==============================================================================
# 1. HOST & DOCKER BERECHTIGUNGEN (Bind-Mount Ownership)
# ==============================================================================
COMPOSE_PROJECT_NAME=openfin
UID=1000
GID=1000
BIND_IP=127.0.0.1
WEB_PORT=8045

# ==============================================================================
# 2. DJANGO CORE & KRYPTOGRAFIE (Encryption at Rest)
# ==============================================================================
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=CHANGE_ME_TO_A_50_CHAR_RANDOM_STRING
# 32-Byte URL-safe Base64 Key für django-cryptography / Fernet (PINs, API-Keys)
FIELD_ENCRYPTION_KEY=CHANGE_ME_GENERATE_VIA_FERNET_GENERATE_KEY
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,.openfin.local
CSRF_TRUSTED_ORIGINS=http://localhost:8045,https://fin.deine-domain.de
TIME_ZONE=Europe/Berlin
LANGUAGE_CODE=de-de

# ==============================================================================
# 3. POSTGRESQL 16 (django-tenants + pg_trgm) & REDIS 7
# ==============================================================================
POSTGRES_DB=openfin
POSTGRES_USER=openfin_user
POSTGRES_PASSWORD=CHANGE_ME_STRONG_DB_PASSWORD
POSTGRES_HOST=db
POSTGRES_PORT=5432

REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# ==============================================================================
# 4. FINTS / HBCI BANKING ENGINE
# ==============================================================================
# Offizielle FinTS-Produktregistrierungsnummer (von der Deutschen Kreditwirtschaft)
FINTS_PRODUCT_ID=CHANGE_ME_FINTS_PRODUCT_ID
FINTS_TAN_STATE_TTL_SECONDS=900

# ==============================================================================
# 5. AKTIVER FORDERUNGSEINZUG (SEPA PAIN.008) & PAYMENT GATEWAYS (DEFAULT/FALLBACK)
# Hinweis: Mandantenspezifische Keys werden verschlüsselt im Tenant-Schema gespeichert.
# ==============================================================================
DEFAULT_SEPA_CREDITOR_ID=DE98ZZZ09999999999
SEPA_PRENOTIFICATION_DAYS=14

STRIPE_WEBHOOK_TOLERANCE_SECONDS=300
PAYPAL_MODE=live
WERO_API_BASE_URL=https://api.wero-wallet.eu/v1

# ==============================================================================
# 6. ENTERPRISE INTEGRATIONEN (ERPNext, DATEV, Paperless-ngx, Local AI)
# ==============================================================================
# Paperless-ngx Beleg-Abgleich
PAPERLESS_API_URL=http://192.168.178.10:8000/api
PAPERLESS_API_TOKEN=CHANGE_ME_PAPERLESS_TOKEN

# Lokale KI-Inferenz (vLLM / LiteLLM / Ollama - OpenAI-kompatibel)
LOCAL_LLM_BASE_URL=http://192.168.178.20:4000/v1
LOCAL_LLM_API_KEY=sk-local-llm-key
LOCAL_LLM_MODEL=qwen-2.5-coder-32b

# ==============================================================================
# 7. SMTP MAIL-VERSAND (für SEPA Pre-Notifications & TAN-Alerts)
# ==============================================================================
EMAIL_HOST=smtp.dein-mailserver.de
EMAIL_PORT=587
EMAIL_HOST_USER=billing@deine-domain.de
EMAIL_HOST_PASSWORD=CHANGE_ME_SMTP_PASSWORD
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=Buchhaltung <billing@deine-domain.de>


Schnelle Generierung der beiden Master-Keys auf deinem Linux-Host

Bevor du die .env.example nach .env kopierst, kannst du mit diesem Einzeiler direkt valide Schlüssel für DJANGO_SECRET_KEY und FIELD_ENCRYPTION_KEY erzeugen:

```bash
python3 -c "import secrets, base64; print('DJANGO_SECRET_KEY=' + secrets.token_urlsafe(50)); print('FIELD_ENCRYPTION_KEY=' + base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

---


Das Dockerfile nutzt python:3.12-slim-bookworm als Basis und löst einen klassischen Stolperstein beim Einsatz von Playwright in Non-Root-Containern: Durch die Umgebungsvariable PLAYWRIGHT_BROWSERS_PATH=/ms-playwright wird Headless Chromium nicht im root-Home-Verzeichnis versteckt, sondern zentral installiert und sauber an die UID/GID deines Host-Users übergeben.


Datei Dockerfile:

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
    # PostgreSQL Client & Header (für psycopg / django-tenants)
    libpq-dev \
    postgresql-client \
    # XML/XSLT & Crypto Libraries (zwingend für python-fints, sepaxml, CAMT/PAIN-Parser)
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libffi-dev \
    libssl-dev \
    # Bildverarbeitung für CMS-Uploads & QR-Codes
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

---

Basis-requirements.txt Datei:

Damit das Dockerfile sofort beim ersten docker compose build fehlerfrei durchläuft, findest du hier die exakt abgestimmte requirements.txt mit allen Paketen für Multi-Tenancy, FinTS, SEPA-XML, Playwright, Verschlüsselung und die Payment-Gateways:
Plaintext

# --- Core & Multi-Tenancy ---
Django>=5.1,<5.2
django-tenants>=3.7.0
djangorestframework>=3.15.2
drf-spectacular>=0.27.2
django-environ>=0.11.2
django-cors-headers>=4.4.0
django-filter>=24.3
gunicorn>=23.0.0

# --- Database & Redis ---
psycopg[binary]>=3.2.1
redis>=5.0.8
hiredis>=3.0.0

# --- Async Workers (Celery) ---
celery>=5.4.0
django-celery-beat>=2.7.0
django-celery-results>=2.5.1

# --- Security & Encryption at Rest ---
cryptography>=43.0.1
django-cryptography-django5>=1.2

# --- Banking (FinTS / HBCI, SEPA PAIN.001 & PAIN.008, MT940) ---
fints>=4.0.0
sepaxml>=2.6.0
mt-940>=4.30.0
Schwifty>=2024.8.0
lxml>=5.3.0
defusedxml>=0.7.1

# --- Payment Gateways & External Providers ---
stripe>=10.10.0
paypalrestsdk>=1.13.3
requests>=2.32.3
httpx>=0.27.2
yfinance>=0.2.43

# --- Headless Scraping (Amazon & Non-FinTS Kreditkarten) ---
playwright>=1.47.0
beautifulsoup4>=4.12.3

# --- Local AI / LLM Client & Document Handling ---
openai>=1.45.0
Pillow>=10.4.0
pypdf>=4.3.1
qrcode[pil]>=7.4.2

# --- Testing & Quality (für das autonome Self-Testing des Agents) ---
pytest>=8.3.3
pytest-django>=4.9.0
pytest-cov>=5.0.0
factory-boy>=3.3.1

Hinweis zu django-cryptography: Da das ursprüngliche Paket unter Django 5.x Kompatibilitätsprobleme mit base.Field hatte, ist hier direkt der gepflegte Fork django-cryptography-django5 (samt nativem cryptography/Fernet-Paket) eingetragen, damit der Coding Agent beim ersten Migrationslauf nicht in Deprecated-Imports läuft.


---

Die Asset-Pipeline kombiniert Tailwind CSS CLI für das Styling und esbuild für das hochperformante Bundling von JavaScript (htmx, Alpine.js, lokaler RTF-Editor Quill) sowie die Bereitstellung der lokalen Webfonts (Inter und JetBrains Mono). Damit der node_builder-Container beim ersten Start ohne Fehlermeldung durchläuft, sind neben der package.json und tailwind.config.js auch die beiden Einstiegsdateien (input.css und app.js) definiert.
1. package.json

Diese Konfiguration installiert alle benötigten Frontend-Pakete lokal und bündelt sie nach ./static/dist/, sodass keinerlei externe Netzwerkverbindungen im Browser entstehen.
JSON

{
  "name": "openfin-frontend",
  "version": "1.0.0",
  "private": true,
  "description": "Zero-CDN Asset Pipeline for OpenFin (Tailwind, Alpine.js, htmx, Quill RTF, Local Fonts)",
  "scripts": {
    "copy:fonts": "mkdir -p ./static/dist/fonts && cp ./node_modules/@fontsource/inter/files/inter-latin-400-normal.woff2 ./node_modules/@fontsource/inter/files/inter-latin-600-normal.woff2 ./node_modules/@fontsource/inter/files/inter-latin-700-normal.woff2 ./node_modules/@fontsource/jetbrains-mono/files/jetbrains-mono-latin-400-normal.woff2 ./node_modules/@fontsource/jetbrains-mono/files/jetbrains-mono-latin-600-normal.woff2 ./static/dist/fonts/",
    "copy:quill-css": "mkdir -p ./static/dist/css && cp ./node_modules/quill/dist/quill.snow.css ./static/dist/css/quill.snow.css",
    "build:css": "npx tailwindcss -i ./static/src/css/input.css -o ./static/dist/css/app.min.css --minify",
    "build:js": "npx esbuild ./static/src/js/app.js --bundle --minify --sourcemap --target=es2020 --outfile=./static/dist/js/app.min.js",
    "build": "npm run copy:fonts && npm run copy:quill-css && npm run build:css && npm run build:js",
    "watch:css": "npx tailwindcss -i ./static/src/css/input.css -o ./static/dist/css/app.min.css --watch",
    "watch:js": "npx esbuild ./static/src/js/app.js --bundle --sourcemap --target=es2020 --outfile=./static/dist/js/app.min.js --watch"
  },
  "dependencies": {
    "@alpinejs/focus": "^3.14.3",
    "@alpinejs/persist": "^3.14.3",
    "@fontsource/inter": "^5.1.0",
    "@fontsource/jetbrains-mono": "^5.1.0",
    "alpinejs": "^3.14.3",
    "htmx.org": "^2.0.3",
    "quill": "^2.0.2"
  },
  "devDependencies": {
    "@tailwindcss/forms": "^0.5.9",
    "@tailwindcss/typography": "^0.5.15",
    "esbuild": "^0.24.0",
    "tailwindcss": "^3.4.14"
  }
}

2. tailwind.config.js

Die Farbpalette enthält bereits den Zwischenwert gray-750 (aus dem Triage-Dashboard) und bindet die lokalen Schriftarten Inter (UI) sowie JetBrains Mono (IBANs, Beträge, Verwendungszwecke) ein.
JavaScript

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './templates/**/*.html',
    './**/templates/**/*.html',
    './static/src/js/**/*.js',
    './**/forms.py'
  ],
  theme: {
    extend: {
      colors: {
        gray: {
          750: '#262f3f',
          850: '#161d2a',
          950: '#0b0f17'
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace']
      }
    }
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography')
  ]
};

3. CSS-Einstiegspunkt: ./static/src/css/input.css

Hier werden die lokal kopierten .woff2-Schriften registriert und die Sichtbarkeitsregeln für htmx-indicator (Lade-Spinner beim One-Click-Approve) sowie [x-cloak] (Verhindern von Alpine.js-Flackern beim Seitenaufbau) hinterlegt.
CSS

@tailwind base;
@tailwind components;
@tailwind utilities;

/* Lokale Fonts (Zero-CDN) */
@font-face {
  font-family: 'Inter';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url('../fonts/inter-latin-400-normal.woff2') format('woff2');
}
@font-face {
  font-family: 'Inter';
  font-style: normal;
  font-weight: 600;
  font-display: swap;
  src: url('../fonts/inter-latin-600-normal.woff2') format('woff2');
}
@font-face {
  font-family: 'Inter';
  font-style: normal;
  font-weight: 700;
  font-display: swap;
  src: url('../fonts/inter-latin-700-normal.woff2') format('woff2');
}
@font-face {
  font-family: 'JetBrains Mono';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url('../fonts/jetbrains-mono-latin-400-normal.woff2') format('woff2');
}
@font-face {
  font-family: 'JetBrains Mono';
  font-style: normal;
  font-weight: 600;
  font-display: swap;
  src: url('../fonts/jetbrains-mono-latin-600-normal.woff2') format('woff2');
}

/* Alpine.js Cloak & htmx Loading Indicators */
[x-cloak] {
  display: none !important;
}

.htmx-indicator {
  display: none;
}
.htmx-request .htmx-indicator,
.htmx-request.htmx-indicator {
  display: inline-block;
}

4. JS-Einstiegspunkt: ./static/src/js/app.js

Diese Datei bündelt htmx, Alpine.js (inklusive @alpinejs/persist für gespeicherte Tabellenfilter und @alpinejs/focus für Modals) sowie den lokalen Quill RTF-Editor für die CMS-Einzelseiten und injiziert automatisch das Django-CSRF-Token in jeden hx-post Request.   
JavaScript

import htmx from 'htmx.org';
import Alpine from 'alpinejs';
import persist from '@alpinejs/persist';
import focus from '@alpinejs/focus';
import Quill from 'quill';

// 1. Globale Verfügbarkeit für Django-Templates herstellen
window.htmx = htmx;
window.Quill = Quill;
window.Alpine = Alpine;

// 2. Alpine.js Plugins registrieren
Alpine.plugin(persist);
Alpine.plugin(focus);

// 3. Automatisches Django CSRF-Token Handling für alle htmx Requests
document.body.addEventListener('htmx:configRequest', (event) => {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
  if (csrfToken) {
    event.detail.headers['X-CSRFToken'] = csrfToken;
  }
});

// 4. Hilfsfunktion zur Initialisierung des lokalen RTF-Editors (CMS-Seiten mit Bild-Upload)
window.initCmsEditor = function (editorSelector, hiddenInputSelector, uploadUrl) {
  const container = document.querySelector(editorSelector);
  const hiddenInput = document.querySelector(hiddenInputSelector);
  if (!container || !hiddenInput) return;

  const quill = new Quill(container, {
    theme: 'snow',
    modules: {
      toolbar: {
        container: [
          [{ header: [1, 2, 3, false] }],
          ['bold', 'italic', 'underline', 'strike'],
          [{ list: 'ordered' }, { list: 'bullet' }],
          ['link', 'image', 'blockquote', 'code-block'],
          ['clean']
        ],
        handlers: {
          image: function () {
            const input = document.createElement('input');
            input.setAttribute('type', 'file');
            input.setAttribute('accept', 'image/*');
            input.click();

            input.onchange = async () => {
              const file = input.files[0];
              if (!file) return;

              const formData = new FormData();
              formData.append('image', file);

              const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
              const response = await fetch(uploadUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
                body: formData
              });

              if (response.ok) {
                const data = await response.json();
                const range = quill.getSelection(true);
                quill.insertEmbed(range.index, 'image', data.url);
              }
            };
          }
        }
      }
    }
  });

  quill.on('text-change', () => {
    hiddenInput.value = quill.root.innerHTML;
  });
};

Alpine.start();

Damit hast du alle Infrastruktur-Dateien (bootstrap_openfin.sh, docker-compose.yml, .env.example, Dockerfile, requirements.txt, package.json, tailwind.config.js und die Asset-Entrypoints) komplett zusammen, um das Projekt ohne Reibungsverluste vom Coding Agent aufbauen zu lassen.

---



    




