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
- [ ] **M2** — socle Django : `accounts`, `devices`, memberships, admin, API DRF, tests
- [ ] **M3** — télémétrie PostgreSQL + flux live (SSE) + pont MQTT (worker)
- [ ] **M4** — appairage Bourgeon : `/claim`, ACL, provisioning des creds
- [ ] **M5** — firmware v2 : `device_id` = `machine.unique_id()`, topic `info`, topic de config, code d'appairage à l'écran
- [ ] **M6** — front Next : login, liste des Bourgeons, partage, dashboard live
- [ ] **M7** — infra : retrait de Flask / InfluxDB / Adminer, compose et unités systemd revus, sauvegardes
- [ ] **M8** — CI/CD : runner self-hosted, jobs build + deploy, runbook et rollback
- [ ] **M9** — documentation finale, CHANGELOG, dépendances à jour

Tags prévus : `v0.2` après M4 (back + appairage), `v0.3` après M6, `v1.0` après M8 (fin de migration).

## Conventions techniques

- `device_id` : `ghb-` + 6 caractères hexadécimaux dérivés de `machine.unique_id()` (stable, imprimé sur le boîtier).
- Topics MQTT : racine `growhub/v1/`, contrat figé dans `docs/mqtt-topics.md`.
- Code et commits en anglais, documentation et UI en français.
- `ruff check`, `ruff format --check` et `pytest` bloquants en CI.
- Versions épinglées : runtime dans `requirements/*.txt`, Python 3.13 dans les images.

## Journal

- **2026-10-09 — M0** : `hermes` (36 commits) mergée dans `main` en `--no-ff` (`fdee1c6`), tag annoté `v0.1` poussé. CI relancée sur `main`.
- **2026-10-09 — M1** : conception écrite (architecture, contrat MQTT, flux d'appairage, 5 ADR).
