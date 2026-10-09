# Backend Django (gateway v2)

Le back est un projet Django 5.2 dans `gateway/backend/`. Il porte l'authentification,
les comptes, les appareils (Bourgeons), leur propriété, l'API REST et — à partir du
jalon M3 — la télémétrie et le flux temps réel. Voir `docs/architecture.md`.

## Arborescence

```
gateway/backend/
├── manage.py
├── growhub/            projet : settings, urls, asgi/wsgi
├── accounts/           User (AbstractUser + e-mail unique), auth par session
└── devices/            Site, Device, Membership, Capability, MqttCredential, PairingClaim
    ├── managers        DeviceQuerySet.for_user / owned_by / active
    ├── permissions.py  lecture pour tout membre, écriture pour le propriétaire
    ├── services.py     appairage (code à 6 caractères), synchronisation des capacités
    ├── views.py        API REST (ViewSets + endpoints d'appairage)
    └── tests/          pytest-django : modèles, appairage, API
```

## Démarrage local

```bash
# dépendances (une fois)
python3 -m venv venv && venv/bin/pip install -r requirements/dev.txt

# base de données : le PostgreSQL du compose (port 5432)
venv/bin/python gateway/backend/manage.py migrate
venv/bin/python gateway/backend/manage.py createsuperuser
venv/bin/python gateway/backend/manage.py runserver 0.0.0.0:8000     # dev
# production : ASGI (nécessaire pour le flux SSE live)
venv/bin/uvicorn growhub.asgi:application --host 0.0.0.0 --port 8000 --app-dir gateway/backend
```

Les variables d'environnement sont lues dans `gateway/.env` (voir `.env.example`).

## Tests et qualité

```bash
venv/bin/python -m pytest -q                  # toute la suite (firmware, gateway v1, backend v2)
venv/bin/python -m pytest -q gateway/backend  # backend seulement
venv/bin/python -m ruff check . && venv/bin/python -m ruff format --check .
```

Les tests du backend s'exécutent sur PostgreSQL (base `test_growhub` créée automatiquement).
L'utilisateur PostgreSQL doit pouvoir créer des bases — c'est le cas de l'utilisateur
`POSTGRES_USER` du compose. Pour un essai rapide sans PostgreSQL : `DJANGO_DB_ENGINE=sqlite`.

## Points d'entrée de l'API (v1)

| Méthode | URL | Accès | Rôle |
| :--- | :--- | :--- | :--- |
| POST | `/api/v1/auth/login` | public | ouvre une session |
| POST | `/api/v1/auth/logout` | connecté | ferme la session |
| GET | `/api/v1/auth/me` | connecté | profil courant |
| GET/POST | `/api/v1/sites` | connecté | sites de l'utilisateur |
| GET | `/api/v1/devices` | connecté | Bourgeons dont il est membre |
| GET/PATCH/DELETE | `/api/v1/devices/{id}` | membre / propriétaire | lecture / renommage / suppression |
| GET/POST | `/api/v1/devices/{id}/members` | membre / propriétaire | lister / ajouter un membre |
| DELETE | `/api/v1/devices/{id}/members/{user_id}` | propriétaire | retirer un membre |
| POST | `/api/v1/devices/{id}/transfer` | propriétaire | céder la propriété (`keep_access`, défaut vrai) |
| POST | `/api/v1/devices/claims` | staff | enregistrer un appareil flashé (outil de provisioning) |
| POST | `/api/v1/devices/claims/redeem` | connecté | appairer avec le code affiché sur l'OLED |

Trois rôles d'appartenance : `owner` (tout), `member` (lire + actionner), `viewer`
(lire seulement). Un transfert rétrograde l'ancien propriétaire en `viewer`, sauf
`keep_access: false` qui le retire complètement de l'appareil.

Règles structurantes :

- aucune création d'appareil par l'API : seul l'appairage crée un `Device` ;
- toute liste passe par `Device.objects.for_user(request.user)` ;
- un membre lit, seul le propriétaire écrit (permission `DeviceAccessPermission`) ;
- un code d'appairage est à usage unique, expire (24 h par défaut) et se verrouille après
  `GROWHUB_PAIRING_MAX_ATTEMPTS` essais.
