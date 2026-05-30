#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PROJECT_NAME="${PROJECT_NAME:-test}"
API_HEALTH_URL="${API_HEALTH_URL:-http://127.0.0.1:8000/health}"
WEB_URL="${WEB_URL:-http://127.0.0.1/}"
COMPOSE=(docker compose)

log() {
  printf '[deploy] %s\n' "$*"
}

fail() {
  printf '[deploy] ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

wait_for_url() {
  local url="$1"
  local name="$2"
  local max_attempts="${3:-60}"
  local attempt=1

  while (( attempt <= max_attempts )); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      log "$name is ready: $url"
      return 0
    fi
    sleep 2
    attempt=$((attempt + 1))
  done

  fail "$name did not become ready after $((max_attempts * 2)) seconds: $url"
}

check_docker() {
  require_command docker
  require_command curl
  docker info >/dev/null 2>&1 || fail "Docker is not running or current user cannot access Docker."
  "${COMPOSE[@]}" version >/dev/null 2>&1 || fail "Docker Compose plugin is not available."
}

check_port_80() {
  if command -v lsof >/dev/null 2>&1 && lsof -iTCP:80 -sTCP:LISTEN >/dev/null 2>&1; then
    log "Port 80 is already in use. If nginx fails to start, stop the process using port 80 or change docker-compose.yml."
  fi
}

deploy() {
  check_docker
  check_port_80

  log "Building and starting Docker Compose services..."
  "${COMPOSE[@]}" -p "$PROJECT_NAME" up --build -d

  log "Current service status:"
  "${COMPOSE[@]}" -p "$PROJECT_NAME" ps

  wait_for_url "$API_HEALTH_URL" "API"
  wait_for_url "$WEB_URL" "Web UI"

  log "Deployment complete."
  log "Web UI: $WEB_URL"
  log "API health: $API_HEALTH_URL"
  log "noVNC direct URL: http://127.0.0.1:6080/vnc.html"
}

case "${1:-deploy}" in
  deploy | up)
    deploy
    ;;
  status)
    check_docker
    "${COMPOSE[@]}" -p "$PROJECT_NAME" ps
    ;;
  logs)
    check_docker
    "${COMPOSE[@]}" -p "$PROJECT_NAME" logs -f --tail=200
    ;;
  down)
    check_docker
    "${COMPOSE[@]}" -p "$PROJECT_NAME" down
    ;;
  restart)
    check_docker
    "${COMPOSE[@]}" -p "$PROJECT_NAME" restart
    ;;
  *)
    cat <<'USAGE'
Usage:
  ./deploy.sh          Build, start, and health-check the app
  ./deploy.sh up       Same as deploy
  ./deploy.sh status   Show Docker Compose service status
  ./deploy.sh logs     Follow service logs
  ./deploy.sh restart  Restart services
  ./deploy.sh down     Stop and remove containers

Environment overrides:
  PROJECT_NAME=test
  API_HEALTH_URL=http://127.0.0.1:8000/health
  WEB_URL=http://127.0.0.1/
USAGE
    exit 2
    ;;
esac
