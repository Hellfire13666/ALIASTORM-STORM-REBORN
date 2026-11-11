#!/usr/bin/env bash
# Optional local report copy. Leaves source reports untouched.
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FROM="${1:-${ROOT}/local-reports}"
VAULT="${ALIASTORM_VAULT_DIR:-${HOME}/.local/share/aliastorm-storm-reborn-vault}"
if [[ ! -d "$FROM" ]]; then
 printf 'No report directory found: %s\n' "$FROM" >&2
 exit 1
fi
mkdir -p -- "$VAULT/reports"
chmod 700 -- "$VAULT" "$VAULT/reports"
copied=0
while IFS= read -r -d '' file; do
 name="${file##*/}"
 if [[ ! -e "$VAULT/reports/$name" ]]; then
  cp -- "$file" "$VAULT/reports/$name"
  chmod 600 -- "$VAULT/reports/$name"
  copied=$((copied+1))
 fi
done < <(find "$FROM" -maxdepth 1 -type f \( -name '*.json' -o -name '*.csv' -o -name '*.txt' -o -name '*.html' \) -print0)
printf 'Copied %s new report files. Originals preserved.\n' "$copied"
printf 'Vault: %s\n' "$VAULT/reports"
