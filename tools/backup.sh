#!/usr/bin/env bash
# Sauvegarde de la base PostgreSQL du gateway GrowHub : dump compressé et
# rotation sur les 7 dernières archives, en local sur le Pi (choix de Marius,
# voir docs/deploiement-v2.md).
#
# Cron conseillé (crontab -e) :
#   30 3 * * * /home/marius/growhub_/tools/backup.sh >> /home/marius/growhub_backups/backup.log 2>&1
#
# Le conteneur postgres n'a pas de port publié : le dump passe par `docker exec`,
# et le conteneur est retrouvé par ses étiquettes Compose plutôt que par un nom
# figé (la pile peut tourner sous un autre nom de projet).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_DIR/gateway/.env"
KEEP=7
PROJECT="${COMPOSE_PROJECT:-gateway}"

# Lecture ciblée : `source .env` échouerait sur UID/GID, qui sont des variables
# en lecture seule dans bash.
read_env() {
  local key="$1"
  [ -f "$ENV_FILE" ] || return 0
  sed -n "s/^${key}=//p" "$ENV_FILE" | head -1
}

POSTGRES_USER="${POSTGRES_USER:-$(read_env POSTGRES_USER)}"
POSTGRES_DB="${POSTGRES_DB:-$(read_env POSTGRES_DB)}"
BACKUP_DIR="${GROWHUB_BACKUP_DIR:-$(read_env GROWHUB_BACKUP_DIR)}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/growhub_backups}"

if [ -z "$POSTGRES_USER" ] || [ -z "$POSTGRES_DB" ]; then
  echo "backup: POSTGRES_USER / POSTGRES_DB introuvables (gateway/.env)" >&2
  exit 1
fi

CONTAINER="$(docker ps -q \
  --filter "label=com.docker.compose.project=${PROJECT}" \
  --filter "label=com.docker.compose.service=postgres" | head -1)"

if [ -z "$CONTAINER" ]; then
  echo "backup: conteneur postgres introuvable (projet Compose « ${PROJECT} »)" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/growhub-${STAMP}.sql.gz"

docker exec "$CONTAINER" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" | gzip > "$OUT"
echo "$(date -Is) backup: $OUT ($(du -h "$OUT" | cut -f1))"

# Rotation : ne conserver que les $KEEP archives les plus récentes.
count=0
while IFS= read -r archive; do
  count=$((count + 1))
  if [ "$count" -gt "$KEEP" ]; then
    rm -f "$archive"
    echo "$(date -Is) backup: rotation, supprimé $(basename "$archive")"
  fi
done < <(ls -1t "$BACKUP_DIR"/growhub-*.sql.gz 2>/dev/null)
