#!/bin/sh
set -eu
VERSION=${1:?usage: build-bundle.sh VERSION OUTPUT_DIRECTORY}
OUT=${2:?usage: build-bundle.sh VERSION OUTPUT_DIRECTORY}
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
case "$VERSION" in *latest*|*[^A-Za-z0-9._-]*) echo 'E_RELEASE: immutable version required' >&2; exit 2;; esac
mkdir -p "$OUT"
docker buildx build --platform linux/arm64 --load --tag "kyrion/core:$VERSION" "$ROOT/services/core"
docker buildx build --platform linux/arm64 --load --tag "kyrion/web:$VERSION" "$ROOT/apps/web"
docker pull --platform linux/arm64 postgres:17.6-alpine
docker pull --platform linux/arm64 caddy:2.10.2-alpine
docker image save --output "$OUT/kyrion-core-arm64.tar" "kyrion/core:$VERSION"
docker image save --output "$OUT/kyrion-web-arm64.tar" "kyrion/web:$VERSION"
docker image save --output "$OUT/postgres-arm64.tar" postgres:17.6-alpine
docker image save --output "$OUT/caddy-arm64.tar" caddy:2.10.2-alpine
python3 - "$VERSION" "$OUT" <<'PY'
import hashlib, json, pathlib, sys
version, directory = sys.argv[1], pathlib.Path(sys.argv[2])
artifacts=[]
for path in sorted(directory.glob("*.tar")):
    artifacts.append({"name":path.name,"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"bytes":path.stat().st_size})
if len(artifacts) != 4: raise SystemExit("E_ARTIFACTS: expected four image archives")
(directory/"manifest.json").write_text(json.dumps({"schemaVersion":1,"release":version,"architecture":"linux/arm64","artifacts":artifacts},separators=(",",":"))+"\n",encoding="utf-8")
PY
echo "Created unsigned ARM64 bundle in $OUT"
