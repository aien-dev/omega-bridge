#!/bin/sh
# Host file/process glue only; both compiler stages are source-born Omega.
set -eu
cd "$(dirname "$0")/.."
tools/check-build-paths.sh
[ "$(uname -s)/$(uname -m)" = Linux/aarch64 ] || exit 69
[ "$#" = 0 ] || exit 64
P=build/bootstrap/omc
[ "$(sha256sum "$P" | cut -d' ' -f1)" = 191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9 ] || { printf 'device: unqualified parent compiler\n' >&2; exit 65; }
D=$(mktemp -d "$PWD/build/device.XXXXXXXX")
"$P" < src/device/omc.om > "$D/omc"
tools/verify-elf.sh "$D/omc"
chmod 700 "$D/omc"
"$D/omc" < src/device/omc.om > "$D/self"
tools/verify-elf.sh "$D/self"
cmp "$D/omc" "$D/self"
sha256sum src/device/omc.om "$P" "$D/omc" "$D/self" > "$D/lineage.sha256"
printf '%s\n' "$D"
