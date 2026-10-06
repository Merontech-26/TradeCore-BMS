"""
Django settings for TradeCore.

Production-safe configuration is controlled by environment variables.
The application architecture, URLs, models and feature flow are unchanged.
"""

import os
from pathlib import Path
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name, default=None):
    value = os.environ.get(name)
    if value is None:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_int(name, default):
    value = os.environ.get(name)
    if value is None or not str(value).strip():
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(
            f"{name} must be an integer."
        ) from exc


def _validate_origins(name, origins):
    invalid = []
    for origin in origins:
        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            invalid.append(origin)
    if invalid:
        raise ImproperlyConfigured(
            f"{name} contains invalid origin(s): {', '.join(invalid)}"
        )
    return origins


# -----------------------------------------------------------------------------
# Core security / environment
# -----------------------------------------------------------------------------
DEBUG = _env_bool("DEBUG", default=False)

SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-local-development-only"
    else:
        raise ImproperlyConfigured(
            "SECRET_KEY must be set in the environment when DEBUG=False."
        )

ALLOWED_HOSTS = _env_list(
    "ALLOWED_HOSTS",
    default=["tradecore.merontech.co.tz", ".railway.app", "localhost", "127.0.0.1", "*"],
)

# CSRF Inazuia fomu zako zisifanye kazi kama domain hazipo hapa
# Badala ya kutumia env tu, tunazi-hardcode domain zetu rasmi
CSRF_TRUSTED_ORIGINS = _validate_origins(
    "CSRF_TRUSTED_ORIGINS",
    _env_list("CSRF_TRUSTED_ORIGINS", default=["https://tradecore.merontech.co.tz", "https://*.railway.app"]),
)


# -----------------------------------------------------------------------------
# Application definition
# -----------------------------------------------------------------------------
INSTALLED_APPS = [
    "pos_app",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves collected static assets directly from the Django app.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "pos_app.middleware.MtambuaOnlineMiddleware",
    "pos_app.trial_middleware.TrialAndSubscriptionMiddleware",
]

ROOT_URLCONF = "tradecore.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
            ],
        },
    },
]

WSGI_APPLICATION = "tradecore.wsgi.application"


# -----------------------------------------------------------------------------
# Production security
# -----------------------------------------------------------------------------
if DEBUG:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
else:
    SECURE_SSL_REDIRECT = True
    # Hii inasaidia Railway kujua kama connection ni HTTPS
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = False
    CSRF_COOKIE_SAMESITE = "Lax"

    # Hizi SECURE_HSTS zinaweza kukataa kufunguka kama Railway haijaseti SSL vizuri. 
    # Tunazifunga (comment) kwa sasa, mpaka utakapo-link domain kamili ya Cloudflare au CPanel.
    # SECURE_HSTS_SECONDS = 31536000
    # SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # SECURE_HSTS_PRELOAD = True

    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    X_FRAME_OPTIONS = "DENY"


# -----------------------------------------------------------------------------
# Database
# -----------------------------------------------------------------------------
# Keep SQLite as the local/default database so the current application
# architecture remains unchanged. Railway can switch to PostgreSQL simply by
# providing DATABASE_URL and installing a PostgreSQL driver in requirements.
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL:
    parsed = urlparse(DATABASE_URL)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured(
            "DATABASE_URL must use postgres:// or postgresql:// for TradeCore."
        )

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": (parsed.path or "").lstrip("/") or None,
            "USER": parsed.username or "",
            "PASSWORD": parsed.password or "",
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or 5432),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# -----------------------------------------------------------------------------
# Password validation
# -----------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# -----------------------------------------------------------------------------
# Internationalization
# -----------------------------------------------------------------------------
LANGUAGE_CODE = "sw"

LANGUAGES = [
    ("sw", "Kiswahili"),
    ("en", "English"),
    ("fr", "Français"),
    ("es", "Español"),
    ("ar", "العربية"),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

LANGUAGE_COOKIE_NAME = "django_language"
LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 365
LANGUAGE_COOKIE_PATH = "/"
LANGUAGE_COOKIE_SAMESITE = "Lax"

TIME_ZONE = "Africa/Dar_es_Salaam"
USE_I18N = True
USE_TZ = True


# -----------------------------------------------------------------------------
# Static / media files
# -----------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Django 6 storage configuration. WhiteNoise handles static files only;
# uploaded media remains under MEDIA_ROOT and is not exposed as static content.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}



# -----------------------------------------------------------------------------
# WhatsApp / Momo Business integration
# -----------------------------------------------------------------------------
MOMO_API_BASE_URL = os.environ.get(
    "MOMO_API_BASE_URL", "https://business.momo.tz/api/v3"
).strip().rstrip("/")
MOMO_API_TOKEN = os.environ.get("MOMO_API_TOKEN", "").strip()
MOMO_WHATSAPP_SENDER_ID = os.environ.get("MOMO_WHATSAPP_SENDER_ID", "").strip()
MOMO_DAILY_REPORT_TEMPLATE_NAME = os.environ.get(
    "MOMO_DAILY_REPORT_TEMPLATE_NAME", "tradecore_daily_business_report"
).strip()
MOMO_DAILY_REPORT_TEMPLATE_LANGUAGE = os.environ.get(
    "MOMO_DAILY_REPORT_TEMPLATE_LANGUAGE", "sw"
).strip()

# Public daily-report link lifetime (seconds). 24 hours by default.
TRADECORE_REPORT_TOKEN_MAX_AGE = _env_int(
    "TRADECORE_REPORT_TOKEN_MAX_AGE",
    86400,
)
if TRADECORE_REPORT_TOKEN_MAX_AGE <= 0:
    raise ImproperlyConfigured(
        "TRADECORE_REPORT_TOKEN_MAX_AGE must be greater than 0."
    )


# -----------------------------------------------------------------------------
# Email
# -----------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "mail.merontech.co.tz")
EMAIL_PORT = _env_int("EMAIL_PORT", 465)
EMAIL_USE_SSL = _env_bool("EMAIL_USE_SSL", default=True)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "info@merontech.co.tz")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = _env_int("EMAIL_TIMEOUT", 20)
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    f"TradeCore BMS <{EMAIL_HOST_USER}>",
)


# -----------------------------------------------------------------------------
# Defaults
# -----------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"