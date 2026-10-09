# ADR 0001 — Django + DRF comme back applicatif

Remplacer Flask par Django 5.2 LTS + DRF pour le back de la passerelle.

## Contexte
L'arrivée de comptes utilisateurs (auth, rôles, partage d'appareils, administration)
sur un back Flask porté à la main. L'opérateur a déjà pratiqué Django.

## Décision
Django 5.2 LTS (supportée jusqu'en avril 2028, montée naturelle vers 6.2 LTS en avril 2027)
avec `contrib.auth`, l'admin, l'ORM/migrations et DRF pour l'API.

## Conséquences
- Auth, sessions, permissions, admin, migrations : fournis, testés, documentés.
- Un seul process applicatif à la place de l'API Flask + les scripts séparés
  (`logic_engine`, `telemetry_logger`, `init_db`, `sync_itk`) réunis en apps Django.
- Dépendances plus lourdes qu'un micro-framework : acceptable, la valeur est dans ce
  qu'on n'écrit pas.
- Coût d'apprentissage de l'admin pour les permissions par objet (`django-guardian` ou
  queryset filtré).
