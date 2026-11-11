#!/usr/bin/env bash
# Optional setup only. Creates a separate report archive without altering existing scans.
set -euo pipefail
umask 077
VAULT="${ALIASTORM_VAULT_DIR:-${HOME}/.local/share/aliastorm-storm-reborn-vault}"
mkdir -p -- "$VAULT/reports" "$VAULT/notes" "$VAULT/backups"
chmod 700 -- "$VAULT" "$VAULT/reports" "$VAULT/notes" "$VAULT/backups"
printf '\n🌈 ALIASTORM // PRIVATE VAULT READY\n'
printf 'Location: %s\n' "$VAULT"
printf 'Created folders: reports / notes / backups\n'
printf 'No scans copied or moved. Nothing published or uploaded.\n'
