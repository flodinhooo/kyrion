#!/bin/sh
set -eu
manifest=${1:?usage: verify-manifest.sh MANIFEST SIGNATURE PUBLIC_KEY}
signature=${2:?usage: verify-manifest.sh MANIFEST SIGNATURE PUBLIC_KEY}
public_key=${3:?usage: verify-manifest.sh MANIFEST SIGNATURE PUBLIC_KEY}
[ -f "$manifest" ] && [ -f "$signature" ] && [ -f "$public_key" ] || { echo 'E_SIGNATURE: required verification input missing' >&2; exit 2; }
openssl pkeyutl -verify -rawin -pubin -inkey "$public_key" -sigfile "$signature" -in "$manifest" >/dev/null
echo 'Manifest signature verified.'
