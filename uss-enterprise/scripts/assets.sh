#!/usr/bin/env bash
# Read the Assets REST service without hand-writing a URL. GET only: the service answers every other method with 405.
# It never starts, stops or modifies a service.
set -euo pipefail

URL="${ASSETS_URL:-http://127.0.0.1:8084}"
URL="${URL%/}"

usage() {
  cat <<'USAGE'
Usage: uss-enterprise/scripts/assets.sh [--dry-run] <command> [args...]
  list [name=value ...]    GET /assets; names: kind, category, status, parentAssetId, offset, limit
  get <assetId>            GET /assets/{id}, for example: get AST-0017
Environment: ASSETS_URL (default http://127.0.0.1:8084)
The HTTP status and the ETag, if the service sends one, go to standard error. --dry-run prints the exact request and
sends nothing.
Start the service: bash uss-enterprise/assets/start.sh start
  (needs ASSETS_DB_ADMIN_PASSWORD and ASSETS_DB_SERVICE_PASSWORD)
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
  get)
    [ "$#" -eq 1 ] || fail_usage
    TARGET="/assets/$(urlenc "$1")"
    ;;
  list)
    TARGET="/assets"
    SEPARATOR="?"
    for arg in "$@"; do
      case "$arg" in
        kind=*|category=*|status=*|parentAssetId=*|offset=*|limit=*)
          TARGET+="$SEPARATOR${arg%%=*}=$(urlenc "${arg#*=}")"
          SEPARATOR="&" ;;
        *) echo "assets.sh: unknown list argument: $arg" >&2; fail_usage ;;
      esac
    done
    ;;
  *) echo "assets.sh: unknown command: $COMMAND" >&2; fail_usage ;;
esac

if [ "$DRY" -eq 1 ]; then
  printf 'GET %s%s\nAccept: application/json\n' "$URL" "$TARGET"
  exit 0
fi

# Pretty-print the JSON on standard input through Python's standard library, using the shim host of claims.sh (never a
# bare python, which may be LibreOffice's). Anything that is not JSON is passed through.
pretty() {
  local host=""
  if command -v py >/dev/null 2>&1; then host="py -3"
  elif command -v python3 >/dev/null 2>&1; then host="python3"
  elif command -v python >/dev/null 2>&1; then host="python"
  fi
  if [ -z "$host" ]; then cat; return; fi
  $host -c '
import json, sys
data = sys.stdin.buffer.read()
try:
    text = json.dumps(json.loads(data.decode("utf-8")), indent=2, ensure_ascii=False)
except Exception:
    sys.stdout.buffer.write(data)
    sys.exit(0)
sys.stdout.buffer.write((text + "\n").encode("utf-8"))
'
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
set +e
curl -sS --max-time 30 -H 'Accept: application/json' -D "$TMP/headers" -o "$TMP/body" -w '%{http_code}' \
  "$URL$TARGET" >"$TMP/status" 2>"$TMP/error"
RC=$?
set -e
if [ "$RC" -eq 6 ] || [ "$RC" -eq 7 ]; then
  echo "The assets service is not running at $URL; start it with: bash uss-enterprise/assets/start.sh start" >&2
  exit 3
fi
if [ "$RC" -ne 0 ]; then cat "$TMP/error" >&2; exit 1; fi

STATUS="$(cat "$TMP/status")"
pretty <"$TMP/body"
echo "HTTP $STATUS" >&2
tr -d '\r' <"$TMP/headers" | grep -i '^etag:' >&2 || true
[ "$STATUS" -lt 400 ] || exit 1
