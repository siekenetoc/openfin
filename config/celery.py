import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

app = Celery("openfin")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "sync-all-bank-accounts": {
        "task": "apps.banking.tasks.sync_all_accounts",
        "schedule": 900.0,
    },
    "sepa-prenotifications": {
        "task": "apps.billing.tasks.send_due_prenotifications",
        "schedule": 3600.0,
    },
    "refresh-depot-prices": {
        "task": "apps.providers.tasks.refresh_all_depots",
        "schedule": 3600.0,
    },
    "paperless-autolink": {
        "task": "apps.integrations.tasks.autolink_paperless_documents",
        "schedule": 1800.0,
    },
}
