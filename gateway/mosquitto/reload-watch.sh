#!/bin/sh
# Relit la configuration de Mosquitto quand le backend l'a réécrite.
#
# Mosquitto ne réévalue `password_file` et `acl_file` que sur SIGHUP : le backend
# écrit ces fichiers dans le dossier partagé (voir docker-compose.yml), ce
# veilleur envoie le signal. Il cible le conteneur du broker par son nom Compose
# (`<projet>-mqtt-broker-1`) et ignore tout le reste, y compris l'ancienne pile
# v0.1 dont le conteneur s'appelle `growhub-mqtt`.
set -eu

WATCHED="password_file acl_file"
CONFIG_DIR="${GROWHUB_MOSQUITTO_CONFIG_DIR:-/mosquitto/config}"

fingerprint() {
  for name in $WATCHED; do
    file="$CONFIG_DIR/$name"
    if [ -f "$file" ]; then
      md5sum "$file"
    else
      echo "absent $file"
    fi
  done | md5sum | cut -d' ' -f1
}

broker_container() {
  docker ps --format '{{.Names}}' --filter 'label=com.docker.compose.service=mqtt-broker' \
    | grep -m1 -- '-mqtt-broker-' || true
}

last="$(fingerprint)"
echo "reload-watch: veille sur $CONFIG_DIR ($WATCHED), état initial $last"

while true; do
  sleep 2
  current="$(fingerprint)"
  [ "$current" = "$last" ] && continue
  last="$current"

  container="$(broker_container)"
  if [ -z "$container" ]; then
    echo "reload-watch: changement détecté mais broker introuvable, rien envoyé"
    continue
  fi

  echo "reload-watch: configuration modifiée, SIGHUP vers $container"
  docker kill -s HUP "$container" || echo "reload-watch: le SIGHUP a échoué"
done
