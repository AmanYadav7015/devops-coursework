#!/usr/bin/env bash
set -euo pipefail

VERSION="${APP_VERSION:-0.0.0-local}"
COMMIT="${GIT_COMMIT:-$(git rev-parse --short HEAD 2>/dev/null || echo unknown)}"
OUT_DIR="${1:-dist}"

echo "[build] packaging yatri-fare-api version=${VERSION} commit=${COMMIT}"

rm -rf "${OUT_DIR}"
mkdir -p "${OUT_DIR}"

cp -R app "${OUT_DIR}/app"
cp requirements.txt "${OUT_DIR}/requirements.txt"
cp Dockerfile "${OUT_DIR}/Dockerfile"
find "${OUT_DIR}" -name '__pycache__' -type d -exec rm -rf {} +

cat > "${OUT_DIR}/build-info.txt" <<INFO
service=yatri-fare-api
version=${VERSION}
commit=${COMMIT}
built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
builder=${BUILDER_NAME:-local-shell}
INFO

tar -czf "${OUT_DIR}/yatri-fare-api-${VERSION}.tar.gz" -C "${OUT_DIR}" app requirements.txt Dockerfile build-info.txt

echo "[build] contents of ${OUT_DIR}"
ls -la "${OUT_DIR}"
echo "[build] done"
