#!/usr/bin/env bash
# Use ONLY after creating a NEW EMPTY public repository with the exact name below.
# Operates only on this extracted repository package. Does not change installed tools.
set -euo pipefail
ROOT="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
OWNER="Hellfire13666"
REPO="ALIASTORM-STORM-REBORN"
REMOTE="https://github.com/${OWNER}/${REPO}.git"

if ! command -v git >/dev/null 2>&1; then
  printf 'Git is not installed. Install Git or upload the extracted files through GitHub.\n' >&2
  exit 1
fi
if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  printf 'Stopped: this folder is already in a Git repository. No changes made.\n' >&2
  exit 1
fi
for file in README.md docs/index.html LICENSE-ORIGINAL-ALIASTORM.txt .gitignore; do
  if [[ ! -f "$ROOT/$file" ]]; then printf 'Missing package file: %s\n' "$file" >&2; exit 1; fi
done

printf '\n🌈 ALIASTORM // STORM REBORN // PUBLICATION CHECK\n'
printf 'NEW repository: %s\n' "https://github.com/${OWNER}/${REPO}"
printf 'This is NOT AliaStorm-Favorite. No older repository will be touched.\n'
printf 'Only allowlisted public source, attribution, tests and artwork are staged.\n'
printf 'Research reports, private vaults and credentials will NOT be staged.\n'
printf 'Before continuing, create the new EMPTY PUBLIC repo at https://github.com/new\n'
printf 'Uncheck README, .gitignore and License initialization on GitHub.\n'
read -r -p 'Type PUBLISH to commit and push this NEW repository, or Enter to cancel: ' choice
if [[ "$choice" != 'PUBLISH' ]]; then printf 'Cancelled; nothing changed.\n'; exit 0; fi

cd "$ROOT"
git init -b main
# Repository-specific author only; does not touch your global Git identity.
git config user.name "$OWNER"
git config user.email '79127597+Hellfire13666@users.noreply.github.com'
git remote add origin "$REMOTE"
files=(
  .gitignore README.md ATTRIBUTION.md LICENSE-ORIGINAL-ALIASTORM.txt
  PUBLICATION-CHECKLIST.md PRIVATE-VAULT-README.md
  RUN-ALIASTORM.sh PUBLISH-TO-GITHUB.sh INIT-PRIVATE-VAULT.sh COPY-REPORTS-TO-VAULT.sh
  aliastorm.py site_intel.py report_html.py viewer_menu.py
  PREVIEW-STORM-REBORN.html catalog/original-aliastorm-urls.txt
  assets/storm-reborn.webp docs/.nojekyll docs/index.html
  docs/assets/storm-enchanted.webp docs/assets/storm-interface.webp
  docs/assets/storm-phoenix.webp docs/assets/storm-report.webp docs/assets/storm-share.jpg
  tests/test_aliastorm.py tests/test_bright_rgb.py tests/test_html_report.py
  tests/test_safe_redirects.py tests/test_viewer_menu.py
)
git add -- "${files[@]}"
printf '\nPublishing exactly these files:\n'
git diff --cached --name-only
printf '\n'
git commit -m 'Launch ALIASTORM Storm Reborn public showcase and source'
printf '\nUploading to %s ...\n' "$REMOTE"
if git push -u origin main; then
  printf '\n✅ Repository uploaded.\n'
  printf 'NEXT: GitHub repository Settings → Pages → Deploy from a branch → main → /docs → Save.\n'
  printf 'Expected page after GitHub Pages deploys: https://hellfire13666.github.io/ALIASTORM-STORM-REBORN/\n'
else
  printf '\nUpload did not complete. Your local commit is safe and the older repository is untouched.\n' >&2
  printf 'Check GitHub authentication and that the NEW repository exists, is EMPTY, and you have push access.\n' >&2
  exit 1
fi
