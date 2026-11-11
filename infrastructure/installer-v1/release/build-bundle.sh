#!/bin/sh
set -eu
VERSION=${1:?usage: build-bundle.sh VERSION OUTPUT_DIRECTORY}
OUT=${2:?usage: build-bundle.sh VERSION OUTPUT_DIRECTORY}
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
PLATFORM=${3:-linux/arm64}
case "$PLATFORM" in linux/arm64|linux/amd64) ;; *) echo 'E_ARCH: unsupported architecture' >&2; exit 2;; esac
ARCH=${PLATFORM#linux/}
case "$VERSION" in *latest*|*[^A-Za-z0-9._-]*) echo 'E_RELEASE: immutable version required' >&2; exit 2;; esac
mkdir -p "$OUT"
docker buildx build --platform "$PLATFORM" --load --tag "kyrion/core:$VERSION" "$ROOT/services/core"
docker buildx build --platform "$PLATFORM" --load --tag "kyrion/web:$VERSION" "$ROOT/apps/web"
docker pull --platform "$PLATFORM" postgres:17.6-alpine
docker pull --platform "$PLATFORM" caddy:2.10.2-alpine
docker image save --output "$OUT/kyrion-core-$ARCH.tar" "kyrion/core:$VERSION"
docker image save --output "$OUT/kyrion-web-$ARCH.tar" "kyrion/web:$VERSION"
docker image save --output "$OUT/postgres-$ARCH.tar" postgres:17.6-alpine
docker image save --output "$OUT/caddy-$ARCH.tar" caddy:2.10.2-alpine
python3 - "$VERSION" "$OUT" "$PLATFORM" <<'PY'
import hashlib, json, pathlib, sys
version, directory = sys.argv[1], pathlib.Path(sys.argv[2])
artifacts=[]
for path in sorted(directory.glob("*.tar")):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    artifacts.append({"name":path.name,"sha256":digest,"bytes":path.stat().st_size})
if len(artifacts) != 4: raise SystemExit("E_ARTIFACTS: expected four image archives")
(directory/"manifest.json").write_text(json.dumps({"schemaVersion":1,"release":version,"architecture":sys.argv[3],"artifacts":artifacts},separators=(",",":"))+"\n",encoding="utf-8")
PY
echo "Created unsigned $PLATFORM bundle in $OUT"
