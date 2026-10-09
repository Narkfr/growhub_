# Appairage d'un Bourgeon

Objectif : passer d'un boîtier flashé mais inconnu à un appareil rattaché à un compte,
avec des credentials MQTT propres à l'appareil, sans jamais manipuler un secret à la main
dans l'interface.

## Étapes

1. **Préparation (opérateur, USB).** `manage.py provision_device ghb-xxxxxx --secrets-path
   firmware/secrets.py` crée le `Device`, le `PairingClaim` (code de 6 caractères, alphabet
   `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`, haché, expiration 24 h) et le compte broker d'amorçage,
   puis écrit le fragment `secrets.py` : Wi-Fi, broker, `MQTT_USER` = `boot-<device_id>`,
   `MQTT_PASSWORD`, `DEVICE_ID`, `PAIRING_CODE`.
   Le `device_id` est celui du matériel : `ghb-` + les 6 derniers hexadécimaux de
   `machine.unique_id()`, relevés sur la carte. Un boîtier qui n'a pas d'identifiant dans son
   `secrets.py` le dérive tout seul, et le serveur l'enregistre sous cet identifiant.
2. **Premier boot (mode appairage).** Le Bourgeon n'a pas de `creds.json` : il se connecte au
   broker avec le compte d'amorçage, publie `growhub/v1/provision/<device_id>` (retained) et
   s'abonne à `.../creds`. L'écran OLED affiche `BOURGEON`, le code à 6 caractères et
   l'identifiant du boîtier. Sans serveur, l'écran et les capteurs continuent de fonctionner
   (mode hors ligne) : l'appairage n'est pas un prérequis pour arroser ou éclairer.
3. **Réclamation (utilisateur).** Dans l'application : « Ajouter un Bourgeon » → saisie du
   code → `POST /api/v1/devices/claims/redeem`. Le serveur vérifie le code et l'expiration,
   refuse un code déjà utilisé, et crée la `Membership(role=owner)`. Le contrôle d'accès
   repose sur cette appartenance, jamais sur le topic : le boîtier peut changer de main sans
   réécriture de son identité.
4. **Provisioning.** Le serveur génère les creds définitives (`username = device_id`,
   mot de passe aléatoire), écrit le fichier de mots de passe et le fichier d'ACL
   (`telemetry/mosquitto.py`, hachage PBKDF2-SHA512 vérifié contre `mosquitto_passwd`),
   recharge le broker (SIGHUP) puis publie en retained
   `growhub/v1/provision/<device_id>/creds`. Le mot de passe en clair n'existe qu'ici,
   dans le fichier du broker et dans ce message : la base ne garde que l'empreinte.
5. **Bascule.** Le Bourgeon écrit `creds.json` puis redémarre — le redémarrage évite de
   réécrire à chaud le client MQTT et ses abonnements, et le fichier devient la seule source
   de vérité des identifiants. Sa **première** trame sur `growhub/v1/<device_id>/...` prouve
   qu'il a bien reçu les creds : le serveur efface alors le retained (le mot de passe n'est
   plus rejouable) et supprime le compte `boot-<device_id>` du fichier de mots de passe et
   des ACL. Rien à faire côté utilisateur : l'appairage se termine tout seul.

Côté Mosquitto, l'isolation repose sur les motifs : `pattern write growhub/v1/%u/telemetry`
et `pattern read growhub/v1/%u/cmd/#`, où `%u` est le nom d'utilisateur — qui est
l'identifiant matériel. Aucune entrée par appareil n'est nécessaire pour les Bourgeons
appairés ; seuls les comptes d'amorçage ont des entrées explicites, retirées à l'appairage.

Vérification avant déploiement :

```bash
tools/mqtt_acl_check.sh   # broker jetable sur un port dédié, 12 contrôles ACL/authentification
```

## Sécurité et cas limites

- Le code à 6 caractères (~10^9 combinaisons avec 32 symboles, seuil de tentatives par IP
  et par code, expiration 24 h) empêche un voisin du LAN de s'approprier un boîtier.
- Un appareil resté non appairé ne publie **que** sur son topic de provisioning : il ne peut
  pas polluer les données d'un autre utilisateur.
- Perte de `creds.json` (reset usine) : le boîtier revient en mode appairage ; il faut
  réémettre un code (`provision_device --force`) et révoquer l'ancien (`--revoke`).
- Transfert d'appareil : on change la `Membership` (l'`owner`), jamais les topics — l'historique
  de télémétrie reste attaché au matériel.
- Réinitialisation complète : suppression du `Device` côté serveur + purge des creds broker + reflash.
