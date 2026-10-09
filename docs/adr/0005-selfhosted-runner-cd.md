# ADR 0005 — Déploiement continu par runner self-hosted

Déployer la passerelle automatiquement depuis GitHub, sans ouvrir de port entrant.

## Contexte
Le Pi héberge les services et n'a pas (et ne doit pas avoir) d'accès entrant depuis Internet.

## Décision
Runner GitHub Actions self-hosted installé sur le Pi ; le job de déploiement est déclenché
sur tag `v*` (ou manuellement), reconstruit les images et redémarre le compose, avec
contrôle de santé et retour arrière documenté.

## Conséquences
- Aucune exposition réseau, pas de clé SSH de déploiement à gérer.
- Le runner exécute du code du dépôt sur la machine de production : le dépôt privé/public
  doit rester sous contrôle (branches protégées, revue).
- Un `deploy.sh` équivalent reste fourni pour un déploiement manuel.
