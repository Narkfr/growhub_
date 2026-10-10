#!/usr/bin/env bash
#
# Déploie la pile growhub_ sur cette machine, depuis le dépôt cloné ici.
#
# Appelé par le workflow « Deploy » quand l'intégration continue passe sur `main`
# (voir `docs/deploiement-cd.md`), et utilisable à la main :
#
#   tools/deploy.sh                # la branche main
#   tools/deploy.sh --ref <sha>    # un commit précis, pour un retour arrière
#   tools/deploy.sh -n             # montre ce qui serait fait, ne touche à rien
#
# Ne touche jamais aux secrets : `gateway/.env`, le fichier de mots de passe
# Mosquitto, l'ACL et les volumes vivent hors de git et hors de ce chemin. Le
# déploiement ne remplace que du code.
#
# En cas d'échec du contrôle de santé, la révision déployée précédemment est
# remise en place automatiquement, et la sortie est non nulle.
set -euo pipefail

# Le runner GitHub démarre avec un environnement minimal : sans PATH explicite,
# `docker` et `pg_dump` (utilisés par la sauvegarde) sont introuvables.
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"

REPO_DIR="${REPO_DIR:-$HOME/growhub_}"
STATE_DIR="${STATE_DIR:-$HOME/growhub_backups}"
BRANCH="${BRANCH:-main}"
COMPOSE_FILE="$REPO_DIR/gateway/docker-compose.yml"
COMPOSE=(docker compose -f "$COMPOSE_FILE")
MANAGE=(python gateway/backend/manage.py)
STATE_FILE="$STATE_DIR/deploy-state"
LOG_FILE="$STATE_DIR/deploy.log"

HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:3001/}"
API_URL="${API_URL:-http://127.0.0.1:3001/api/v1/auth/me}"
SERVICES=(postgres mqtt-broker mqtt-reloader backend worker frontend)

mkdir -p "$STATE_DIR"

# Le script se copie hors du dépôt avant de travailler : un déploiement change la
# révision du dépôt, donc potentiellement ce fichier même, et bash lit un script au
# fur et à mesure de son exécution — se faire réécrire en cours de route donne un
# comportement indéfini. Cette recopie précède la lecture des arguments : la
# relance repasse la ligne de commande telle quelle, et une liste déjà vidée par
# l'analyse perdrait `--ref` en silence.
if [ -z "${DEPLOY_STAGED:-}" ]; then
    staged="$STATE_DIR/deploy-$$.sh"
    cp "$0" "$staged"
    chmod +x "$staged"
    export DEPLOY_STAGED=1
    exec "$staged" "$@"
fi
trap 'rm -f "$0"' EXIT

# Le runner GitHub tourne en service utilisateur : il hérite de tous les groupes de
# l'utilisateur sauf `docker` (le gestionnaire de session ne reprend pas un groupe
# ajouté après son démarrage), et tout appel à `docker compose` échoue alors sur
# « permission denied … /var/run/docker.sock ». `sg` reprend le groupe le temps du
# déploiement, sans privilège supplémentaire — l'utilisateur en est déjà membre.
if ! docker info >/dev/null 2>&1 && command -v sg >/dev/null 2>&1; then
    exec sg docker -c "$(printf '%q ' "$0" "$@")"
fi

target="$BRANCH"
dry_run=0
while [ $# -gt 0 ]; do
    case "$1" in
        --ref) target="${2:?--ref attend un commit ou une branche}"; shift 2 ;;
        -n|--dry-run) dry_run=1; shift ;;
        -h|--help) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "option inconnue : $1" >&2; exit 2 ;;
    esac
done

# shellcheck disable=SC2317  # appelée depuis le piège et le chemin d'échec
log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"; }

git_at() { git -C "$REPO_DIR" "$@"; }

compose() {
    # La pile tourne dans le projet Compose « gateway » ; on s'y tient.
    "${COMPOSE[@]}" "$@"
}

