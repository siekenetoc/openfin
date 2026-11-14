import os

from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ["*"]
FINTS_USE_MOCK = True
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

DATABASES["default"]["HOST"] = os.environ.get("TEST_DB_HOST", "127.0.0.1")
DATABASES["default"]["PORT"] = os.environ.get("TEST_DB_PORT", "5432")
DATABASES["default"]["NAME"] = os.environ.get("TEST_DB_NAME", os.environ.get("POSTGRES_DB", "openfin"))
DATABASES["default"]["CONN_MAX_AGE"] = 0

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "openfin-test",
    }
}

LOGGING["root"]["level"] = "WARNING"
LOGGING["loggers"]["django"]["level"] = "WARNING"
LOGGING["loggers"]["openfin"]["level"] = "WARNING"
