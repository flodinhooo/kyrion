#!/bin/sh
set -eu
umask 077
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
INSTALL_DIR=${KYRION_INSTALL_DIR:-/etc/kyrion/installer-v1}
DATA_DIR=${KYRION_DATA_DIR:-/var/lib/kyrion}
SECRETS_DIR=${KYRION_SECRETS_DIR:-/var/lib/kyrion/secrets}
HOSTNAME=${KYRION_HOSTNAME:-kyrion.local}
RELEASE=${KYRION_RELEASE:-}
JOURNAL="$INSTALL_DIR/install-state.json"
log(){ printf '%s\n' "$1"; }
die(){ log "ERROR $1" >&2; exit 2; }
[ "$(id -u)" -eq 0 ] || die "E_PRIVILEGE: run as root"
[ -n "$RELEASE" ] || die "E_RELEASE: set KYRION_RELEASE to an immutable release"
[ -e "$INSTALL_DIR" ] && die "E_EXISTING_STATE: installation target already exists"
[ -e "$DATA_DIR" ] && [ "$(find "$DATA_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ] && die "E_EXISTING_STATE: data target is not empty"
[ -e "$SECRETS_DIR" ] && [ "$(find "$SECRETS_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ] && die "E_EXISTING_STATE: secrets target is not empty"
mkdir "$INSTALL_DIR" || die "E_CONCURRENT: another installer owns the target"
mkdir -p "$DATA_DIR" "$SECRETS_DIR"
chmod 700 "$INSTALL_DIR" "$SECRETS_DIR"; chmod 750 "$DATA_DIR"
trap 'printf "{\n  \"stage\": \"failed\",\n  \"release\": "%s"\n}\n" "$RELEASE" > "$JOURNAL"' EXIT INT TERM
python3 "$ROOT/preflight.py" --install-dir "$INSTALL_DIR" --data-dir "$DATA_DIR" --secrets-dir "$SECRETS_DIR" --hostname "$HOSTNAME" > "$INSTALL_DIR/preflight.json" || die "E_PREFLIGHT: host does not satisfy requirements"
python3 "$ROOT/bundle.py" "$ROOT/release" "$ROOT/release/manifest.json" > "$INSTALL_DIR/bundle.json" || die "E_BUNDLE: release bundle verification failed"
python3 "$ROOT/configure.py" --secrets-dir "$SECRETS_DIR" --hostname "$HOSTNAME" --release "$RELEASE" --output "$INSTALL_DIR/config.json" > "$INSTALL_DIR/configure.json" || die "E_CONFIG: secure configuration failed"
cp "$ROOT/templates/compose.yml" "$INSTALL_DIR/compose.yml"; cp "$ROOT/templates/Caddyfile" "$DATA_DIR/Caddyfile"
sed -i "s/__KYRION_HOSTNAME__/$HOSTNAME/g; s/__KYRION_RELEASE__/$RELEASE/g; s#__KYRION_DATA_DIR__#$DATA_DIR#g; s#__KYRION_SECRETS_DIR__#$SECRETS_DIR#g" "$INSTALL_DIR/compose.yml" "$DATA_DIR/Caddyfile"
printf '{\n  "stage": "configured",\n  "release": "%s",\n  "hostname": "%s"\n}\n' "$RELEASE" "$HOSTNAME" > "$JOURNAL"
log "Kyrion is configured for https://$HOSTNAME"; log "Read the bootstrap secret from the protected file: $SECRETS_DIR/bootstrap.secret"; log "No secret value is printed or logged."
