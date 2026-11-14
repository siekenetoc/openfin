from django.db import migrations

PAGES = [
    (
        "AGB",
        "agb",
        "Allgemeine Geschäftsbedingungen",
        """
        <h2>1. Geltungsbereich</h2>
        <p>Diese Allgemeinen Geschäftsbedingungen gelten für alle Verträge zwischen der OpenFin Demo GmbH und ihren Kunden über die Nutzung der OpenFin-Finanzplattform.</p>
        <h2>2. Leistungsumfang</h2>
        <p>Die Plattform stellt Funktionen für Banking, Zahlungsverkehr, Forderungseinzug, ERP-Reconciliation und Dokumentenverwaltung bereit. Der konkrete Leistungsumfang ergibt sich aus dem jeweiligen Vertrag.</p>
        <h2>3. Verfügbarkeit</h2>
        <p>Die Plattform wird selbst gehostet betrieben. Wartungsfenster werden nach Möglichkeit vorab angekündigt.</p>
        <h2>4. Haftung</h2>
        <p>Die Haftung richtet sich nach den gesetzlichen Bestimmungen. Diese Mustertexte sind vor dem Produktivbetrieb juristisch zu prüfen.</p>
        """,
    ),
    (
        "Impressum",
        "impressum",
        "Impressum",
        """
        <h2>Angaben gemäß § 5 DDG</h2>
        <p>OpenFin Demo GmbH<br>Musterstraße 1<br>12345 Musterstadt<br>Deutschland</p>
        <p>E-Mail: kontakt@openfin.example<br>Telefon: +49 123 456789</p>
        <p>Geschäftsführung: Max Mustermann<br>Handelsregister: Amtsgericht Musterstadt, HRB 12345<br>USt-IdNr.: DE123456789</p>
        <p>Verantwortlich für den Inhalt: Max Mustermann, Adresse wie oben.</p>
        """,
    ),
    (
        "Datenschutzerklärung",
        "datenschutz",
        "Datenschutzerklärung",
        """
        <h2>1. Verantwortlicher</h2>
        <p>OpenFin Demo GmbH, Musterstraße 1, 12345 Musterstadt, kontakt@openfin.example.</p>
        <h2>2. Verarbeitete Daten</h2>
        <p>Die Plattform verarbeitet Stammdaten, Bankumsätze, Rechnungsdaten und Zugangsdaten, soweit dies für die Vertragserfüllung erforderlich ist. Sensible Zugangsdaten werden verschlüsselt gespeichert.</p>
        <h2>3. Rechtsgrundlagen</h2>
        <p>Art. 6 Abs. 1 lit. b DSGVO (Vertrag), lit. c DSGVO (gesetzliche Pflichten) und lit. f DSGVO (berechtigtes Interesse an sicherem Betrieb).</p>
        <h2>4. Speicherdauer</h2>
        <p>Daten werden nur so lange gespeichert, wie dies für die Zwecke und gesetzliche Aufbewahrungsfristen erforderlich ist.</p>
        <h2>5. Rechte</h2>
        <p>Betroffene Personen haben das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung, Datenübertragbarkeit und Widerspruch.</p>
        """,
    ),
    (
        "Partner",
        "partner",
        "Partner &amp; Schnittstellen",
        """
        <h2>Integrierte Systeme</h2>
        <p>OpenFin arbeitet mit Banken über FinTS/HBCI, mit ERPNext/Frappe für die Buchhaltung, mit DATEV für den Buchungsdatenaustausch, mit Paperless-ngx für die Belegverwaltung sowie mit Stripe, PayPal und Wero für den Zahlungseinzug zusammen.</p>
        <p>Alle Schnittstellen sind mandantenspezifisch konfigurierbar. Zugangsdaten werden verschlüsselt gespeichert.</p>
        """,
    ),
    (
        "Disclaimer",
        "disclaimer",
        "Hinweise &amp; Disclaimer",
        """
        <h2>Keine Anlage- oder Steuerberatung</h2>
        <p>Die dargestellten Auswertungen, Prognosen und KI-Vorschläge dienen ausschließlich Informationszwecken. Sie ersetzen keine rechtliche, steuerliche oder finanzielle Beratung.</p>
        <h2>Datenqualität</h2>
        <p>Automatische Abgleiche können Fehler enthalten. Verbindliche Buchungen sind vor der Freigabe zu prüfen. Die Demo-Seite verwendet Mock-Daten und stellt keine echten Bankverbindungen her.</p>
        """,
    ),
]


def seed_pages(apps, schema_editor):
    ContentPage = apps.get_model("cms", "ContentPage")
    for title, slug, meta_title, content in PAGES:
        ContentPage.objects.update_or_create(
            tenant=None,
            slug=slug,
            defaults={
                "title": title,
                "content_html": content,
                "meta_description": f"{meta_title} – OpenFin",
                "is_published": True,
                "show_in_footer": True,
            },
        )


def unseed_pages(apps, schema_editor):
    ContentPage = apps.get_model("cms", "ContentPage")
    ContentPage.objects.filter(tenant=None, slug__in=[slug for _, slug, _, _ in PAGES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(seed_pages, unseed_pages),
    ]
