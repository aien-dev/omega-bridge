#!/bin/sh
# Build the native Omega GPU adapter with the pinned seed compiler.
# Source-only: no C compiler, assembler or linker participates.
set -eu
cd "$(dirname "$0")/.."
seed=${OMEGA_SEED:-build/omc}
want=191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9
[ -x "$seed" ] || { echo "seed compiler missing: $seed (set OMEGA_SEED)" >&2; exit 1; }
[ "$(sha256sum "$seed" | cut -d' ' -f1)" = "$want" ] || { echo 'seed fingerprint mismatch' >&2; exit 1; }
file "$seed" | grep -q 'ELF 64-bit.*ARM aarch64' || { echo 'seed is not AArch64' >&2; exit 1; }
mkdir -p build
"$seed" < src/gpu_adapter.om > build/gpu-adapter.tmp
[ -s build/gpu-adapter.tmp ] || { echo 'empty compiler output' >&2; exit 1; }
file build/gpu-adapter.tmp | grep -q 'ELF 64-bit.*ARM aarch64' || { echo 'not an AArch64 ELF' >&2; exit 1; }
chmod +x build/gpu-adapter.tmp
mv build/gpu-adapter.tmp build/gpu-adapter
sha256sum src/gpu_adapter.om build/gpu-adapter > build/gpu-adapter.sha256
cat build/gpu-adapter.sha256
