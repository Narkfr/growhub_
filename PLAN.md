# GrowHub — plan de migration v2 (Django, multi-utilisateurs)

État au 2026-10-09. Décisions, jalons et journal de la refonte « v2 ».
Les jalons sont fusionnés dans `main` (qui reste stable et taggué) au fil de l'eau ;
le travail se fait dans une branche par jalon, `hermes` reste la branche d'intégration.

## Décisions verrouillées

| Sujet | Décision |
| :--- | :--- |
| Front | **Next.js conservé** (c'est déjà React 19 + TypeScript). Client API + types sortis dans un paquet partagé, réutilisable par l'app React Native future. |
| Base de données | **PostgreSQL unique** (applicatif + télémétrie). InfluxDB supprimé. |
| Back | **Django 5.2 LTS + DRF** remplace Flask, **bascule directe** (pas de cohabitation prolongée). |
| Auth | `contrib.auth` + DRF. Sessions + CSRF pour le web, JWT (simplejwt) réservé au mobile/API tierce. |
| MQTT | Un utilisateur broker **par appareil** + ACL, identité de topic = `device_id` matériel. |
| Appairage | Code de réclamation à 6 caractères affiché sur l'OLED + provisioning réseau des creds MQTT. |
| CD | **Runner GitHub self-hosted sur le Pi** (aucun port entrant). |
| Git | `main` = stable + tags, `hermes` = intégration, une branche par jalon. |
| Nom produit | L'objet connecté s'appelle **Bourgeon** (code : `Device`). |

## Jalons

- [x] **M0** — merge `hermes` → `main`, tag `v0.1`
- [x] **M1** — documents de conception (`docs/architecture.md`, `docs/mqtt-topics.md`, `docs/pairing.md`, ADR)
- [x] **M2** — socle Django : `accounts`, `devices`, memberships, admin, API DRF, tests
- [x] **M3** — télémétrie PostgreSQL + flux live (SSE) + pont MQTT (worker)
- [x] **M4** — appairage Bourgeon : `/claim`, ACL, provisioning des creds
- [x] **M5** — firmware v2 : `device_id` = `machine.unique_id()`, topic `info`, topic de config, code d'appairage à l'écran
- [x] **M6** — front Next : login, liste des Bourgeons, partage, dashboard live
- [x] **M7** — infra : retrait de Flask / InfluxDB / Adminer, compose et unités systemd revus, sauvegardes
- [x] **M8** — CI/CD : runner self-hosted, jobs build + deploy, runbook et rollback
- [ ] **M9** — documentation finale, CHANGELOG, dépendances à jour

Paquet partagé `@growhub/client` : types et client API réutilisables par l’application mobile (React Native) — voir `docs/front.md`.

Tags prévus : `v0.2` après M4 (back + appairage), `v0.3` après M6, `v1.0` après M8 (fin de migration).
`v0.2` est posé sur `main` après M4 ; M5 (firmware) ne change rien à ce que le serveur expose,
il n'ajoute donc pas de tag.

## Conventions techniques

- `device_id` : `ghb-` + 6 caractères hexadécimaux dérivés de `machine.unique_id()` (stable, imprimé sur le boîtier).
- Topics MQTT : racine `growhub/v1/`, contrat figé dans `docs/mqtt-topics.md`.
- Code et commits en anglais, documentation et UI en français.
- `ruff check`, `ruff format --check` et `pytest` bloquants en CI.
- Versions épinglées : runtime dans `requirements/*.txt`, Python 3.13 dans les images.

## Journal

- **2026-10-10 — M8** : déploiement continu. Un runner auto-hébergé sur le Pi
  (`pi-growhub`, service utilisateur, `linger` activé) attend le verdict de la CI ;
  si `main` est verte, `.github/workflows/deploy.yml` lui fait exécuter
  `tools/deploy.sh` sur la copie de production `~/growhub_`. Le script sauvegarde
  la base **avant** la migration, reconstruit, migre, puis contrôle le service
  (page, API, six conteneurs) et **revient tout seul** à la révision précédente si
  le contrôle échoue. Choix de Marius : runner local plutôt qu'un SSH entrant, et
  déploiement automatique plutôt qu'une approbation à chaque fois. Runbook :
  `docs/deploiement-cd.md`.
- **2026-10-10 — M7** : bascule de la v2 en production, sur le vrai matériel. Pile v2 dans
  `gateway/docker-compose.yml` (postgres, mosquitto, `mqtt-reloader`, backend ASGI, worker, front),
  l'ancienne conservée dans `docker-compose.v1.yml` ; ses quatre conteneurs retirés après vérification,
  ses images gardées comme retour arrière. Le Bourgeon `ghb-29442c` a été reflashé et appairé, son écran
  est décrit par le manifeste. La répétition générale à blanc puis la bascule ont mis au jour **six
  défauts qu'aucun test ne pouvait voir**, tous corrigés : droits des fichiers du broker (Mosquitto
  s'arrêtait au lieu de recharger), identifiant client MQTT partagé par deux processus (déconnexions en
  boucle), adresse du broker livrée au boîtier dans le message d'appairage, `ALLOWED_HOSTS` et origines
  CSRF du proxy, flux temps réel recompressé (mesures en direct figées), et les deux vocabulaires de
  statut confondus (« Inconnu » sur la carte). Sauvegarde `pg_dump` quotidienne, rotation 7 jours.
  Runbook : `docs/deploiement-v2.md`. Reste connu : le broker déconnecte le boîtier (`malformed packet`
  toutes les 30 à 60 s) — publications concurrentes à sérialiser côté firmware, jalon à part.
- **2026-10-09 — M0** : `hermes` (36 commits) mergée dans `main` en `--no-ff` (`fdee1c6`), tag annoté `v0.1` poussé. CI relancée sur `main`.
- **2026-10-09 — M1** : conception écrite (architecture, contrat MQTT, flux d'appairage, 5 ADR).
- **2026-10-09 — M6** : paquet partagé `@growhub/client` (types alignés sur les sérialiseurs DRF,
  client sans dépendance : `fetch` injecté, jeton CSRF lu dans le cookie, flux SSE avec repli en
  sondage — donc utilisable tel quel par React Native) ; tableau de bord Next complet (connexion,
  liste, appairage par code, détail avec mesures/actionneurs/configuration/historique/partage) ;
  `/auth/me` pose désormais le cookie CSRF, sans quoi la SPA ne pouvait pas poster ; job CI dédié
  au paquet partagé.
- **2026-10-09 — M5** : firmware sur le contrat v1 — identifiant `ghb-xxxxxx` dérivé des
  6 derniers hexadécimaux du matériel (les octets de tête sont communs aux Pico W de la série),
  topics centralisés dans `src/topics.py`, mode appairage (annonce retained, attente des
  identifiants, écriture de `creds.json`, redémarrage) et code affiché à l'écran, `ack` avec
  `cmd_id` et un motif de refus, configuration à chaud bornée, télémétrie `{seq,sensors,actuators}`
  sans horodatage (le boîtier n'a pas d'horloge). Test de contrat firmware↔serveur ajouté ;
  il a fait apparaître une divergence réelle sur la forme de `state` dans l'`ack`.
- **2026-10-09 — M4** : provisioning réel — hachage PBKDF2 vérifié contre `mosquitto_passwd`,
  ACL par motifs `%u` générées et rechargées à chaud, publication des creds en retained puis
  effacement à la première trame du boîtier, révocation du compte d'amorçage, commande
  `provision_device`, 12 contrôles ACL validés contre un Mosquitto jetable (`tools/mqtt_acl_check.sh`).
