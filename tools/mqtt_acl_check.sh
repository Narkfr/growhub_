#!/usr/bin/env bash
#
# Contrôle des ACL MQTT avant déploiement.
#
# Lance une instance Mosquitto JETABLE (port dédié, configuration et fichiers de
# mots de passe temporaires) et vérifie, avec les identifiants réellement générés
# par le backend (telemetry/mosquitto.py) :
#
#   * le hash PBKDF2 est accepté par le broker (sinon les Bourgeons ne peuvent pas se connecter) ;
#   * un appareil appairé n'écrit et ne lit que son propre préfixe de topics ;
#   * le compte de service lit tout et commande tout ;
#   * le compte d'amorçage ne fait que demander son appairage et lire ses credentials ;
#   * mot de passe erroné et client anonyme sont refusés.
#
# Aucun service de la passerelle n'est touché : pas de docker, pas de systemd,
# rien sur le port 1883. Utilisation :
#
#     tools/mqtt_acl_check.sh
#
# Sortie : un rapport OK/ÉCHEC par contrôle, puis un verdict et un code de retour.

set -u

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOSQ_ROOT="${GROWHUB_MOSQUITTO_ROOT:-$HOME/growhub-mosquitto/rootfs}"
PORT="${GROWHUB_ACL_CHECK_PORT:-18831}"
SCRATCH="${GROWHUB_ACL_CHECK_DIR:-$(mktemp -d /tmp/growhub-acl-check-XXXXXX)}"
PYTHON="$REPO_DIR/venv/bin/python"

MOSQ="$MOSQ_ROOT/usr/sbin/mosquitto"
PUB="$MOSQ_ROOT/usr/bin/mosquitto_pub"
SUB="$MOSQ_ROOT/usr/bin/mosquitto_sub"

DEVICE="ghb-3f2a91"
OTHER="ghb-001122"
BOOTSTRAP_ID="ghb-7c1d02"
BOOTSTRAP="boot-$BOOTSTRAP_ID"
SERVICE="growhub_api"

for binary in "$MOSQ" "$PUB" "$SUB"; do
  if [ ! -x "$binary" ]; then
    echo "Binaire introuvable : $binary (définir GROWHUB_MOSQUITTO_ROOT)" >&2
    exit 2
  fi
done

export LD_LIBRARY_PATH="$MOSQ_ROOT/usr/lib/aarch64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# --- 1. Identifiants et ACL générés par le backend ---------------------------
cd "$REPO_DIR" || exit 2
GROWHUB_ACL_CHECK_OUT="$SCRATCH" PYTHONPATH=gateway/backend DJANGO_SETTINGS_MODULE=growhub.settings \
  "$PYTHON" - <<'PY' || exit 2
import os

import django

django.setup()
from telemetry.mosquitto import BrokerFiles, bootstrap_username

out = os.environ["GROWHUB_ACL_CHECK_OUT"]
broker = BrokerFiles(config_dir=out, reload_command="")
users = {
    "DEVICE_PW": "ghb-3f2a91",
    "OTHER_PW": "ghb-001122",
    "BOOT_PW": bootstrap_username("ghb-7c1d02"),
    "SERVICE_PW": "growhub_api",
}
with open(os.path.join(out, "creds.env"), "w", encoding="utf-8") as handle:
    for key, username in users.items():
        password, _ = broker.set_password(username)
        handle.write(f"{key}={password}\n")
broker.write_acl(["ghb-7c1d02"])
PY

# shellcheck disable=SC1091
source "$SCRATCH/creds.env"

cat > "$SCRATCH/mosquitto.conf" <<EOF
listener $PORT
allow_anonymous false
password_file $SCRATCH/password_file
acl_file $SCRATCH/acl_file
persistence false
log_dest file $SCRATCH/broker.log
log_type all
EOF

"$MOSQ" -c "$SCRATCH/mosquitto.conf" &
MOSQ_PID=$!
sleep 2
if ! kill -0 "$MOSQ_PID" 2>/dev/null; then
  echo "Le broker jetable n'a pas démarré :" >&2
  cat "$SCRATCH/broker.log" >&2
  exit 2
fi

cleanup() {
  kill "$MOSQ_PID" 2>/dev/null
  wait "$MOSQ_PID" 2>/dev/null
}
trap cleanup EXIT

FAILED=0
ok() { printf '  OK    %s\n' "$1"; }
fail() { printf '  ÉCHEC %s\n' "$1"; FAILED=1; }

# publish <user> <password> <topic> : le code retour n'est PAS une preuve d'ACL en
# MQTT (le broker jette silencieusement un publish refusé), on l'ignore pour juger.
publish() {
  "$PUB" -h 127.0.0.1 -p "$PORT" -q 1 -u "$1" -P "$2" -t "$3" -m '{"x":1}' >/dev/null 2>&1
}

# assert_delivered <abonné_user> <abonné_pw> <éditeur_user> <éditeur_pw> <topic> <libellé>
# L'abonné témoin doit être le client qui a légitimement le droit de lire ce topic.
assert_delivered() {
  local sub_user=$1
  local sub_password=$2
  local pub_user=$3
  local pub_password=$4
  local topic=$5
  local label=$6
  local file="$SCRATCH/w-$(echo "$topic" | tr '/' '_')"
  timeout 6 "$SUB" -h 127.0.0.1 -p "$PORT" -q 1 -u "$sub_user" -P "$sub_password" \
    -t "$topic" -C 1 -W 5 > "$file" 2>/dev/null &
  local watcher=$!
  sleep 1
  publish "$pub_user" "$pub_password" "$topic"
  wait "$watcher" 2>/dev/null
  if [ -s "$file" ]; then ok "$label"; else fail "$label (rien reçu)"; fi
}

