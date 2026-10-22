#!/bin/sh
# Test-only external encoder. This is never called by build/install/product paths.
set -eu
cd "$(dirname "$0")/.."
[ -n "${CUDA_CPP_CUDAPP_SOURCE:-}" ] || { printf '%s\n' 'Set CUDA_CPP_CUDAPP_SOURCE to a local canonical CUDApp Git clone for the external test oracle.' >&2; exit 69; }
pin=232332422bfdc31c8918085b50f13c1e18ab702e
git -C "$CUDA_CPP_CUDAPP_SOURCE" cat-file -e "$pin^{commit}"
tools/check-build-paths.sh
out=${CUDA_CPP_ENCODER_OUT:-build/cuda-cpp-reference}
[ ! -e "$out" ] || { printf '%s\n' 'test oracle output already exists; preserve it and select a clean source export' >&2; exit 73; }
mkdir "$out"
git -C "$CUDA_CPP_CUDAPP_SOURCE" archive "$pin" src nvrm m16 | tar -x -C "$out"
cp tests/cuda-cpp/encoder-oracle.c "$out/oracle.c"
gcc -std=c11 -O2 -Wall -Wextra -Werror -DOMEGA_GPU_NO_POSIX -ffunction-sections -fdata-sections -I"$out/src" -I"$out" tests/cuda-cpp/encoder-oracle.c "$out/src/omega_blackwell_codegen.c" -Wl,--gc-sections -o "$out/c-encoder"
sha256sum "$out/src/omega_blackwell_codegen.c" "$out/src/omega_blackwell_codegen.h" "$out/oracle.c" "$out/c-encoder" > "$out/oracle.sha256"
printf 'PASS test-only CUDApp encoder oracle at %s\n' "$pin"
