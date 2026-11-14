from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8045",
    "http://127.0.0.1:8045",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
