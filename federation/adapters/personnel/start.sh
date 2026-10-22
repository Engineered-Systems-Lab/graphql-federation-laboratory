#!/usr/bin/env bash
# Start, stop or inspect the Personnel adapter with its compose file, on loopback.
# It never removes a container, an image or a volume: no rm, no down, no prune.
set -euo pipefail

HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
COMPOSE_FILE="$HERE/compose.yaml"
PORT="${PERSONNEL_ADAPTER_HOST_PORT:-8182}"

usage() {
  cat <<'USAGE'
Usage: bash federation/adapters/personnel/start.sh [--dry-run] start|stop|status
  start    refuse when the loopback port is taken, else: docker compose up -d --wait
  stop     docker compose stop (the container is kept)
  status   docker compose ps
Environment: PERSONNEL_SERVICE_URL (the Personnel v2 service; default http://host.docker.internal:8082/soap/personnel-v2),
  PERSONNEL_ADAPTER_HOST_PORT (default 8182), COMPOSE_PROJECT_NAME.
--dry-run checks the port and prints the command it would run, and runs nothing.
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
  ''|*[!0-9]*) echo "start.sh: PERSONNEL_ADAPTER_HOST_PORT must be a number, not '$PORT'" >&2; exit 2 ;;
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
      echo "start.sh: refusing to start: 127.0.0.1:$PORT is already in use (stop what listens there, or set PERSONNEL_ADAPTER_HOST_PORT)" >&2
      exit 1
    fi
    run docker compose -f "$COMPOSE_FILE" up -d --build --wait --wait-timeout 240
    ;;
  stop)
    run docker compose -f "$COMPOSE_FILE" stop --timeout 30
    ;;
  status)
    run docker compose -f "$COMPOSE_FILE" ps
    ;;
  *) echo "start.sh: unknown command: $COMMAND" >&2; fail_usage ;;
esac
