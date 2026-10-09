# Contrat MQTT v1

Contrat figé de la version 2. Toute évolution passe par `growhub/v2/` et une nouvelle
table d'ACL, afin que les appareils déjà déployés continuent de fonctionner.

## Identités

- `device_id` : `ghb-` + les **6 derniers** caractères hexadécimaux de `machine.unique_id()` — identité
  matérielle, immuable. Ce sont les derniers et non les premiers parce que les octets de tête sont
  communs à tous les Pico W de la série : deux boîtiers se ressembleraient.
- Utilisateur broker : un par appareil, nommé exactement `device_id`.
- Comptes de service : `growhub_api` (API et worker), utilisateurs de provisioning révoqués après appairage.

## Topics

| Topic | Sens | Retained | Payload |
| :--- | :--- | :--- | :--- |
| `growhub/v1/<device_id>/info` | Bourgeon → serveur | oui | `{"model","fw","hw_id","sensors":[...],"actuators":[...],"boot_ts"}` |
| `growhub/v1/<device_id>/telemetry` | Bourgeon → serveur | non | `{"seq","sensors":{"<Nom>":{"<métrique>":{"value","unit"}}},"actuators":{"<Nom>":"ON\|OFF"}}` — `ts` absent : le boîtier n'a pas d'horloge, le serveur date à la réception |
| `growhub/v1/<device_id>/state` | Bourgeon → serveur | oui | `{"actuators":{"<Nom>":"ON\|OFF"}}` (état réel, réémis à chaque changement) |
| `growhub/v1/<device_id>/status` | Bourgeon → serveur | oui | `online` / `offline` (Last Will) |
| `growhub/v1/<device_id>/ack` | Bourgeon → serveur | non | `{"cmd_id","ok","error","state"}` — `state` reprend la forme de la catégorie commandée : `{"actuators":{…}}`, `{"sensors":{…}}` ou `{"config":{…}}` ; un échec porte `ok:false` et un motif dans `error` |
| `growhub/v1/<device_id>/cmd/<kind>` | serveur → Bourgeon | non | `{"cmd_id","action","args"}` — `kind` ∈ `actuators`, `sensors`, `config` |
| `growhub/v1/provision/<device_id>` | Bourgeon (bootstrap) → serveur | oui | `{"device_id","model","fw"}` — annonce du boîtier en attente d'appairage |
| `growhub/v1/provision/<device_id>/creds` | serveur → Bourgeon | oui, effacé après lecture | `{"username","password","broker","port"}` |

Conventions : `ts` en ISO 8601 UTC **quand l'émetteur a une horloge** (le boîtier n'en a pas, le
serveur horodate à la réception), `seq` croissant depuis le démarrage (détection de trous),
QoS 0 partout (la télémétrie est périodique, `retain` porte l'état), payloads JSON UTF-8.

### Qui publie quoi

| | publie | écoute |
| :--- | :--- | :--- |
| Bourgeon appairé | `info`, `telemetry`, `state`, `status`, `ack` | `cmd/actuators`, `cmd/sensors`, `cmd/config` |
| Bourgeon en appairage | `provision/<device_id>` + les mêmes topics | `provision/<device_id>/creds` |
| Serveur | `cmd/<kind>`, `provision/<device_id>/creds` | `+` sur `info`, `telemetry`, `state`, `status`, `ack`, `provision/#` |

Le contrat est écrit une fois de chaque côté du fil — `firmware/src/topics.py` et
`gateway/backend/growhub/topics.py` — et un test les confronte
(`gateway/backend/telemetry/tests/test_contract.py`) : renommer un topic d'un seul
côté fait échouer la suite, pas un boîtier dans une serre.

## ACL Mosquitto

Le fichier est **généré** par `gateway/backend/telemetry/mosquitto.py` (jamais édité à la
main) et le broker le recharge sur SIGHUP. Forme réelle :

```conf
user growhub_api
topic read growhub/v1/+/info        # … telemetry, state, status, ack
topic write growhub/v1/+/cmd/#
topic readwrite growhub/v1/provision/#

# Tout appareil appairé : son propre préfixe uniquement (username == device_id)
pattern write growhub/v1/%u/info    # … telemetry, state, status, ack
pattern read growhub/v1/%u/cmd/#

# Compte d'amorçage, présent seulement pendant l'appairage
user boot-<device_id>
topic write growhub/v1/provision/<device_id>
topic read  growhub/v1/provision/<device_id>/creds
```

Rien à regénérer quand un appareil est ajouté : les motifs couvrent l'existant comme le futur.
Les 12 contrôles de `tools/mqtt_acl_check.sh` (broker jetable) vérifient que ces règles font bien
ce qu'elles annoncent.

Détail historique (une entrée par appareil) conservé pour référence :

```
user <device_id>
topic write growhub/v1/<device_id>/info
topic write growhub/v1/<device_id>/telemetry
topic write growhub/v1/<device_id>/state
topic write growhub/v1/<device_id>/status
topic write growhub/v1/<device_id>/ack
topic read  growhub/v1/<device_id>/cmd/#

user growhub_api
topic read  growhub/v1/+/info
topic read  growhub/v1/+/telemetry
topic read  growhub/v1/+/state
topic read  growhub/v1/+/status
topic read  growhub/v1/+/ack
topic write growhub/v1/+/cmd/#
topic readwrite growhub/v1/provision/#

user boot-<device_id>            # provisoire, supprimé après appairage
topic write growhub/v1/provision/<device_id>
topic read  growhub/v1/provision/<device_id>/creds
```

Conséquence à retenir : l'ancien réglage (un seul identifiant `growhub_device1` partagé)
permettait à n'importe quel boîtier d'écrire chez un autre. Il disparaît avec ce contrat.
