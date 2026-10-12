#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
printf 'isolated-test-artifact\n' > "$TMP/image.tar"
python3 - "$TMP" <<'PY'
import hashlib,json,sys,pathlib
p=pathlib.Path(sys.argv[1]); a=p/'image.tar'; (p/'manifest.json').write_text(json.dumps({'schemaVersion':1,'release':'test-0.0.0','architecture':'linux/arm64','artifacts':[{'name':a.name,'sha256':hashlib.sha256(a.read_bytes()).hexdigest(),'bytes':a.stat().st_size}]})+'\n')
PY
openssl genpkey -algorithm ED25519 -out "$TMP/private.pem" >/dev/null 2>&1
openssl pkey -in "$TMP/private.pem" -pubout -out "$TMP/public.pem" >/dev/null 2>&1
"$ROOT/sign-manifest.sh" "$TMP/manifest.json" "$TMP/private.pem" "$TMP/manifest.sig"
"$ROOT/verify-manifest.sh" "$TMP/manifest.json" "$TMP/manifest.sig" "$TMP/public.pem"
sed -i 's/test-0.0.0/test-tampered/' "$TMP/manifest.json"
if "$ROOT/verify-manifest.sh" "$TMP/manifest.json" "$TMP/manifest.sig" "$TMP/public.pem" >/dev/null 2>&1; then echo 'E_TEST: tampered manifest accepted' >&2; exit 1; fi
echo 'Isolated signature tests passed.'
