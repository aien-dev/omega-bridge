#!/bin/sh
set -eu
R=$HOME/workspace/omega-cuda-cpp-frontend
H=$HOME/handoffs/cuda-cpp-L605
mkdir "$H/final-source"
git -C "$R" archive d36abe7e94bafce9a20d1be00f9405b23e3f05e2 | tar -x -C "$H/final-source"
cd "$H/final-source"
tools/test-native.sh > "$H/final-full-suite.log" 2>&1
printf 'COLD_FULL_SUITE_RC=0\n'
tools/install.sh --offline --prefix "$H/final-candidate" > "$H/final-final-candidate-install.log" 2>&1
cd "$H"
"$H/final-candidate/bin/om" check --from cuda-cpp "$H/final-source/tests/cuda-cpp/vector.cu"
"$H/final-candidate/bin/om" build --from cuda-cpp --target cpu-sim "$H/final-source/tests/cuda-cpp/vector.cu" -o "$H/final-vector-sim"
printf 'CANDIDATE_BUILD_RC=0\n'
cmp "$R/build/native/cuda-cpp" "$H/final-source/build/native/cuda-cpp"
sha256sum "$H/final-candidate/lib/omega-native/omc" "$H/final-candidate/lib/omega-native/cuda-cpp" "$H/final-vector-sim" > "$H/final-binaries.sha256"
printf 'COLD_REPLAY_RC=0\n'
