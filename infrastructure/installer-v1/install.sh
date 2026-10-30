#!/bin/sh
set -eu
umask 077
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
INSTALL_DIR=${KYRION_INSTALL_DIR:-/etc/kyrion/installer-v1}
DATA_DIR=${KYRION_DATA_DIR:-/var/lib/kyrion}
SECRETS_DIR=${KYRION_SECRETS_DIR:-/var/lib/kyrion/secrets}
HOSTNAME=${KYRION_HOSTNAME:-kyrion.local}
RELEASE=${KYRION_RELEASE:-}
SIGNATURE=${KYRION_RELEASE_SIGNATURE:-$ROOT/release/manifest.sig}
PUBLIC_KEY=${KYRION_RELEASE_PUBLIC_KEY:-$ROOT/release/release-public.pem}
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
mkdir "$DATA_DIR/knowledge"
chown 10001:10001 "$DATA_DIR/knowledge"
chmod 700 "$DATA_DIR/knowledge"
trap 'printf "{\n  \"stage\": \"failed\",\n  \"release\": "%s"\n}\n" "$RELEASE" > "$JOURNAL"' EXIT INT TERM
python3 "$ROOT/preflight.py" --install-dir "$INSTALL_DIR" --data-dir "$DATA_DIR" --secrets-dir "$SECRETS_DIR" --hostname "$HOSTNAME" > "$INSTALL_DIR/preflight.json" || die "E_PREFLIGHT: host does not satisfy requirements"
python3 "$ROOT/bundle.py" "$ROOT/release" "$ROOT/release/manifest.json" > "$INSTALL_DIR/bundle.json" || die "E_BUNDLE: release bundle verification failed"
[ -f "$SIGNATURE" ] || die "E_SIGNATURE: detached manifest signature is missing"
[ -f "$PUBLIC_KEY" ] || die "E_SIGNATURE: trusted public signing key is missing"
openssl pkeyutl -verify -rawin -pubin -inkey "$PUBLIC_KEY" -sigfile "$SIGNATURE" -in "$ROOT/release/manifest.json" >/dev/null 2>&1 || die "E_SIGNATURE: manifest signature verification failed"
for artifact in "$ROOT"/release/*.tar; do [ -f "$artifact" ] && docker load --input "$artifact" >/dev/null || true; done
python3 "$ROOT/configure.py" --secrets-dir "$SECRETS_DIR" --hostname "$HOSTNAME" --release "$RELEASE" --output "$INSTALL_DIR/config.json" > "$INSTALL_DIR/configure.json" || die "E_CONFIG: secure configuration failed"
cp "$ROOT/templates/compose.yml" "$INSTALL_DIR/compose.yml"; cp "$ROOT/templates/Caddyfile" "$DATA_DIR/Caddyfile"
printf 'KYRION_RELEASE=%s\nKYRION_HOSTNAME=%s\nKYRION_DATA_DIR=%s\nKYRION_SECRETS_DIR=%s\n' "$RELEASE" "$HOSTNAME" "$DATA_DIR" "$SECRETS_DIR" > "$INSTALL_DIR/.env"
chmod 600 "$INSTALL_DIR/.env"
sed -i "s/__KYRION_HOSTNAME__/$HOSTNAME/g" "$DATA_DIR/Caddyfile"
printf '{\n  "stage": "configured",\n  "release": "%s",\n  "hostname": "%s"\n}\n' "$RELEASE" "$HOSTNAME" > "$JOURNAL"
log "Kyrion is configured for https://$HOSTNAME"; log "Read the bootstrap secret from the protected file: $SECRETS_DIR/bootstrap.secret"; log "No secret value is printed or logged."