expected_health() {
    # Le contrôle doit répondre sur le service, pas sur un code de sortie : un
    # déploiement vert qui laisse l'API à terre est pire qu'un échec franc.
    local code
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$HEALTH_URL" || true)"
    [ "$code" = "200" ] || { log "échec : $HEALTH_URL répond $code (200 attendu)"; return 1; }

    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$API_URL" || true)"
    case "$code" in
        401|403|200) ;;  # l'API répond : non authentifié, c'est normal ici.
        *) log "échec : $API_URL répond $code (l'API ne répond pas)"; return 1 ;;
    esac

    local service
    for service in "${SERVICES[@]}"; do
        if [ -z "$(compose ps --status running --services | grep -x "$service" || true)" ]; then
            log "échec : le service $service ne tourne pas"
            return 1
        fi
    done

    # Le worker est le seul service sans port : s'il boucle sur une traceback, rien
    # ne le montre de l'extérieur. On exige donc une ingestion récente.
    local stale
    stale="$(compose exec -T backend "${MANAGE[@]}" shell -c "
from devices.models import Device
from django.utils import timezone
recent = [d for d in Device.objects.all() if d.last_seen and (timezone.now() - d.last_seen).total_seconds() < 300]
print(len(recent))
" 2>/dev/null | tail -1 | tr -d '[:space:]')"
    if [ "${stale:-0}" = "0" ]; then
        log "avertissement : aucun Bourgeon n'a parlé depuis 5 minutes (contrôle non bloquant)"
    fi
    return 0
}

deploy_revision() {
    local ref="$1" previous="$2"
    log "déploiement de $ref (depuis $previous)"

    git_at fetch --prune origin
    # Sur `main`, la copie de production suit la branche ; pour un commit précis
    # (retour arrière), elle se détache — on ne déplace jamais une branche de
    # travail vers une révision arbitraire. Un commit qui *est* `main` est traité
    # comme `main`, sans quoi chaque déploiement laisserait la copie détachée.
    if [ "$(git_at rev-parse "$ref")" = "$(git_at rev-parse "origin/$BRANCH")" ]; then
        git_at checkout -q -B "$BRANCH" "$ref"
    else
        git_at checkout -q --detach "$ref"
    fi

    if [ "$dry_run" = "0" ] && [ -x "$REPO_DIR/tools/backup.sh" ]; then
        # Avant toute migration : la base est la seule chose que git ne sait pas
        # remettre en place.
        "$REPO_DIR/tools/backup.sh" >/dev/null 2>&1 || log "avertissement : la sauvegarde a échoué, on continue"
    fi

    compose up -d --build --remove-orphans
    compose exec -T backend "${MANAGE[@]}" migrate --noinput
}

# --- déroulé -----------------------------------------------------------------

cd "$REPO_DIR"
if [ -n "$(git_at status --porcelain)" ]; then
    log "refus : le dépôt porte des modifications non validées dans $REPO_DIR"
    exit 1
fi

previous="$(git_at rev-parse HEAD)"
if [ "$target" = "$BRANCH" ]; then
    git_at fetch --prune origin
    target="origin/$BRANCH"
fi
resolved="$(git_at rev-parse "$target")"

log "=== déploiement demandé : $target ($resolved), révision en place : $(git_at rev-parse --short "$previous") ==="
deployed=1
if [ "$resolved" = "$previous" ]; then
    log "rien à déployer : la révision demandée est déjà en place"
    deployed=0
else
    if [ "$dry_run" = "1" ]; then
        log "mode simulation : rien n'a été touché"
        exit 0
    fi
    deploy_revision "$target" "$previous"
fi

if expected_health; then
    [ "$deployed" = "1" ] && printf '%s\n' "$previous" > "$STATE_FILE"
    log "déploiement réussi : $(git_at rev-parse --short HEAD) en place (état précédent conservé dans $STATE_FILE)"
    exit 0
fi

if [ "$deployed" = "0" ]; then
    # Rien n'a été déployé : il n'y a rien à défaire, la pile était déjà malade.
    log "contrôle de santé en échec alors que rien n'a été déployé — la pile demande un regard humain"
    exit 1
fi

log "contrôle de santé en échec — retour arrière vers $(git_at rev-parse --short "$previous")"
git_at checkout -q --detach "$previous"
compose up -d --build --remove-orphans
compose exec -T backend "${MANAGE[@]}" migrate --noinput || true

if expected_health; then
    log "retour arrière effectué : $(git_at rev-parse --short HEAD) est de nouveau en place"
else
    log "le retour arrière n'a pas suffi — la pile demande un regard humain"
fi
exit 1
