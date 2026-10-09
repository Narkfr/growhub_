# ADR 0002 — PostgreSQL seul, suppression d'InfluxDB

Stocker télémétrie et données applicatives dans le même PostgreSQL.

## Contexte
Une serre, quelques appareils, une télémétrie à 30 s d'intervalle. Deux services de
stockage (PostgreSQL + InfluxDB) à administrer, sauvegarder et monitorer sur un Pi.

## Décision
Un seul PostgreSQL. Tables `telemetry` indexées `(device_id, ts)`, partitionnement mensuel
et agrégats horaires au-delà de 24 mois.

## Conséquences
- Un service, une sauvegarde, des transactions cohérentes entre appareil et mesure.
- Requêtes analytiques un peu moins confortables qu'en Flux, largement compensé par
  l'absence d'un second stockage à opérer.
- L'historique existant dans InfluxDB est exporté puis réimporté (ou abandonné, au choix).
