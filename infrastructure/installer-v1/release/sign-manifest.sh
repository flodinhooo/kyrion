#!/bin/sh
set -eu
manifest=${1:?usage: sign-manifest.sh MANIFEST PRIVATE_KEY OUTPUT_SIGNATURE}
key=${2:?usage: sign-manifest.sh MANIFEST PRIVATE_KEY OUTPUT_SIGNATURE}
signature=${3:?usage: sign-manifest.sh MANIFEST PRIVATE_KEY OUTPUT_SIGNATURE}
[ -f "$manifest" ] || { echo 'E_MANIFEST: missing manifest' >&2; exit 2; }
[ -f "$key" ] || { echo 'E_KEY: missing signing key' >&2; exit 2; }
openssl pkeyutl -sign -rawin -inkey "$key" -in "$manifest" -out "$signature"
chmod 0644 "$signature"
