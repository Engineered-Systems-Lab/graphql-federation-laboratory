#!/usr/bin/env sh
# Explicit stopped-service reset; Python owns validation and operator mechanics.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python -B "$HERE/missions_operator.py" reset "$@"
