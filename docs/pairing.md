# Appairage d'un Bourgeon

Objectif : passer d'un boîtier flashé mais inconnu à un appareil rattaché à un compte,
avec des credentials MQTT propres à l'appareil, sans jamais manipuler un secret à la main
dans l'interface.

## Étapes

1. **Flash (opérateur, USB).** `tools/provision_device.py` écrit `firmware/secrets.py` :
   Wi-Fi + `bootstrap_secret` (aléatoire 32 hex) + `pairing_code` (6 caractères, alphabet
   `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`). Le même script enregistre côté serveur (API admin)
   l'empreinte du `bootstrap_secret` et le `pairing_code` haché, avec une expiration (24 h).
2. **Premier boot.** Le Bourgeon n'a pas encore de creds définitives : il se connecte au
   broker avec l'utilisateur `boot-<device_id>` (mot de passe = `bootstrap_secret`), publie
   `growhub/v1/provision/<device_id>` (retained) et s'abonne à `.../creds`.
   L'écran OLED affiche `APPAIRAGE` + le code à 6 caractères ; les logs série le répètent.
   Sans serveur, l'écran et les capteurs continuent de fonctionner (mode hors ligne).
3. **Réclamation (utilisateur).** Dans l'application : « Ajouter un Bourgeon » → saisie du
   code → `POST /api/devices/claims`. Le serveur vérifie l'empreinte et l'expiration,
   refuse un code déjà utilisé, crée le `Device`, la `Membership(role=owner)` et
   `DeviceCapability` à partir du topic `info`.
4. **Provisioning.** Le serveur génère les creds définitives (`username = device_id`,
   mot de passe aléatoire), les ajoute au fichier de mots de passe Mosquitto et aux ACL,
   puis publie en retained `growhub/v1/provision/<device_id>/creds`, et efface ce retained
   une fois le `ack` reçu.
5. **Bascule.** Le Bourgeon écrit `/creds.json`, redémarre en mode normal (topics
   `growhub/v1/<device_id>/...`), et le serveur révoque `boot-<device_id>`.

## Sécurité et cas limites

- Le code à 6 caractères (~10^9 combinaisons avec 32 symboles, seuil de tentatives par IP
  et par code, expiration 24 h) empêche un voisin du LAN de s'approprier un boîtier.
- Un appareil resté non appairé ne publie **que** sur son topic de provisioning : il ne peut
  pas polluer les données d'un autre utilisateur.
- Perte de `/creds.json` (reset usine) : le boîtier revient en mode provisioning avec un
  nouveau `bootstrap_secret` et un nouveau code, l'ancien étant révoqué.
- Transfert d'appareil : on change la `Membership` (l'`owner`), jamais les topics — l'historique
  de télémétrie reste attaché au matériel.
- Réinitialisation complète : suppression du `Device` côté serveur + purge des creds broker + reflash.
