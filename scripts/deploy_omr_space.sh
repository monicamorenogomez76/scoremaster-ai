#!/bin/sh
# Publishes the PDF reader (omr/) to the author's private Hugging Face Space (2026-10-27).
# Usage: scripts/deploy_omr_space.sh <user>/<space>   e.g. scripts/deploy_omr_space.sh monica/scoremaster-omr
# Before: create the Space (Docker, private) and its secret OMR_TOKEN in its Settings; sign in once with
# `hf auth login` (a write token of your account). No secret is written here or in the Space's files.
set -eu
cd "$(dirname "$0")/.."
space=${1:?Indica el Space: usuario/nombre}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
# The Space repository: its Dockerfile and README at the root, the omr package beside them.
git clone --quiet "https://huggingface.co/spaces/$space" "$work/space"
find "$work/space" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
mkdir "$work/space/omr"
cp omr/__init__.py omr/app.py omr/merge.py omr/requirements.txt omr/NOTICE "$work/space/omr/"
cp omr/Dockerfile "$work/space/Dockerfile"
cp omr/SPACE_README.md "$work/space/README.md"
cp LICENSE "$work/space/LICENSE"
cd "$work/space"
git add --all
if git diff --cached --quiet; then
  echo "El Space ya tiene esta versión."
  exit 0
fi
git commit --quiet -m "ScoreMaster OMR $(git -C "$OLDPWD" rev-parse --short HEAD)"
git push --quiet
echo "Publicado en https://huggingface.co/spaces/$space: Hugging Face construye la imagen (unos 10 minutos)."
