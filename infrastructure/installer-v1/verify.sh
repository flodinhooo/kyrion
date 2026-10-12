#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
INSTALL_DIR=${1:?usage: verify.sh INSTALL_DIR}
test -f "$INSTALL_DIR/compose.yml" || { echo 'E_VERIFY: compose file missing' >&2; exit 2; }
grep -q '443:443' "$INSTALL_DIR/compose.yml" || { echo 'E_VERIFY: HTTPS listener missing' >&2; exit 2; }
test "$(stat -c '%a' "$INSTALL_DIR/config.json")" = 600 || { echo 'E_VERIFY: configuration permissions' >&2; exit 2; }
docker compose -f "$INSTALL_DIR/compose.yml" config --quiet
docker compose -f "$INSTALL_DIR/compose.yml" ps --format json
curl --fail --silent --show-error "https://$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["hostname"])' "$INSTALL_DIR/config.json")/actuator/health" >/dev/null
echo 'Kyrion installer verification passed.'
