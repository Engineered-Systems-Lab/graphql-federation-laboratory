#!/usr/bin/env bash
# Start, stop or inspect the Assets service and its database with their compose file, on loopback.
# It never removes a container, an image or a volume: no rm, no down, no prune.
set -euo pipefail

HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
COMPOSE_FILE="$HERE/compose.yaml"
PORT="${ASSETS_HOST_PORT:-8084}"

usage() {
  cat <<'USAGE'
Usage: bash uss-enterprise/assets/start.sh [--dry-run] start|stop|status
  start    refuse when the loopback port is taken, else: docker compose up -d --wait
  stop     docker compose stop, with 60 seconds for the database (containers and data are kept)
  status   docker compose ps
Environment: ASSETS_DB_ADMIN_PASSWORD and ASSETS_DB_SERVICE_PASSWORD (start needs both; see .env.example),
  ASSETS_HOST_PORT (default 8084), COMPOSE_PROJECT_NAME.
--dry-run checks the port and prints the command it would run, and runs nothing.
Reset the data (your command, not this script's): docker compose -f uss-enterprise/assets/compose.yaml down --volumes
USAGE
}
fail_usage() { usage >&2; exit 2; }

DRY=0
ARGS=()
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) ARGS+=("$arg") ;;
  esac
done
set -- ${ARGS[@]+"${ARGS[@]}"}
[ "$#" -eq 1 ] || fail_usage
COMMAND="$1"

case "$PORT" in
  ''|*[!0-9]*) echo "start.sh: ASSETS_HOST_PORT must be a number, not '$PORT'" >&2; exit 2 ;;
esac

# A connect attempt, not a bind: Windows lets a second listener bind a taken port without an error.
port_taken() {
  (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null
}

run() {
  if [ "$DRY" -eq 1 ]; then
    echo "would run: $*"
  else
    "$@"
  fi
}

case "$COMMAND" in
  start)
    if port_taken; then
      echo "start.sh: refusing to start: 127.0.0.1:$PORT is already in use (stop what listens there, or set ASSETS_HOST_PORT)" >&2
      exit 1
    fi
    run docker compose -f "$COMPOSE_FILE" up -d --wait --wait-timeout 240
    ;;
  stop|status)
    # These commands never use a password, but compose still insists that the variables exist.
    export ASSETS_DB_ADMIN_PASSWORD="${ASSETS_DB_ADMIN_PASSWORD:-unused}" ASSETS_DB_SERVICE_PASSWORD="${ASSETS_DB_SERVICE_PASSWORD:-unused}"
    if [ "$COMMAND" = "stop" ]; then
      run docker compose -f "$COMPOSE_FILE" stop --timeout 60
    else
      run docker compose -f "$COMPOSE_FILE" ps
    fi
    ;;
  *) echo "start.sh: unknown command: $COMMAND" >&2; fail_usage ;;
esac
