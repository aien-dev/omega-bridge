#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
seed=${OMEGA_SEED:-build/bootstrap/omc}
want=191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9
[ "$(sha256sum "$seed" | cut -d' ' -f1)" = "$want" ] || { echo 'seed fingerprint mismatch' >&2; exit 1; }
file "$seed" | grep -q 'ELF 64-bit.*ARM aarch64' || exit 1
mkdir -p build
"$seed" < src/toc.om > build/bridge.tmp
[ -s build/bridge.tmp ]
file build/bridge.tmp | grep -q 'ELF 64-bit.*ARM aarch64'
chmod +x build/bridge.tmp
mv build/bridge.tmp build/bridge
