#!/usr/bin/env bash
# Start, stop or inspect the whole federation stack with its compose file, on loopback: with the Missions stub (stub-backend mode,
# the default) or, with MISSIONS_BACKEND=real, with the operator's real Missions service on Oracle (missions-real.compose.yaml).
# It never removes a container, an image or a volume: no rm, no down, no prune.
# It never starts, stops, creates or resets Oracle or the real Missions service: the real mode checks that they run and refuses otherwise.
set -euo pipefail

HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ROOT="$(CDPATH= cd -- "$HERE/../.." && pwd)"
COMPOSE_FILE="$HERE/compose.yaml"
REAL_MISSIONS_OVERLAY="$HERE/missions-real.compose.yaml"
COMPOSE_SCRIPT="$ROOT/federation/routers/apollo/compose_supergraph.py"
COSMO_COMPOSE_SCRIPT="$ROOT/federation/routers/cosmo/compose_execution_config.py"
# One router at a time: apollo (default, port 8170) or cosmo (port 8171).
ROUTER_KIND="${FEDERATION_ROUTER:-apollo}"
case "$ROUTER_KIND" in
  apollo) ROUTER_PORT="${ROUTER_HOST_PORT:-8170}" ;;
  cosmo) ROUTER_PORT="${COSMO_ROUTER_HOST_PORT:-8171}" ;;
  *) echo "start.sh: FEDERATION_ROUTER must be apollo or cosmo, not '$ROUTER_KIND'" >&2; exit 2 ;;
esac
# The Missions backend: stub (default, missions-stub) or real (the operator's service, as uss-enterprise/missions/compose.yaml starts it).
MISSIONS_KIND="${MISSIONS_BACKEND:-stub}"
case "$MISSIONS_KIND" in
  stub|real) ;;
  *) echo "start.sh: MISSIONS_BACKEND must be stub or real, not '$MISSIONS_KIND'" >&2; exit 2 ;;
esac
PORTS="$ROUTER_PORT ${PERSONNEL_ADAPTER_HOST_PORT:-8182} ${MISSIONS_ADAPTER_HOST_PORT:-8183} ${ASSETS_ADAPTER_HOST_PORT:-8184} ${MAPPING_ADAPTER_HOST_PORT:-8190}"
BACKENDS="assets-db assets-bootstrap assets-service personnel-service missions-stub missions-adapter personnel-adapter assets-adapter mapping-adapter"
COMPOSE_FILES=(-f "$COMPOSE_FILE")
if [ "$MISSIONS_KIND" = "real" ]; then
  # The same backends without missions-stub, and the overlay in every compose call, so start, stop and status address the same containers.
  COMPOSE_FILES+=(-f "$REAL_MISSIONS_OVERLAY")
  UP_BACKENDS=""
  for name in $BACKENDS; do
    if [ "$name" != "missions-stub" ]; then UP_BACKENDS="${UP_BACKENDS:+$UP_BACKENDS }$name"; fi
  done
else
  UP_BACKENDS="$BACKENDS"
