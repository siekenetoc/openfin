from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1", ".openfin.local"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
    FINTS_USE_MOCK=(bool, True),
    FINTS_TAN_STATE_TTL_SECONDS=(int, 900),
    SEPA_PRENOTIFICATION_DAYS=(int, 14),
    STRIPE_WEBHOOK_TOLERANCE_SECONDS=(int, 300),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-development-key-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", ".openfin.local"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ---------------------------------------------------------------------------
# Multi-Tenancy
# ---------------------------------------------------------------------------
SHARED_APPS = [
    "django_tenants",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "drf_spectacular",
    "django_filters",
    "corsheaders",
    "django_celery_beat",
    "django_celery_results",
    "apps.core",
    "apps.cms",
]

TENANT_APPS = [
    "apps.banking",
    "apps.providers",
    "apps.erp",
    "apps.billing",
    "apps.integrations",
    "apps.dashboard",
]

INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]

MIDDLEWARE = [
    "django_tenants.middleware.main.TenantMainMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.PublicSchemaMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.navigation",
                "apps.cms.context_processors.footer_pages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": env("POSTGRES_DB", default="openfin"),
        "USER": env("POSTGRES_USER", default="openfin_user"),
        "PASSWORD": env("POSTGRES_PASSWORD", default="openfin"),
        "HOST": env("POSTGRES_HOST", default="db"),
        "PORT": env("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": 60,
    }
}
DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

TENANT_MODEL = "core.Tenant"
TENANT_DOMAIN_MODEL = "core.Domain"
PUBLIC_SCHEMA_NAME = "public"
SHOW_PUBLIC_IF_NO_TENANT_FOUND = False

AUTH_USER_MODEL = "core.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

LANGUAGE_CODE = "de-de"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "docker-data" / "static"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "docker-data" / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Encryption at rest
# ---------------------------------------------------------------------------
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", default="")

# ---------------------------------------------------------------------------
# REST Framework / OpenAPI
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "OpenFin API",
    "DESCRIPTION": "Multi-Tenant Banking, PSP & ERP-Reconciliation Hub",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

# ---------------------------------------------------------------------------
# Celery / Redis
# ---------------------------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://redis:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://redis:6379/2")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 900
CELERY_TASK_SOFT_TIME_LIMIT = 840
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# ---------------------------------------------------------------------------
# FinTS / SEPA / Payment providers
# ---------------------------------------------------------------------------
FINTS_PRODUCT_ID = env("FINTS_PRODUCT_ID", default="CHANGE_ME_FINTS_PRODUCT_ID")
FINTS_USE_MOCK = env.bool("FINTS_USE_MOCK", default=True)
FINTS_TAN_STATE_TTL_SECONDS = env.int("FINTS_TAN_STATE_TTL_SECONDS", default=900)

DEFAULT_SEPA_CREDITOR_ID = env("DEFAULT_SEPA_CREDITOR_ID", default="DE98ZZZ09999999999")
DEFAULT_SEPA_CREDITOR_NAME = env("DEFAULT_SEPA_CREDITOR_NAME", default="OpenFin Demo GmbH")
SEPA_PRENOTIFICATION_DAYS = env.int("SEPA_PRENOTIFICATION_DAYS", default=14)

STRIPE_WEBHOOK_TOLERANCE_SECONDS = env.int("STRIPE_WEBHOOK_TOLERANCE_SECONDS", default=300)
PAYPAL_MODE = env("PAYPAL_MODE", default="sandbox")
PAYPAL_CLIENT_ID = env("PAYPAL_CLIENT_ID", default="")
PAYPAL_CLIENT_SECRET = env("PAYPAL_CLIENT_SECRET", default="")
WERO_API_BASE_URL = env("WERO_API_BASE_URL", default="https://api.wero-wallet.eu/v1")
WERO_API_KEY = env("WERO_API_KEY", default="")

# ---------------------------------------------------------------------------
# Integrations
# ---------------------------------------------------------------------------
ERPNEXT_BASE_URL = env("ERPNEXT_BASE_URL", default="http://erpnext.local:8080")
ERPNEXT_API_KEY = env("ERPNEXT_API_KEY", default="")
ERPNEXT_API_SECRET = env("ERPNEXT_API_SECRET", default="")
ERPNEXT_WEBHOOK_SECRET = env("ERPNEXT_WEBHOOK_SECRET", default="")

PAPERLESS_API_URL = env("PAPERLESS_API_URL", default="http://192.168.178.10:8000/api")
PAPERLESS_API_TOKEN = env("PAPERLESS_API_TOKEN", default="")
PLAYWRIGHT_PROFILES_DIR = BASE_DIR / "docker-data" / "playwright_profiles"

STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
PAYPAL_WEBHOOK_SECRET = env("PAYPAL_WEBHOOK_SECRET", default="")
WERO_WEBHOOK_SECRET = env("WERO_WEBHOOK_SECRET", default="")

LOCAL_LLM_BASE_URL = env("LOCAL_LLM_BASE_URL", default="http://192.168.178.20:4000/v1")
LOCAL_LLM_API_KEY = env("LOCAL_LLM_API_KEY", default="")
LOCAL_LLM_MODEL = env("LOCAL_LLM_MODEL", default="qwen-2.5-coder-32b")

# ---------------------------------------------------------------------------
# E-Mail
# ---------------------------------------------------------------------------
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Buchhaltung <billing@example.invalid>")
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "openfin": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
