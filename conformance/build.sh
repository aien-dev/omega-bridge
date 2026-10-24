#!/bin/sh
# Build the Omega conformance runner against the CUDApp worktree.
set -eu
cd "$(dirname "$0")"
cudapp=${CUDAPP:-../../cudapp}
[ -f "$cudapp/build/libomega_gpu.a" ] || { echo "CUDApp library missing: $cudapp/build/libomega_gpu.a" >&2; exit 1; }
cc -std=gnu11 -Wall -Wextra -Werror -O2 -I"$cudapp/src" -I"$cudapp/m16" -I"$cudapp/nvrm" \
   -I"$cudapp/third_party/nvidia-open-580.173.02/src/common/sdk/nvidia/inc" \
   -o build/omega_runner omega_runner.c "$cudapp/build/libomega_gpu.a" -lpthread -lm
file build/omega_runner
