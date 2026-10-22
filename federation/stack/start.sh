#!/usr/bin/env bash
# Start, stop or inspect the whole federation stack (stub-backend mode) with its compose file, on loopback.
# It never removes a container, an image or a volume: no rm, no down, no prune.
set -euo pipefail

HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ROOT="$(CDPATH= cd -- "$HERE/../.." && pwd)"
COMPOSE_FILE="$HERE/compose.yaml"
COMPOSE_SCRIPT="$ROOT/federation/routers/apollo/compose_supergraph.py"
COSMO_COMPOSE_SCRIPT="$ROOT/federation/routers/cosmo/compose_execution_config.py"
# One router at a time: apollo (default, port 8170) or cosmo (port 8171).
ROUTER_KIND="${FEDERATION_ROUTER:-apollo}"
case "$ROUTER_KIND" in
  apollo) ROUTER_PORT="${ROUTER_HOST_PORT:-8170}" ;;
  cosmo) ROUTER_PORT="${COSMO_ROUTER_HOST_PORT:-8171}" ;;
  *) echo "start.sh: FEDERATION_ROUTER must be apollo or cosmo, not '$ROUTER_KIND'" >&2; exit 2 ;;
esac
PORTS="$ROUTER_PORT ${PERSONNEL_ADAPTER_HOST_PORT:-8182} ${MISSIONS_ADAPTER_HOST_PORT:-8183} ${ASSETS_ADAPTER_HOST_PORT:-8184} ${MAPPING_ADAPTER_HOST_PORT:-8190}"
BACKENDS="assets-db assets-bootstrap assets-service personnel-service missions-stub missions-adapter personnel-adapter assets-adapter mapping-adapter"

usage() {
  cat <<'USAGE'
Usage: bash federation/stack/start.sh [--dry-run] start|stop|status
  start    refuse when a loopback port is taken, else: start the backends and the four adapters, compose the supergraph with Rover,
           then start the Apollo router (docker compose up -d --wait). With FEDERATION_ROUTER=cosmo: compose the execution config with
           wgc (no license, no account) and start the Cosmo router instead.
  stop     docker compose stop (the containers are kept)
  status   docker compose ps
Ports (loopback): router 8170 (Apollo) or 8171 (Cosmo), Personnel adapter 8182, Missions adapter 8183, Assets adapter 8184, mapping adapter 8190.
Environment: FEDERATION_ROUTER=apollo|cosmo (default apollo; one router at a time),
  APOLLO_ELV2_LICENSE=accept (an Apollo start needs it: Rover's composition plugin is under the Elastic License 2.0 and YOU accept it),
  ROUTER_HOST_PORT (Apollo), COSMO_ROUTER_HOST_PORT (Cosmo), PERSONNEL_ADAPTER_HOST_PORT, MISSIONS_ADAPTER_HOST_PORT, ASSETS_ADAPTER_HOST_PORT, MAPPING_ADAPTER_HOST_PORT,
  SUPERGRAPH_FILE (default federation/routers/apollo/supergraph.graphql, the committed file: start composes it again, so a changed
  schema shows up as a Git diff), EXECUTION_CONFIG_FILE (Cosmo; default federation/routers/cosmo/execution-config.json, the committed
  file, composed again the same way), COMPOSE_PROJECT_NAME, PYTHON (default python).
  Random database credentials are made for the run unless STACK_ASSETS_DB_ADMIN_PASSWORD and STACK_ASSETS_DB_SERVICE_PASSWORD are set.
--dry-run checks the ports and prints the commands it would run, and runs nothing.
Reset the data (your command, not this script's): docker compose -f federation/stack/compose.yaml down --volumes
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

for port in $PORTS; do
  case "$port" in
    ''|*[!0-9]*) echo "start.sh: a host port must be a number, not '$port'" >&2; exit 2 ;;
  esac
done

# A connect attempt, not a bind: Windows lets a second listener bind a taken port without an error.
port_taken() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}

run() {
  if [ "$DRY" -eq 1 ]; then
    echo "would run: $*"
  else
    "$@"
  fi
}

random_secret() {
  head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n'
}

native_path() {
  cygpath -m "$1" 2>/dev/null || printf '%s' "$1"
}

SUPERGRAPH="${SUPERGRAPH_FILE:-$ROOT/federation/routers/apollo/supergraph.graphql}"
export SUPERGRAPH_FILE="$(native_path "$SUPERGRAPH")"
EXECUTION_CONFIG="${EXECUTION_CONFIG_FILE:-$ROOT/federation/routers/cosmo/execution-config.json}"
export EXECUTION_CONFIG_FILE="$(native_path "$EXECUTION_CONFIG")"
PROFILE=()
if [ "$ROUTER_KIND" = "cosmo" ]; then PROFILE=(--profile cosmo); fi

case "$COMMAND" in
  start)
    for port in $PORTS; do
      if port_taken "$port"; then
        echo "start.sh: refusing to start: 127.0.0.1:$port is already in use (stop what listens there, or set its *_HOST_PORT variable)" >&2
        exit 1
      fi
    done
    if [ "$ROUTER_KIND" = "apollo" ] && [ "${APOLLO_ELV2_LICENSE:-}" != "accept" ]; then
      echo "start.sh: refusing to start: Rover's composition plugin is under the Elastic License 2.0; set APOLLO_ELV2_LICENSE=accept to accept it" >&2
      exit 1
    fi
    export STACK_ASSETS_DB_ADMIN_PASSWORD="${STACK_ASSETS_DB_ADMIN_PASSWORD:-$(random_secret)}"
    export STACK_ASSETS_DB_SERVICE_PASSWORD="${STACK_ASSETS_DB_SERVICE_PASSWORD:-$(random_secret)}"
    run docker compose -f "$COMPOSE_FILE" up -d --build --wait --wait-timeout 600 $BACKENDS
    if [ "$ROUTER_KIND" = "cosmo" ]; then
      run "${PYTHON:-python}" -B "$COSMO_COMPOSE_SCRIPT" --out "$EXECUTION_CONFIG"
      run docker compose -f "$COMPOSE_FILE" "${PROFILE[@]}" up -d --wait --wait-timeout 120 cosmo-router
    else
      run "${PYTHON:-python}" -B "$COMPOSE_SCRIPT" --out "$SUPERGRAPH"
      run docker compose -f "$COMPOSE_FILE" up -d --wait --wait-timeout 120 router
    fi
    ;;
  stop|status)
    # These commands never use a password, but compose still insists that the variables exist.
    export STACK_ASSETS_DB_ADMIN_PASSWORD="${STACK_ASSETS_DB_ADMIN_PASSWORD:-unused}" STACK_ASSETS_DB_SERVICE_PASSWORD="${STACK_ASSETS_DB_SERVICE_PASSWORD:-unused}"
    if [ "$COMMAND" = "stop" ]; then
      run docker compose -f "$COMPOSE_FILE" ${PROFILE[@]+"${PROFILE[@]}"} stop --timeout 60
    else
      run docker compose -f "$COMPOSE_FILE" ${PROFILE[@]+"${PROFILE[@]}"} ps
    fi
    ;;
  *) echo "start.sh: unknown command: $COMMAND" >&2; fail_usage ;;
esac