# assert_denied_publish <user> <password> <topic> <libellé> : la publication doit
# apparaître comme refusée dans le journal du broker, et un témoin ne rien recevoir.
assert_denied_publish() {
  local user=$1
  local password=$2
  local topic=$3
  local label=$4
  local file="$SCRATCH/d-$(echo "$topic" | tr '/' '_')"
  local before
  before=$(grep -c "Denied PUBLISH.*'$topic'" "$SCRATCH/broker.log" 2>/dev/null || true)
  timeout 6 "$SUB" -h 127.0.0.1 -p "$PORT" -q 1 -u "$SERVICE" -P "$SERVICE_PW" \
    -t "$topic" -C 1 -W 4 > "$file" 2>/dev/null &
  local watcher=$!
  sleep 1
  publish "$user" "$password" "$topic"
  wait "$watcher" 2>/dev/null
  sleep 1
  local after
  after=$(grep -c "Denied PUBLISH.*'$topic'" "$SCRATCH/broker.log" 2>/dev/null || true)
  if [ "${after:-0}" -gt "${before:-0}" ] && [ ! -s "$file" ]; then
    ok "$label"
  else
    fail "$label (refus journalisé: ${after:-0} vs ${before:-0}, reçu='$(cat "$file")')"
  fi
}

echo "Broker jetable : pid $MOSQ_PID, port $PORT, fichiers dans $SCRATCH"
echo

echo "A. Appareil appairé ($DEVICE)"
assert_delivered "$SERVICE" "$SERVICE_PW" "$DEVICE" "$DEVICE_PW" "growhub/v1/$DEVICE/telemetry" "publie sur son propre topic"
assert_denied_publish "$DEVICE" "$DEVICE_PW" "growhub/v1/$OTHER/telemetry" "écriture chez un autre appareil refusée"
assert_denied_publish "$DEVICE" "$DEVICE_PW" "growhub/v1/$DEVICE/cmd/actuators" "écriture de ses propres commandes refusée"

echo
echo "B. Compte de service ($SERVICE)"
assert_delivered "$DEVICE" "$DEVICE_PW" "$SERVICE" "$SERVICE_PW" "growhub/v1/$DEVICE/cmd/actuators" "commande transmise à l'appareil"
assert_delivered "$OTHER" "$OTHER_PW" "$SERVICE" "$SERVICE_PW" "growhub/v1/$OTHER/cmd/actuators" "commande à n'importe quel appareil"

echo
echo "C. Compte d'amorçage ($BOOTSTRAP)"
assert_delivered "$SERVICE" "$SERVICE_PW" "$BOOTSTRAP" "$BOOT_PW" "growhub/v1/provision/$BOOTSTRAP_ID" "demande d'appairage acceptée"
assert_denied_publish "$BOOTSTRAP" "$BOOT_PW" "growhub/v1/$BOOTSTRAP_ID/telemetry" "télémétrie refusée au compte d'amorçage"
assert_denied_publish "$BOOTSTRAP" "$BOOT_PW" "growhub/v1/$OTHER/telemetry" "compte d'amorçage confiné à son topic"

# Le compte d'amorçage doit pouvoir LIRE ses credentials.
creds_file="$SCRATCH/creds_read"
timeout 6 "$SUB" -h 127.0.0.1 -p "$PORT" -q 1 -u "$BOOTSTRAP" -P "$BOOT_PW" \
  -t "growhub/v1/provision/$BOOTSTRAP_ID/creds" -C 1 -W 4 > "$creds_file" 2>/dev/null &
creds_watcher=$!
sleep 1
"$PUB" -h 127.0.0.1 -p "$PORT" -q 1 -u "$SERVICE" -P "$SERVICE_PW" \
  -t "growhub/v1/provision/$BOOTSTRAP_ID/creds" -m '{"username":"ghb-7c1d02"}' >/dev/null 2>&1
wait "$creds_watcher" 2>/dev/null
if [ -s "$creds_file" ]; then ok "credentials lisibles par le compte d'amorçage"; else fail "credentials non reçus"; fi

echo
echo "D. Lectures croisées"
other_read="$SCRATCH/other_read"
timeout 6 "$SUB" -h 127.0.0.1 -p "$PORT" -q 1 -u "$OTHER" -P "$OTHER_PW" \
  -t "growhub/v1/$DEVICE/telemetry" -C 1 -W 3 > "$other_read" 2>/dev/null &
other_watcher=$!
sleep 1
publish "$DEVICE" "$DEVICE_PW" "growhub/v1/$DEVICE/telemetry"
wait "$other_watcher" 2>/dev/null
if [ ! -s "$other_read" ]; then ok "télémétrie d'un appareil illisible par un autre"; else fail "fuite de lecture entre appareils"; fi

echo
echo "E. Authentification"
if "$PUB" -h 127.0.0.1 -p "$PORT" -q 1 -u "$DEVICE" -P "mauvais-mot-de-passe" \
  -t "growhub/v1/$DEVICE/telemetry" -m '{}' >/dev/null 2>&1; then
  fail "mot de passe erroné accepté"
else
  ok "mot de passe erroné refusé"
fi
if "$PUB" -h 127.0.0.1 -p "$PORT" -q 1 -t "growhub/v1/$DEVICE/telemetry" -m '{}' >/dev/null 2>&1; then
  fail "publication anonyme acceptée"
else
  ok "publication anonyme refusée"
fi

echo
echo "Refus journalisés par le broker : $(grep -c 'Denied PUBLISH' "$SCRATCH/broker.log" 2>/dev/null || echo 0)"
echo
if [ "$FAILED" = "1" ]; then
  echo "RÉSULTAT : AU MOINS UN CONTRÔLE A ÉCHOUÉ"
  exit 1
fi
echo "RÉSULTAT : tous les contrôles passent"
