#!/bin/sh
# Publishes the PDF reader's workflow to its private GitHub repository (scoremaster-omr), where GitHub Actions runs it
# (2026-10-27). The reader's code is not copied: the workflow checks it out from ScoreMaster's main branch at every
# reading (2026-10-28), so this is only needed when omr/workflow/read-pdf.yml changes.
# Usage: scripts/deploy_omr_worker.sh <user>/<repository>   e.g. scripts/deploy_omr_worker.sh monica/scoremaster-omr
# Before: create the repository (private, empty) on GitHub; `gh auth login` already works on this machine. No secret
# is written here or in the repository: ScoreMaster sends a one-time token with each reading.
set -eu
cd "$(dirname "$0")/.."
repository=${1:?Indica el repositorio: usuario/nombre}
source_commit=$(git rev-parse --short HEAD)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
gh repo clone "$repository" "$work/worker" -- --quiet
find "$work/worker" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
mkdir -p "$work/worker/.github/workflows"
cp omr/workflow/read-pdf.yml "$work/worker/.github/workflows/read-pdf.yml"
cp omr/NOTICE "$work/worker/NOTICE"
cp LICENSE "$work/worker/LICENSE"
printf '# ScoreMaster OMR\n\nLector de PDF de ScoreMaster (copista-2m). El código está en `omr/` del repositorio de ScoreMaster y se\ndescarga de su rama main en cada lectura. Lo lanza ScoreMaster; no se usa a mano.\n' > "$work/worker/README.md"
cd "$work/worker"
# GitHub runs repository_dispatch workflows only on the default branch: main.
git checkout --quiet -B main
# The commit carries GitHub's private address of the account, never a personal email (GitHub refuses it).
noreply=$(gh api user -q '"\(.id)+\(.login)@users.noreply.github.com"')
git config user.email "$noreply"
git config user.name "$(gh api user -q .login)"
git add --all
if git diff --cached --quiet; then
  echo "El repositorio ya tiene esta versión."
  exit 0
fi
git commit --quiet -m "ScoreMaster OMR $source_commit"
git push --quiet origin main
echo "Publicado en https://github.com/$repository: el lector queda listo para las lecturas que lance ScoreMaster."
