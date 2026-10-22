#!/usr/bin/env bash
# Read the Missions REST service without hand-writing a URL. GET only: the write methods need the audit headers and
# are not wrapped. It never starts, stops or modifies a service.
set -euo pipefail

URL="${MISSIONS_URL:-http://127.0.0.1:8083}"
URL="${URL%/}"

usage() {
  cat <<'USAGE'
Usage: scripts/missions.sh [--dry-run] <command> [args...]
  list [name=value ...]    GET /missions; names: type, classification, status, priority, issuingAuthority,
                           commandingOfficerId, assignedCrewId, assignedAssetId, locationType, page, pageSize
  get <missionId>          GET /missions/{id}
  changes <missionId>      GET /missions/{id}/changes
Environment: MISSIONS_URL (default http://127.0.0.1:8083)
The HTTP status and the ETag go to standard error. --dry-run prints the exact request and sends nothing.
Start the service: docker compose -f uss-enterprise/missions/compose.yaml up --detach --build
  (needs MISSIONS_JDBC_URL, MISSIONS_DB_USER, MISSIONS_DB_PASSWORD and the provisioned Oracle network)
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
[ "$#" -ge 1 ] || fail_usage
COMMAND="$1"
shift

urlenc() {
  local LC_ALL=C s="$1" i c out=""
  for ((i = 0; i < ${#s}; i++)); do
    c="${s:i:1}"
    case "$c" in
      [A-Za-z0-9._~-]) out+="$c" ;;
      *) out+="$(printf '%%%02X' "'$c")" ;;
    esac
  done
  printf '%s' "$out"
}

case "$COMMAND" in
  get|changes)
    [ "$#" -eq 1 ] || fail_usage
    TARGET="/missions/$(urlenc "$1")"
    [ "$COMMAND" = "get" ] || TARGET+="/changes"
    ;;
  list)
    TARGET="/missions"
    SEPARATOR="?"
    for arg in "$@"; do
      case "$arg" in
        type=*|classification=*|status=*|priority=*|issuingAuthority=*|commandingOfficerId=*|assignedCrewId=*|assignedAssetId=*|locationType=*|page=*|pageSize=*)
          TARGET+="$SEPARATOR${arg%%=*}=$(urlenc "${arg#*=}")"
          SEPARATOR="&" ;;
        *) echo "missions.sh: unknown list argument: $arg" >&2; fail_usage ;;
      esac
    done
    ;;
  *) echo "missions.sh: unknown command: $COMMAND" >&2; fail_usage ;;
esac

if [ "$DRY" -eq 1 ]; then
  printf 'GET %s%s\nAccept: application/xml\n' "$URL" "$TARGET"
  exit 0
fi

# Pretty-print the XML on standard input: xmllint when present, else Python's standard library through the shim host
# of claims.sh (never a bare python, which may be LibreOffice's). Anything that is not XML is passed through.
pretty() {
  if command -v xmllint >/dev/null 2>&1; then xmllint --format - && return; fi
  local host=""
  if command -v py >/dev/null 2>&1; then host="py -3"
  elif command -v python3 >/dev/null 2>&1; then host="python3"
  elif command -v python >/dev/null 2>&1; then host="python"
  fi
  if [ -z "$host" ]; then cat; return; fi
  $host -c '
import sys, xml.dom.minidom as m
data = sys.stdin.buffer.read()
try:
    text = m.parseString(data).toprettyxml(indent="  ")
except Exception:
    sys.stdout.buffer.write(data)
    sys.exit(0)
sys.stdout.buffer.write(("\n".join(l for l in text.splitlines() if l.strip()) + "\n").encode("utf-8"))
'
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
set +e
curl -sS --max-time 30 -H 'Accept: application/xml' -D "$TMP/headers" -o "$TMP/body" -w '%{http_code}' \
  "$URL$TARGET" >"$TMP/status" 2>"$TMP/error"
RC=$?
set -e
if [ "$RC" -eq 6 ] || [ "$RC" -eq 7 ]; then
  echo "The missions service is not running at $URL; start it with: docker compose -f uss-enterprise/missions/compose.yaml up --detach --build" >&2
  exit 3
fi
if [ "$RC" -ne 0 ]; then cat "$TMP/error" >&2; exit 1; fi

STATUS="$(cat "$TMP/status")"
pretty <"$TMP/body"
echo "HTTP $STATUS" >&2
tr -d '\r' <"$TMP/headers" | grep -i '^etag:' >&2 || true
[ "$STATUS" -lt 400 ] || exit 1
