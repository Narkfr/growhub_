"""Prepare a freshly flashed device: claim code + temporary broker account.

    venv/bin/python gateway/backend/manage.py provision_device ghb-3f2a91 \
        --name "Serre tomates" --secrets-path firmware/secrets.py

Prints (and optionally writes) the snippet to paste into the Pico's secrets.py,
then the pairing code to type in the app once the device is powered on.
"""

from devices.models import DEVICE_ID_VALIDATOR, Device
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from telemetry.mosquitto import BrokerFiles
from telemetry.provisioning import (
    provision_bootstrap,
    register_claim,
    revoke_credentials,
)


def render_secrets_snippet(device_id, username, password, broker, port, pairing_code):
    """The firmware's ``secrets.py`` entries, key names included.

    The keys mirror ``firmware/secrets.example.py``: the firmware reads
    ``WIFI_SSID``, ``MQTT_BROKER``… in upper case, so generating lower-case
    keys here would silently leave the device unconfigured.
    """
    body = ", ".join(
        [
            '"WIFI_SSID": ""',
            '"WIFI_PASSWORD": ""',
            f'"MQTT_BROKER": "{broker}"',
            f'"MQTT_PORT": {port}',
            f'"MQTT_USER": "{username}"',
            f'"MQTT_PASSWORD": "{password}"',
            f'"DEVICE_ID": "{device_id}"',
            f'"PAIRING_CODE": "{pairing_code}"',
        ]
    )
    return f"secrets = {{{body}}}\n"


class Command(BaseCommand):
    help = "Crée un Bourgeon, son code d'appairage et son compte broker d'amorçage."

    def add_arguments(self, parser):
        parser.add_argument("device_id", help="Identifiant matériel, ex. ghb-3f2a91")
        parser.add_argument("--name", help="Nom affiché (défaut : l'identifiant)")
        parser.add_argument("--model", default="Bourgeon V1")
        parser.add_argument(
            "--code", help="Forcer le code d'appairage (sinon aléatoire)"
        )
        parser.add_argument("--ttl-hours", type=int, help="Validité du code, en heures")
        parser.add_argument(
            "--broker",
            help="Adresse du broker telle que le boîtier doit la voir "
            "(défaut : MQTT_BROKER des réglages, qui est le nom du service Compose "
            "dans un conteneur — inutilisable depuis un Bourgeon sur le réseau).",
        )
        parser.add_argument("--port", type=int, help="Port du broker vu du boîtier")
        parser.add_argument(
            "--secrets-path", help="Écrire le fragment secrets.py dans ce fichier"
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Réinitialiser un appareil déjà enregistré",
        )
        parser.add_argument(
            "--revoke", action="store_true", help="Révoquer les identifiants et sortir"
        )

    def handle(self, *args, **options):
        device_id = options["device_id"].strip().lower()
        try:
            DEVICE_ID_VALIDATOR(device_id)
        except ValidationError as exc:
            raise CommandError(f"identifiant invalide : {exc.messages[0]}") from exc

        device = Device.objects.filter(device_id=device_id).first()
        if options["revoke"]:
            if device is None:
                raise CommandError(f"appareil inconnu : {device_id}")
            revoke_credentials(device)
            self.stdout.write(
                self.style.WARNING(f"{device_id} : identifiants révoqués")
            )
            return

        if device is not None and not options["force"]:
            raise CommandError(
                f"{device_id} existe déjà (utilise --force pour le réinitialiser)."
            )
        if device is None:
            device = Device.objects.create(
                device_id=device_id,
                slug=device_id,
                name=options["name"] or device_id,
                model=options["model"],
            )

        claim, code = register_claim(
            device, code=options["code"], ttl_hours=options["ttl_hours"]
        )
        username, password = provision_bootstrap(device)

        snippet = render_secrets_snippet(
            device_id,
            username,
            password,
            options["broker"] or settings.MQTT_BROKER,
            options["port"] or settings.MQTT_PORT,
            code,
        )
        if options["secrets_path"]:
            with open(options["secrets_path"], "w", encoding="utf-8") as handle:
                handle.write(snippet)
            self.stdout.write(
                self.style.SUCCESS(f"fragment écrit dans {options['secrets_path']}")
            )

        self.stdout.write(snippet)
        self.stdout.write(
            self.style.SUCCESS(
                f"Code d'appairage de {device_id} : {code} "
                f"(expire le {claim.expires_at:%Y-%m-%d %H:%M} UTC)"
            )
        )
        self.stdout.write(
            "Prochaine étape : allumer le boîtier, puis saisir ce code dans l'app. "
            f"Fichier de mots de passe : {BrokerFiles().password_file}"
        )
