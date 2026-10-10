# Déploiement de la v2 (jalons M7/M8) — runbook

Bascule de la pile Flask + InfluxDB vers Django 5.2 + DRF + PostgreSQL, avec
appairage des Bourgeons et ACL MQTT par appareil. Ce document est le mode
opératoire : il doit pouvoir être suivi sans rien redécouvrir.

Décisions prises par Marius le 2026-10-10 :

| Sujet | Décision |
| :--- | :--- |
| Sauvegardes | **En local sur le Pi** (`~/growhub_backups`, rotation 7 jours), pas de copie hors machine. |
| Historique InfluxDB | **Aucune archive conservée.** Le volume n'est pas supprimé pour autant (rien ne se fait avec `down -v`). |
| Données PostgreSQL v0.1 | Néant : la base `growhub` ne contient aucune table applicative. Rien à migrer. |
| Écran du Bourgeon | Inchangé : température + humidité (champs par défaut du manifeste). |
| Tableau de bord | S'ouvrira avec des courbes vides : accepté. |
| Automatisation ITK | Non portée en v2 pour l'instant. L'ancien `logic_engine.py` n'était lancé nulle part. |

## Ce que la bascule casse, et ce qu'elle ne casse pas

Le firmware v2 change l'identité de l'appareil (`GrowHubClient-xxx` →
`ghb-xxxxxx`, compte d'amorçage `boot-ghb-xxxxxx`) et le préfixe des topics. Le
backend v2 n'écoute que `growhub/v1/…` : **entre la bascule de la passerelle et
l'appairage réussi du boîtier, la télémétrie n'est plus enregistrée.** C'est la
seule conséquence.

- Le Bourgeon est autonome : il publie, exécute les commandes reçues, et son
  écran ne dépend pas du réseau. La serre ne s'arrête pas.
- Aucune automatisation n'est active (l'ancien moteur ITK n'était pas lancé) :
  il n'y a aucun pilotage d'actionneur à interrompre.
- Côté PostgreSQL, rien à perdre : la base v0.1 est vide. Côté InfluxDB, rien à
  garder (décision ci-dessus).

## Phase 0 — préparer (aucun impact sur la machine en service)

Sur la branche `chore/m7-infra`, dans le dépôt :

- `gateway/docker-compose.yml` = pile v2 (postgres, mosquitto, `mqtt-reloader`,
  backend ASGI, worker `mqtt_bridge`, front). L'ancienne pile est conservée telle
  quelle dans `gateway/docker-compose.v1.yml`.
- `gateway/backend/Dockerfile` (Python 3.13 + deps `requirements/common.txt`),
  `gateway/frontend/Dockerfile` (contexte = racine du dépôt, pour embarquer le
  paquet partagé `packages/growhub-client`).
- `gateway/mosquitto/config/mosquitto.conf` déclare `acl_file` ; le contenu de
  démarrage est le modèle `acl_file.example` (à copier en `acl_file`, ignoré par
  git).
- `gateway/mosquitto/reload-watch.sh` + service `mqtt-reloader` : Mosquitto ne
  relit `password_file`/`acl_file` que sur SIGHUP, ce veilleur envoie le signal
  dès que le backend réécrit les fichiers.
- `tools/backup.sh` : `pg_dump` + rotation 7 jours dans `~/growhub_backups`.
- `gateway/.env.example` à jour (les variables `INFLUXDB_*` restent, elles
  servent au chemin de retour arrière).

## Phase 1 — sauvegarder

1. `cp gateway/mosquitto/config/acl_file.example gateway/mosquitto/config/acl_file`
   (si le fichier n'existe pas encore).
2. `./tools/backup.sh` — la base est vide, mais on veut l'habitude et la
   preuve que le chemin fonctionne.
3. **Dumper le Pico** avant tout flash : `mpremote connect /dev/ttyACM0` puis
   copie de `main.py`, `boot.py`, `config.json`, `constants.py`, `manifest.py`,
   `secrets.py`, `src/`, `sensors/`, `lib/` vers `~/growhub_backups/pico-v0.1/`.
   C'est le seul retour arrière qui demande du physique.

## Phase 2 — répétition générale à blanc (la v0.1 continue de tourner)

Pile v2 complète montée à côté de la v0.1, projet Compose distinct et ports
décalés :

```
cd gateway
docker compose -p growhub_dryrun -f docker-compose.yml -f docker-compose.dryrun.yml up -d
```

L'override `docker-compose.dryrun.yml` isole aussi le broker : l'essai écrit ses
comptes et ses ACL dans `mosquitto/config-dryrun`, jamais dans la configuration
de la pile en service.

Déroulé de l'essai, avec le **Bourgeon simulé** (`tools/fake_bourgeon.py`, le test
d'intégration du jalon M8) :

```
# 1. provisionner un appareil de laboratoire (identifiant volontairement factice)
docker compose -p growhub_dryrun ... exec -T backend \
  python gateway/backend/manage.py provision_device ghb-dead01 \
  --name "Essai M8" --broker mqtt-broker --port 1883 \
  --secrets-path /tmp/dryrun_secrets.py

# 2. le Bourgeon simulé s'annonce et attend ses identifiants
docker compose -p growhub_dryrun ... exec -T backend \
  python tools/fake_bourgeon.py --secrets /tmp/dryrun_secrets.py --frames 5

# 3. racheter le code (POST /api/v1/devices/claims/redeem) puis demander la
#    livraison des identifiants (POST /api/v1/devices/<pk>/provision)
```

Contrôles passés le 2026-10-10 : `migrate` et `/healthz` répondent ; les
identifiants arrivent au boîtier ; 9 à 15 mesures atterrissent en base
(`telemetry.Telemetry`) et dans le flux SSE ; les capacités sont créées depuis
l'annonce du boîtier ; le compte d'amorçage est révoqué après appairage ;
`tools/mqtt_acl_check.sh` passe ses 12 contrôles ; le tableau de bord sert sa page.

### Ce que la répétition a corrigé avant la bascule

1. **Mosquitto mourait au rechargement.** Le backend écrivait les comptes et les
   ACL en tant que `root` *dans son conteneur*, alors que le broker tourne en
   `${UID}:${GID}` : il ne pouvait plus relire son fichier de mots de passe et
   s'arrêtait au lieu de recharger. Les services `backend` et `worker` portent
   donc `user: "${UID}:${GID}"`.
2. **Deux processus publiaient sous le même identifiant client** (`gh-prov`), et
   le broker les déconnectait mutuellement en boucle (`session taken over` à
   répétition). Le suffixe doit identifier le processus **et** le conteneur : les
   PID valent 1 dans l'un comme dans l'autre, c'est le nom d'hôte qui tranche
   (`telemetry/mqtt.py`, fonction `process_client_id`).
3. **Un nom de service n'est pas une adresse pour le boîtier.** `MQTT_BROKER`
   vaut `mqtt-broker` dans les conteneurs : écrit tel quel dans `secrets.py`, le
   Bourgeon ne pourrait pas s'y connecter. D'où l'option `--broker` de
   `provision_device` (le `.env` garde `localhost` pour l'outillage de l'hôte, le
   compose remplace par les noms de service).
4. **Une publication refusée reste muette** (MQTT 3.1.1, QoS 0). Juste après la
   livraison des identifiants, le broker peut encore ignorer le nouveau compte
   pendant le temps qu'il relit ses fichiers : le boîtier doit attendre d'être
   *effectivement connecté* avant d'émettre (`fake_bourgeon.py` le fait comme le
   firmware, via `is_connected()`), sinon ses premières trames disparaissent sans
   trace. Le veilleur recharge désormais toutes les 0,5 s.

### Ce que la bascule elle-même a appris (2026-10-10)

Deux défauts que la répétition n'avait pas pu montrer, corrigés pendant la
bascule :

5. **Le message d'appairage transportait `MQTT_BROKER`, donc le nom du service
   Compose.** Le boîtier a écrit `creds.json` avec `broker: "mqtt-broker"`,
   intraduisible depuis le réseau : « Échec de connexion MQTT : -2 », en boucle.
   Le Bourgeon simulé ne lisait pas ce champ, d'où l'angle mort. Les réglages
   portent maintenant `GROWHUB_DEVICE_BROKER` / `GROWHUB_DEVICE_BROKER_PORT`
   (l'IP LAN du Pi), utilisés **par les deux** — le `secrets.py` et le message
   d'appairage.
6. **Le proxy du tableau de bord réécrit l'en-tête `Host`** par celui du service
   Django : toutes les routes `/api` répondaient 400 (`DisallowedHost:
   'backend:8000'`) — le tableau de bord était inutilisable derrière le front.
   `DJANGO_ALLOWED_HOSTS` reçoit le nom du service depuis le compose.
7. **DRF répondait en HTML à un navigateur.** Dès qu'un client annonce préférer
   `text/html`, DRF choisit son rendu « browsable API » : la connexion réussie
   *et* les erreurs revenaient en HTML, le SPA échouait à les lire et affichait
   « Impossible de joindre l'API. » quel que soit le mot de passe — jamais
   « Identifiants invalides. ». `DEFAULT_RENDERER_CLASSES` se limite maintenant à
   `JSONRenderer` (ce qui retire aussi un formulaire d'essai exposé sur le LAN).
   Réflexe de diagnostic : reproduire toute requête du SPA **avec l'en-tête
   `Accept` d'un navigateur**, jamais avec `curl` seul — c'est ce qui a masqué le
   défaut pendant les essais.

## Phase 3 — la bascule (fenêtre courte, Pico en USB)

1. `docker compose -f gateway/docker-compose.v1.yml stop` — conteneurs
   conservés, pas supprimés (c'est la moitié du retour arrière).
2. Vérifier que `password_file` contient bien le compte de service (`growhub_api`)
   et que `acl_file` existe.
3. `docker compose -f gateway/docker-compose.yml up -d --build` puis
   `docker compose exec backend python gateway/backend/manage.py migrate`.
4. `createsuperuser` (compte de Marius), connexion à `http://<pi>:3001`,
   vérification de l'admin.
5. Lire l'identifiant réel du boîtier sur le matériel, puis le provisionner —
   `--broker` doit être l'adresse par laquelle le **boîtier** voit le broker
   (l'IP LAN du Pi, jamais le nom de service Compose) :
   ```
   mpremote connect /dev/ttyACM0 exec "import machine, ubinascii; print('ghb-' + ubinascii.hexlify(machine.unique_id()).decode()[-6:])"
   docker compose exec backend python gateway/backend/manage.py provision_device ghb-xxxxxx \
       --name "Serre" --broker 192.168.1.113 --port 1883 --secrets-path firmware/secrets.py
   ```
6. Flasher le boîtier (séquence watchdog de `growhub-pico-deploy`) : `main.py`,
   `constants.py`, `src/**` (dont `src/display/`), `lib/ssd1306.py`,
   `manifest.py` **mis à jour en place** (section `display.fields`) et le
   `secrets.py` produit à l'étape 5. **Le fragment généré porte
   `"WIFI_SSID": ""`** : y recopier les identifiants WiFi du boîtier (ceux de la
   sauvegarde de la phase 1), sinon la carte ne rejoint plus le réseau. Le
   boîtier démarre alors en mode appairage : l'écran affiche `BOURGEON`, le code
   et l'identifiant.
7. Appairer dans le tableau de bord (`/pair`), puis vérifier : le boîtier reçoit
   ses creds, écrit `creds.json`, redémarre, et la télémétrie remonte.
8. Laisser tourner 15 à 30 minutes : compter les mesures en base, surveiller les
   `Denied PUBLISH` du broker.

## Phase 4 — retirer l'ancien (après confirmation de la télémétrie)

- `docker compose -f gateway/docker-compose.v1.yml rm -s` des seuls services
  `api`, `telemetry-logger`, `influxdb`, `adminer` — **jamais `down -v`**.
- Retirer le bloc « transition v0.1 » de `acl_file`, recharger le broker.
- Unités systemd vestiges (`growhub-mosquitto`, `growhub-api`,
  `growhub-dashboard`) : `systemctl --user disable --now`, et surtout **ne pas
  toucher** à `hermes-gateway.service`.
- Mettre le cron de sauvegarde en place.
- Le volume InfluxDB reste en place, inerte, jusqu'à décision explicite.

**Exécuté le 2026-10-10** : les quatre conteneurs retirés (`docker rm` sur les noms,
sans passer par le compose v0.1 pour ne rien risquer d'autre), **images conservées**
(~1 Go) comme retour arrière — elles sont reconstructibles depuis le dépôt au tag
`v0.1` si on veut récupérer la place. Le bloc « transition v0.1 » de `acl_file` a
disparu de lui-même : le backend réécrit ce fichier en entier au premier appairage.
Les trois unités systemd étaient déjà `disabled`, rien ne les démarre. Sauvegarde
quotidienne en place (03 h 30, rotation 7 jours, testée avec un `PATH` minimal).

## Phase 5 — M8 / M9

- Runner GitHub self-hosted sur le Pi + workflow CD : déployer = pousser sur
  `main`.
- Test d'intégration de bout en bout (issu de la phase 2) branché en CI.
- Purge de rétention (`GROWHUB_TELEMETRY_RETENTION_MONTHS`) : la commande
  n'existe pas encore.
- CHANGELOG, relecture des dépendances.

## Retour arrière

| Élément | Marche arrière |
| :--- | :--- |
| Passerelle | `docker compose -f gateway/docker-compose.v1.yml up -d` : la v0.1 repart sur les mêmes volumes, InfluxDB intact. |
| Boîtier | Reflash des fichiers sauvegardés en phase 1 (USB, quelques minutes). |
| Données | Rien à perdre : PostgreSQL était vide, le volume InfluxDB n'est jamais supprimé. |
| ACL | Restaurer le contenu d'amorçage (`acl_file.example`) et recharger le broker : le compte partagé du boîtier retrouve ses droits. |

Aucun point de non-retour avant la phase 4.
