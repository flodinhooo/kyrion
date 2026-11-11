#!/bin/sh
# Interactive local entrypoint; all writes occur after the reviewed approval.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$ROOT/guided.py" "$@"
