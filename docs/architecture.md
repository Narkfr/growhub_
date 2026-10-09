# Architecture GrowHub v2

Document de référence de la refonte multi-utilisateurs. Remplace la description
« Flask + InfluxDB » du README (qui reste valable pour la version déployée tant que
le jalon M7 n'est pas passé).

## 1. Couches

| Couche | Technologie | Rôle |
| :--- | :--- | :--- |
| Objet connecté (**Bourgeon**) | Raspberry Pi Pico W / MicroPython | Lecture capteurs, pilotage actionneurs, écran OLED, MQTT. |
| Transport | MQTT (Mosquitto) | Télémétrie montante, commandes descendantes, statut, appairage. |
| Application | **Django 5.2 LTS + DRF** (ASGI) | Auth, utilisateurs, appareils, API REST, flux live SSE, admin. |
| Pont machine | worker Python (client paho) | MQTT ↔ base, commandes ↔ audit, moteur d'automatisation (ITK). |
| Persistance | **PostgreSQL unique** | Applicatif + télémétrie + audit. Plus d'InfluxDB. |
| Interface | Next.js (React 19 + TypeScript) | Dashboard temps réel, gestion des appareils et des membres. |

Principe directeur : **le broker transporte, la base décide**. Aucune règle de
propriété n'est encodée dans un topic MQTT ; l'appartenance est une ligne en base.

## 2. Modèle de données

```
User            (django.contrib.auth)           identifiant, e-mail, mot de passe, MFA
Site            (optionnel)  owner → User       regroupement (serre, tunnel, parcelle)
Device          (Bourgeon)   device_id, slug,    nom donné par l'utilisateur, modèle,
                             fw_version,          dernier contact, état de provisionnement
Membership      (Device × User, role)           owner | member | viewer ; un appareil peut
                                                être partagé, un utilisateur a N appareils
DeviceCapability(Device)                        capteurs / actionneurs déclarés (topic info)
Telemetry       (Device, ts, metric, value, unit)  séries temporelles, indexées (device, ts)
CommandAudit    (Device, User, cmd_id, payload, résultat, ts)  qui a actionné quoi
AlertRule       (User, Device, condition, canal)   règles personnelles par utilisateur
PairingClaim    (Device, code_hash, expires_at, claimed_by)  appairage, usage unique
MqttCredential  (Device, username, password_hash, revoked_at)  creds broker par appareil
```

Règles :

1. `device_id` est immuable et vient du matériel (`machine.unique_id()`), jamais d'un nom saisi.
2. Une seule ligne `Membership` avec `role=owner` par appareil (contrainte d'unicité partielle).
3. **Toute** requête API se filtre par appartenance de l'utilisateur courant
   (`Device.objects.for_user(request.user)`), jamais par un `device_id` reçu du client seul.

Hiérarchie des droits :

| Rôle | Lire | Actionner (capteurs/actionneurs) | Configurer | Membres / transfert |
| :--- | :--- | :--- | :--- | :--- |
| `owner` | oui | oui | oui | oui |
| `member` | oui | oui | non | non |
| `viewer` | oui | non | non | non |

Cession d'un Bourgeon : `POST /api/v1/devices/{id}/transfer` avec `{"username": "...",
"keep_access": true}` (défaut) — l'ancien propriétaire devient `viewer` et garde l'historique
sans pouvoir agir ; avec `"keep_access": false`, il quitte l'appareil (revente). Un cadran ne
force rien côté boîtier : la propriété est une donnée, pas un topic.
4. Les credentials MQTT sont stockés hachés ; les mots de passe en clair ne sont affichés
   qu'une fois, au moment du provisioning.

## 3. Chemin des données

Montant (télémétrie) :
`Bourgeon → MQTT growhub/v1/<device_id>/telemetry → worker (validation, résolution du device)
→ INSERT Telemetry + cache mémoire du dernier état → diffusion SSE aux navigateurs abonnés`

Descendant (commande) :
`navigateur → POST /api/devices/<id>/commands (DRF, permission par objet) → contrôle
de capacité + écriture CommandAudit → publish growhub/v1/<device_id>/cmd/<kind>
→ Bourgeon répond sur .../ack → worker met à jour CommandAudit`

Automatisation (ITK) : même chemin descendant, déclenché par le worker (seuils, plages
horaire, hysteresis). Les règles vivent en base, pas dans le firmware.

## 4. Flux live (SSE)

Le worker pousse chaque état validé dans une file ; une vue **asynchrone** Django
(`StreamingHttpResponse`) la sert en `text/event-stream`, filtrée par appartenance.
Le worker et l'API ASGI partagent le même processus applicatif (worker en tâche de fond)
ou deux conteneurs — décision d'implémentation au jalon M3, le contrat reste identique.

## 5. Déploiement (cible, jalon M7)

```
docker compose (sur le Pi)
├── postgres        (volume persistant, healthcheck)
├── mosquitto       (broker + ACL, remplace le service natif et son conflit de port)
├── django-asgi     (API + SSE + admin, gunicorn/uvicorn)
├── worker          (pont MQTT ↔ base, automatisation)
└── frontend        (Next.js standalone, port 3001)
Caddy (optionnel) : TLS + reverse proxy, cookies de session en Secure.
```

Sauvegardes : `pg_dump` quotidien comprimé + rotation 7 jours, copie hors machine.
Rétention télémétrie : 24 mois brutes, agrégats horaires au-delà (purge planifiée).

## 6. Sécurité

- Un utilisateur broker Mosquitto **par appareil** (`device_id`) ; les ACL sont générées
  automatiquement (`telemetry/mosquitto.py`) et reposent sur les motifs `%u`, donc un
  appareil ne peut ni lire ni écrire chez un autre (voir `docs/mqtt-topics.md`).
  Matrice vérifiée contre un vrai broker par `tools/mqtt_acl_check.sh`.
- Comptes de service séparés : `growhub_api` (lecture totale, écriture des commandes) et
  le compte de provisioning, révoqué dès que l'appareil est appairé.
- Web : session + CSRF, `HttpOnly`/`SameSite=Lax`, HTTPS dès qu'exposé hors LAN.
- Le firmware ne connaît ni les utilisateurs ni les permissions : il exécute ce qu'il reçoit
  sur son topic de commandes.

## 7. Migration et bascule

La bascule est **directe** (décision du 2026-10-09) : Django est construit en entier,
puis Flask / InfluxDB / Adminer sont retirés dans le même mouvement et Mosquitto passe
en conteneur. Les appareils devront être reflashés (jalon M5) car l'identité de topic
change de `GrowHubClient-xxxx` à `ghb-xxxxxx`.

## 8. Stratégie de tests

| Niveau | Outillage | Cible |
| :--- | :--- | :--- |
| Modèles et permissions Django | `pytest-django` | appartenance, isolation entre utilisateurs, unicité de l'`owner` |
| API DRF | `APIClient` | parcours appairage, commandes, refus d'accès croisés |
| Worker MQTT | paho simulé | validation des payloads, écriture télémétrie, audit |
| Automatisation | unitaires | hysteresis, seuils, plages horaires (portés depuis `logic_engine`) |
| Firmware | pytest avec `machine` mocké | logique capteurs/actionneurs, format des payloads |
| Front | vitest | formatage, client API, hooks live |

Test d'intégration de bout en bout (jalon M8) : un Bourgeon simulé (script Python publiant
sur le broker) → télémétrie visible en base et dans le flux SSE.
