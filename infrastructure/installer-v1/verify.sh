#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$ROOT/verify.py" "${1:?usage: verify.sh INSTALL_DIR}"
