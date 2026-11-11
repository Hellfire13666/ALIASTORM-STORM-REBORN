#!/usr/bin/env bash
set -euo pipefail
HERE="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
# Clear the previously pasted shell command from the terminal display.
# Only do this for an interactive terminal. Redirects and logs are untouched.
if [[ -t 1 && "${TERM:-dumb}" != dumb ]]; then
  printf '\033[2J\033[H'
fi
exec python3 "$HERE/src/aliastorm.py" "$@"
