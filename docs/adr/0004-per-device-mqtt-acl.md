# ADR 0004 — Un compte broker par appareil + appairage par code

Rompre avec l'identifiant broker partagé et introduire un flux d'appairage.

## Contexte
Aujourd'hui tous les boîtiers utilisent `growhub_device1`, et le topic est préfixé par un
`client_id` choisi à la main. Dès qu'il y a plusieurs utilisateurs, un appareil peut
écrire chez un autre : la séparation est décorative.

## Décision
Un utilisateur Mosquitto par appareil (`device_id` matériel) avec ACL limitée à son
préfixe, plus un utilisateur de provisioning temporaire révoqué après appairage par code
à 6 caractères.

## Conséquences
- Provisioning automatisé à maintenir (fichier de mots de passe + ACL générés).
- Les appareils existants doivent être reflashés (nouvelle identité de topic).
- L'appartenance reste en base : changer de propriétaire ne réécrit aucun topic.