fi
# The real Missions service, as uss-enterprise/missions/compose.yaml starts it with its defaults.
MISSIONS_CONTAINER="starfleet-missions-service"
MISSIONS_NETWORK="starfleet-missions_default"
MISSIONS_PROBE_URL="http://127.0.0.1:8083/missions?pageSize=1"

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
  MISSIONS_BACKEND=stub|real (default stub, the Missions stub; real: the operator's Missions service on Oracle, through
  federation/stack/missions-real.compose.yaml, without missions-stub; give stop and status the same value as the start),
  APOLLO_ELV2_LICENSE=accept (an Apollo start needs it: Rover's composition plugin is under the Elastic License 2.0 and YOU accept it),
  ROUTER_HOST_PORT (Apollo), COSMO_ROUTER_HOST_PORT (Cosmo), PERSONNEL_ADAPTER_HOST_PORT, MISSIONS_ADAPTER_HOST_PORT, ASSETS_ADAPTER_HOST_PORT, MAPPING_ADAPTER_HOST_PORT,
  SUPERGRAPH_FILE (default federation/routers/apollo/supergraph.graphql, the committed file: start composes it again, so a changed
  schema shows up as a Git diff), EXECUTION_CONFIG_FILE (Cosmo; default federation/routers/cosmo/execution-config.json, the committed
  file, composed again the same way), COMPOSE_PROJECT_NAME, PYTHON (default python).
  Random database credentials are made for the run unless STACK_ASSETS_DB_ADMIN_PASSWORD and STACK_ASSETS_DB_SERVICE_PASSWORD are set;
  the scripts create no credentials file.
The real mode never starts, stops, creates or resets Oracle or the Missions service: the operator starts them first (see the
  Missions README). A real start refuses unless the container starfleet-missions-service runs, the network starfleet-missions_default
  exists, Docker Compose is 2.24.4 or later and http://127.0.0.1:8083/missions?pageSize=1 answers 200 (curl).
--dry-run checks the ports (and, in the real mode, the Missions service) and prints the commands it would run, and runs nothing.
The data: the Assets database lives in memory only while its container runs, so the next start after a stop loads dataset 1.1 again.
Remove the stack (your command, not this script's; compose needs the file's variables, placeholders here, and --profile cosmo removes a Cosmo router too;
set the same COMPOSE_PROJECT_NAME as the start, if you set one):
  SUPERGRAPH_FILE=./unused STACK_ASSETS_DB_ADMIN_PASSWORD=unused STACK_ASSETS_DB_SERVICE_PASSWORD=unused \
    docker compose -f federation/stack/compose.yaml --profile cosmo down --volumes
See federation/stack/README.md, "Status, stop and reset".
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

refuse_real() {
  echo "start.sh: refusing to start with MISSIONS_BACKEND=real: $1" >&2
  exit 1
}

# version_at_least <found> <major> <minor> <patch>: true when found (for example v2.29.1 or 5.5.1) is that version or later.
version_at_least() {
  local found="${1#v}"
  [[ "$found" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+) ]] || return 1
  local major=$((10#${BASH_REMATCH[1]})) minor=$((10#${BASH_REMATCH[2]})) patch=$((10#${BASH_REMATCH[3]}))
  (( major > $2 || (major == $2 && (minor > $3 || (minor == $3 && patch >= $4))) ))
}

# Read-only checks of the real mode, before anything starts; each refusal is one line that names the operator's step.
check_real_missions() {
  local running version status
  running="$(docker inspect --type container --format '{{.State.Running}}' "$MISSIONS_CONTAINER" 2>/dev/null)" || running=""
  if [ "$running" != "true" ]; then
    refuse_real "the real Missions service container $MISSIONS_CONTAINER is not running; the operator starts Oracle and then the service first (uss-enterprise/missions/README.md, Explicit operator workflow and Packaging and deployment)"
  fi
  if ! docker inspect --type network --format '{{.Name}}' "$MISSIONS_NETWORK" >/dev/null 2>&1; then
    refuse_real "the network $MISSIONS_NETWORK of the real Missions service does not exist; the operator starts the service first with docker compose -f uss-enterprise/missions/compose.yaml up --detach --build"
  fi
  version="$(docker compose version --short 2>/dev/null)" || version=""
  if ! version_at_least "$version" 2 24 4; then
    refuse_real "missions-real.compose.yaml needs Docker Compose 2.24.4 or later (the !reset tag); found '${version:-none}'"
  fi
  status="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$MISSIONS_PROBE_URL" 2>/dev/null)" || true
  if [ "$status" != "200" ]; then
    refuse_real "the real Missions service does not answer $MISSIONS_PROBE_URL (status ${status:-none})"
  fi
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
    if [ "$MISSIONS_KIND" = "real" ]; then check_real_missions; fi
    export STACK_ASSETS_DB_ADMIN_PASSWORD="${STACK_ASSETS_DB_ADMIN_PASSWORD:-$(random_secret)}"
    export STACK_ASSETS_DB_SERVICE_PASSWORD="${STACK_ASSETS_DB_SERVICE_PASSWORD:-$(random_secret)}"
    run docker compose "${COMPOSE_FILES[@]}" up -d --build --wait --wait-timeout 600 $UP_BACKENDS
    if [ "$ROUTER_KIND" = "cosmo" ]; then
      run "${PYTHON:-python}" -B "$COSMO_COMPOSE_SCRIPT" --out "$EXECUTION_CONFIG"
      run docker compose "${COMPOSE_FILES[@]}" "${PROFILE[@]}" up -d --wait --wait-timeout 120 cosmo-router
    else
      run "${PYTHON:-python}" -B "$COMPOSE_SCRIPT" --out "$SUPERGRAPH"
      run docker compose "${COMPOSE_FILES[@]}" up -d --wait --wait-timeout 120 router
    fi
    ;;
  stop|status)
    # These commands never use a password, but compose still insists that the variables exist.
    export STACK_ASSETS_DB_ADMIN_PASSWORD="${STACK_ASSETS_DB_ADMIN_PASSWORD:-unused}" STACK_ASSETS_DB_SERVICE_PASSWORD="${STACK_ASSETS_DB_SERVICE_PASSWORD:-unused}"
    if [ "$COMMAND" = "stop" ]; then
      run docker compose "${COMPOSE_FILES[@]}" ${PROFILE[@]+"${PROFILE[@]}"} stop --timeout 60
    else
      run docker compose "${COMPOSE_FILES[@]}" ${PROFILE[@]+"${PROFILE[@]}"} ps
    fi
    ;;
  *) echo "start.sh: unknown command: $COMMAND" >&2; fail_usage ;;
esac
