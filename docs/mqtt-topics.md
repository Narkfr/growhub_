# Contrat MQTT v1

Contrat figé de la version 2. Toute évolution passe par `growhub/v2/` et une nouvelle
table d'ACL, afin que les appareils déjà déployés continuent de fonctionner.

## Identités

- `device_id` : `ghb-` + 6 hexadécimaux dérivés de `machine.unique_id()` — identité matérielle, immuable.
- Utilisateur broker : un par appareil, nommé exactement `device_id`.
- Comptes de service : `growhub_api` (API et worker), utilisateurs de provisioning révoqués après appairage.

## Topics

| Topic | Sens | Retained | Payload |
| :--- | :--- | :--- | :--- |
| `growhub/v1/<device_id>/info` | Bourgeon → serveur | oui | `{"model","fw","hw_id","sensors":[...],"actuators":[...],"boot_ts"}` |
| `growhub/v1/<device_id>/telemetry` | Bourgeon → serveur | non | `{"ts","seq","sensors":{"<Nom>":{"<métrique>":{"value","unit"}}},"actuators":{"<Nom>":"ON\|OFF"}}` |
| `growhub/v1/<device_id>/state` | Bourgeon → serveur | oui | `{"actuators":{"<Nom>":"ON\|OFF"}}` (état réel, réémis à chaque changement) |
| `growhub/v1/<device_id>/status` | Bourgeon → serveur | oui | `online` / `offline` (Last Will) |
| `growhub/v1/<device_id>/ack` | Bourgeon → serveur | non | `{"cmd_id","ok","error","state"}` |
| `growhub/v1/<device_id>/cmd/<kind>` | serveur → Bourgeon | non | `{"cmd_id","action","args"}` — `kind` ∈ `actuators`, `sensors`, `config` |
| `growhub/v1/provision/<device_id>` | Bourgeon (bootstrap) → serveur | oui | `{"model","fw","hw_id","pairing_required":true}` |
| `growhub/v1/provision/<device_id>/creds` | serveur → Bourgeon | oui, effacé après lecture | `{"username","password","broker","port"}` |

Conventions : `ts` en ISO 8601 UTC, `seq` croissant depuis le boot (détection de trous),
QoS 0 partout (la télémétrie est périodique, `retain` porte l'état), payloads JSON UTF-8.

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
