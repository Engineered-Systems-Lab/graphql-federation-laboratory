#!/usr/bin/env bash
# Read the Personnel v2 SOAP service without hand-writing an envelope or a URL. GetPersonnelMember and
# ListPersonnelMembers only; it never starts, stops or modifies a service.
set -euo pipefail

NS="urn:graphql-federation-lab:personnel:v2"
SOAP="http://schemas.xmlsoap.org/soap/envelope/"
URL="${PERSONNEL_URL:-http://127.0.0.1:8082/soap/personnel-v2}"
URL="${URL%/}"

usage() {
  cat <<'USAGE'
Usage: uss-enterprise/scripts/personnel.sh [--dry-run] <command> [args...]
  get <personnelId>              GetPersonnelMember, for example: get PRS-0001
  list [name=value ...]          ListPersonnelMembers; names: department, dutyStatus, offset, limit
Environment: PERSONNEL_URL (default http://127.0.0.1:8082/soap/personnel-v2)
--dry-run prints the exact request (method, URL, headers, body) and sends nothing.
The dataset is chosen when the service starts (PERSONNEL_DATASET_VERSION), not per request.
Start the service: docker compose -f uss-enterprise/personnel-v2/compose.yaml up --detach --build
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

# The replacements are quoted: an unquoted & in a replacement stands for the matched text in newer bash.
xml_escape() {
  local s="$1" amp='&amp;' lt='&lt;' gt='&gt;'
  s="${s//&/"$amp"}"; s="${s//</"$lt"}"; s="${s//>/"$gt"}"
  printf '%s' "$s"
}

case "$COMMAND" in
  get)
    [ "$#" -eq 1 ] || fail_usage
    ACTION="GetPersonnelMember"
    PAYLOAD="<GetPersonnelMemberRequest xmlns='$NS'><personnelId>$(xml_escape "$1")</personnelId></GetPersonnelMemberRequest>"
    ;;
  list)
    ACTION="ListPersonnelMembers"
    declare -A GIVEN=()
    for arg in "$@"; do
      case "$arg" in
        department=*|dutyStatus=*|offset=*|limit=*)
          NAME="${arg%%=*}"
          [ -z "${GIVEN[$NAME]+x}" ] || { echo "personnel.sh: $NAME given twice" >&2; fail_usage; }
          GIVEN[$NAME]="${arg#*=}" ;;
        *) echo "personnel.sh: unknown list argument: $arg" >&2; fail_usage ;;
      esac
    done
    CHILDREN=""
    # The element order is the one of the contract's sequence.
    for NAME in department dutyStatus offset limit; do
      if [ -n "${GIVEN[$NAME]+x}" ]; then CHILDREN+="<$NAME>$(xml_escape "${GIVEN[$NAME]}")</$NAME>"; fi
    done
    PAYLOAD="<ListPersonnelMembersRequest xmlns='$NS'>$CHILDREN</ListPersonnelMembersRequest>"
    ;;
  *) echo "personnel.sh: unknown command: $COMMAND" >&2; fail_usage ;;
esac

BODY="<s:Envelope xmlns:s='$SOAP'><s:Body>$PAYLOAD</s:Body></s:Envelope>"
SOAP_ACTION="\"$NS:$ACTION\""

if [ "$DRY" -eq 1 ]; then
  printf 'POST %s\nContent-Type: text/xml; charset=utf-8\nSOAPAction: %s\n\n%s\n' "$URL" "$SOAP_ACTION" "$BODY"
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
curl -sS --max-time 30 -X POST -H 'Content-Type: text/xml; charset=utf-8' -H "SOAPAction: $SOAP_ACTION" \
  --data-binary "$BODY" -o "$TMP/body" -w '%{http_code}' "$URL" >"$TMP/status" 2>"$TMP/error"
RC=$?
set -e
if [ "$RC" -eq 6 ] || [ "$RC" -eq 7 ]; then
  echo "The personnel service is not running at $URL; start it with: docker compose -f uss-enterprise/personnel-v2/compose.yaml up --detach --build" >&2
  exit 3
fi
if [ "$RC" -ne 0 ]; then cat "$TMP/error" >&2; exit 1; fi

STATUS="$(cat "$TMP/status")"
pretty <"$TMP/body"
echo "HTTP $STATUS" >&2
[ "$STATUS" -lt 400 ] || exit 1
