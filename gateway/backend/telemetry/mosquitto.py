"""Mosquitto administration: password hashing, ACL generation, reload.

The broker is the only component that needs a usable password, and it only ever
stores the PBKDF2 hash. The format here was verified byte for byte against
``mosquitto_passwd`` 2.0.21: ``$7$101$<salt b64>$<hash b64>``, 12-byte salt,
101 iterations, PBKDF2-HMAC-SHA512, 64-byte key.

Access control relies on Mosquitto ``pattern`` rules with ``%u`` (the username,
which *is* the device id), so a paired device can only touch its own topic
prefix without any per-device ACL entry. Only the short-lived bootstrap users
need explicit entries.
"""

import base64
import hashlib
import logging
import os
import secrets
import shlex
import subprocess
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

SALT_BYTES = 12
KEY_BYTES = 64
ITERATIONS = 101
PASSWORD_FILE_MODE = 0o600
ACL_FILE_MODE = 0o640
GENERATED_HEADER = (
    "# Fichier généré par gateway/backend/telemetry/mosquitto.py — ne pas éditer."
)


def hash_password(password, salt=None, iterations=ITERATIONS):
    """Return the Mosquitto password-file hash of ``password``."""
    salt = salt or secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha512", password.encode(), salt, iterations, dklen=KEY_BYTES
    )
    salt_b64 = base64.b64encode(salt).decode()
    digest_b64 = base64.b64encode(digest).decode()
    return f"$7${iterations}${salt_b64}${digest_b64}"


def generate_password():
    return secrets.token_urlsafe(24)


def parse_password_file(text):
    """``{username: hash}`` from a Mosquitto password file (blank lines ignored)."""
    entries = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        username, _, password_hash = line.partition(":")
        if username and password_hash:
            entries[username] = password_hash
    return entries


def render_password_file(entries):
    lines = [GENERATED_HEADER]
    lines += [
        f"{username}:{password_hash}"
        for username, password_hash in sorted(entries.items())
    ]
    return "\n".join(lines) + "\n"


def bootstrap_username(device_id):
    return f"boot-{device_id}"


def render_acl(service_user, bootstrap_device_ids=()):
    """Full ACL file: service account, per-device patterns, bootstrap accounts.

    ``pattern`` entries apply to every user, with ``%u`` replaced by the
    username. Since a device's broker username is its ``device_id``, one pair of
    patterns covers every device — past, present and future.
    """
    lines = [
        GENERATED_HEADER,
        "",
        "# Compte de service : lit tout, commande tout, gère le provisioning.",
        f"user {service_user}",
        "topic read growhub/v1/+/info",
        "topic read growhub/v1/+/telemetry",
        "topic read growhub/v1/+/state",
        "topic read growhub/v1/+/status",
        "topic read growhub/v1/+/ack",
        "topic write growhub/v1/+/cmd/#",
        "topic readwrite growhub/v1/provision/#",
        "",
        "# Appareil appairé : uniquement son propre préfixe (username == device_id).",
        "pattern write growhub/v1/%u/info",
        "pattern write growhub/v1/%u/telemetry",
        "pattern write growhub/v1/%u/state",
        "pattern write growhub/v1/%u/status",
        "pattern write growhub/v1/%u/ack",
        "pattern read growhub/v1/%u/cmd/#",
    ]
    for device_id in sorted(bootstrap_device_ids):
        lines += [
            "",
            f"# Amorcage de {device_id} : révoqué dès l'appairage terminé.",
            f"user {bootstrap_username(device_id)}",
            f"topic write growhub/v1/provision/{device_id}",
            f"topic read growhub/v1/provision/{device_id}/creds",
        ]
    return "\n".join(lines) + "\n"


def _write_atomic(path, text, mode):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.chmod(tmp, mode)
    os.replace(tmp, path)


class BrokerFiles:
    """Reads and writes the broker's password and ACL files, then reloads it."""

    def __init__(self, config_dir=None, reload_command=None, service_user=None):
        config_dir = Path(config_dir or settings.GROWHUB["MOSQUITTO_CONFIG_DIR"])
        self.password_file = config_dir / settings.GROWHUB["MOSQUITTO_PASSWORD_FILE"]
        self.acl_file = config_dir / settings.GROWHUB["MOSQUITTO_ACL_FILE"]
        self.reload_command = (
            settings.GROWHUB["MQTT_RELOAD_COMMAND"]
            if reload_command is None
            else reload_command
        )
        self.service_user = service_user or settings.MQTT_USER

    # --- passwords ---------------------------------------------------------
    def read_users(self):
        if not self.password_file.exists():
            return {}
        return parse_password_file(self.password_file.read_text(encoding="utf-8"))

    def set_password(self, username, password=None):
        """Add or replace one user; returns ``(password, hash)``."""
        password = password or generate_password()
        password_hash = hash_password(password)
        users = self.read_users()
        users[username] = password_hash
        _write_atomic(
            self.password_file, render_password_file(users), PASSWORD_FILE_MODE
        )
        return password, password_hash

    def remove_user(self, username):
        users = self.read_users()
        if username in users:
            del users[username]
            _write_atomic(
                self.password_file, render_password_file(users), PASSWORD_FILE_MODE
            )
            return True
        return False

    # --- ACL ---------------------------------------------------------------
    def write_acl(self, bootstrap_device_ids=()):
        text = render_acl(self.service_user, bootstrap_device_ids)
        _write_atomic(self.acl_file, text, ACL_FILE_MODE)
        return text

    # --- reload ------------------------------------------------------------
    def reload(self):
        """Ask Mosquitto to re-read its password and ACL files (SIGHUP)."""
        if not self.reload_command:
            logger.debug(
                "aucune commande de rechargement configurée, broker non rechargé"
            )
            return False
        result = subprocess.run(  # noqa: S603 - command comes from settings, not user input
            shlex.split(self.reload_command),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            logger.error(
                "rechargement du broker en échec (rc=%s): %s",
                result.returncode,
                (result.stderr or "").strip(),
            )
            return False
        return True
