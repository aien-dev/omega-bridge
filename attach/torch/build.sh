#!/bin/sh
# Link CUDA++'s libomega_gpu.a (built with -fPIC: make CC="gcc -fPIC" OUT_DIR=build-pic libomega_gpu) into the one
# shared object cudapp_torch.py loads. usage: build.sh CUDAPP_LIB_A [OUT_SO]
# The archive must carry omega_gpu_gemm_ex (CUDApp gemm_ex, build switch CUDAPP_MIGRATION_PENDING_GEMM_EX=1).
set -eu
A=${1:?usage: build.sh libomega_gpu.a [out.so]}
O=${2:-$(dirname "$0")/libcudapp_attach.so}
nm "$A" | grep -q ' T omega_gpu_gemm_ex$' || { echo "FAIL $A has no omega_gpu_gemm_ex" >&2; exit 1; }
cc -shared -o "$O" -Wl,--whole-archive "$A" -Wl,--no-whole-archive -lpthread -lm
echo "BUILT $O from $A (sha256 $(sha256sum < "$A" | cut -c1-16))"
