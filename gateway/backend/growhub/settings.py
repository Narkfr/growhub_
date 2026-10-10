"""Django settings for the GrowHub gateway (v2).

Configuration is environment driven: values are read from the process
environment, with ``gateway/.env`` loaded first when present. Defaults target a
local development machine and must be overridden in production.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # gateway/backend
GATEWAY_DIR = BASE_DIR.parent  # gateway/
REPO_DIR = GATEWAY_DIR.parent

load_dotenv(GATEWAY_DIR / ".env")


def env_bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,growhub.local")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "accounts",
    "devices",
    "telemetry",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "growhub.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "growhub.wsgi.application"
ASGI_APPLICATION = "growhub.asgi.application"

if os.environ.get("DJANGO_DB_ENGINE", "postgres") == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("DJANGO_SQLITE_PATH", BASE_DIR / "db.sqlite3"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "growhub"),
            "USER": os.environ.get("POSTGRES_USER", "growhub"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        )
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_FILTER_BACKENDS": [],
}

# --- GrowHub domain settings -------------------------------------------------

MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER", "growhub_api")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "")

GROWHUB = {
    # Pairing claim codes live this long after provisioning.
    "PAIRING_CODE_TTL_HOURS": int(os.environ.get("GROWHUB_PAIRING_TTL_HOURS", "24")),
    # Failed redemptions allowed per code before it is locked.
    "PAIRING_MAX_ATTEMPTS": int(os.environ.get("GROWHUB_PAIRING_MAX_ATTEMPTS", "5")),
    # Hardware device id prefix, e.g. ghb-3f2a91.
    "DEVICE_ID_PREFIX": os.environ.get("GROWHUB_DEVICE_ID_PREFIX", "ghb-"),
    # Mosquitto administration (password_file / acl_file live in the broker config dir).
    "MOSQUITTO_CONFIG_DIR": os.environ.get(
        "GROWHUB_MOSQUITTO_CONFIG_DIR", str(GATEWAY_DIR / "mosquitto" / "config")
    ),
    "MOSQUITTO_PASSWORD_FILE": os.environ.get(
        "GROWHUB_MOSQUITTO_PASSWORD_FILE", "password_file"
    ),
    "MOSQUITTO_ACL_FILE": os.environ.get("GROWHUB_MOSQUITTO_ACL_FILE", "acl_file"),
    # Reload hook: Mosquitto re-reads its files on SIGHUP. Empty = no reload.
    "MQTT_RELOAD_COMMAND": os.environ.get("GROWHUB_MQTT_RELOAD_COMMAND", ""),
    # How often the SSE stream re-reads the database (seconds).
    "LIVE_POLL_SECONDS": float(os.environ.get("GROWHUB_LIVE_POLL_SECONDS", "2")),
    # Adresse du broker telle que le *boîtier* doit la voir. Dans un conteneur,
    # MQTT_BROKER est le nom du service Compose : le Bourgeon, lui, est sur le
    # réseau et a besoin de l'IP de la passerelle. Ces deux valeurs partent dans
    # le secrets.py du boîtier et dans le message d'appairage.
    "DEVICE_BROKER": os.environ.get("GROWHUB_DEVICE_BROKER", MQTT_BROKER),
    "DEVICE_BROKER_PORT": int(
        os.environ.get("GROWHUB_DEVICE_BROKER_PORT", str(MQTT_PORT))
    ),
    # A device with no message for this long is shown as offline.
    "DEVICE_STALE_AFTER_SECONDS": int(
        os.environ.get("GROWHUB_DEVICE_STALE_AFTER", "300")
    ),
    # Raw telemetry retention; older rows are rolled up then purged.
    "TELEMETRY_RETENTION_MONTHS": int(
        os.environ.get("GROWHUB_TELEMETRY_RETENTION_MONTHS", "24")
    ),
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
    },
}
