#!/bin/sh
set -eu
R=$HOME/workspace/omega-cuda-cpp-frontend
H=$HOME/handoffs/cuda-cpp-L605
mkdir "$H/gpu-source"
git -C "$R" archive 0e0b486c300c78ed335b26e86b1fed29d858adad | tar -x -C "$H/gpu-source"
cd "$H/gpu-source"
CUDA_CPP_CUDAPP_SOURCE="$HOME/workspace/cudapp" tools/test-native.sh > "$H/gpu-full-suite.log" 2>&1
printf 'GPU_COLD_FULL_SUITE_RC=0\n'
tools/install.sh --offline --prefix "$H/gpu-candidate" > "$H/gpu-candidate-install.log" 2>&1
cd "$H"
strace -f -qq -e trace=execve -o "$H/gpu-command-exec.trace" "$H/gpu-candidate/bin/om" build --from cuda-cpp --target sm_121-lab "$H/gpu-source/tests/cuda-cpp/vector.cu" -o "$H/vector-sm121.omgpu"
printf 'NATIVE_GPU_LAB_BUILD_RC=0\n'
set +e
"$H/gpu-candidate/bin/om" run --from cuda-cpp --target sm_121-lab "$H/gpu-source/tests/cuda-cpp/vector.cu" > "$H/gpu-launch-refusal.out" 2> "$H/gpu-launch-refusal.err"
rc=$?
set -e
[ "$rc" = 69 ]
[ ! -s "$H/gpu-launch-refusal.out" ]
printf 'UNQUALIFIED_LAUNCH_REFUSAL_RC=%s\n' "$rc"
cmp "$R/build/native/cuda-cpp" "$H/gpu-source/build/native/cuda-cpp"
sha256sum "$H/gpu-candidate/lib/omega-native/omc" "$H/gpu-candidate/lib/omega-native/cuda-cpp" "$H/vector-sm121.omgpu" > "$H/gpu-binaries.sha256"
printf 'GPU_COLD_REPLAY_RC=0; HARDWARE_NOT_RUN\n'
