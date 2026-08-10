#!/usr/bin/env bash
set -euo pipefail

SPACE_URL="${1:?uso: ./deploy/push_space.sh https://huggingface.co/spaces/USUARIO/NOME-DO-SPACE}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cp -R "$ROOT/src" "$STAGE/src"
cp -R "$ROOT/markdown_cursos" "$STAGE/markdown_cursos"
cp -R "$ROOT/markdown_disciplinas" "$STAGE/markdown_disciplinas"
cp -R "$ROOT/markdown_docentes" "$STAGE/markdown_docentes"
cp -R "$ROOT/markdown_regimentos" "$STAGE/markdown_regimentos"
cp -R "$ROOT/jsons_regimentos" "$STAGE/jsons_regimentos"
cp -R "$ROOT/chroma_db_unifesp" "$STAGE/chroma_db_unifesp"
cp "$ROOT/requirements.txt" "$ROOT/start_api.py" "$ROOT/graph_viewer.html" "$ROOT/planner.html" "$STAGE/"
cp "$ROOT/deploy/space/Dockerfile" "$ROOT/deploy/space/start.sh" "$ROOT/deploy/space/README.md" "$ROOT/deploy/space/.gitattributes" "$STAGE/"

find "$STAGE" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

cd "$STAGE"
git init -q -b main
git lfs install --local
git add -A
git commit -q -m "deploy FESP-AI backend"
git remote add space "$SPACE_URL"
git push -f space main

echo "Enviado. Acompanhe o build em $SPACE_URL"
