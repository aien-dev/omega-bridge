#!/bin/sh
set -eu
R=$HOME/workspace/omega-cuda-cpp-frontend
H=$HOME/handoffs/cuda-cpp-L605
mkdir "$H/cold-source"
git -C "$R" archive 9ac729a73bd036633ffccc0c23783fc104866132 | tar -x -C "$H/cold-source"
cd "$H/cold-source"
tools/test-native.sh > "$H/cold-full-suite.log" 2>&1
printf 'COLD_FULL_SUITE_RC=0\n'
tools/install.sh --offline --prefix "$H/candidate" > "$H/candidate-install.log" 2>&1
cd "$H"
"$H/candidate/bin/om" check --from cuda-cpp "$H/cold-source/tests/cuda-cpp/vector.cu"
"$H/candidate/bin/om" build --from cuda-cpp --target cpu-sim "$H/cold-source/tests/cuda-cpp/vector.cu" -o "$H/vector-sim"
printf 'CANDIDATE_BUILD_RC=0\n'
cmp "$R/build/native/cuda-cpp" "$H/cold-source/build/native/cuda-cpp"
sha256sum "$H/candidate/lib/omega-native/omc" "$H/candidate/lib/omega-native/cuda-cpp" "$H/vector-sim" > "$H/cold-binaries.sha256"
printf 'COLD_REPLAY_RC=0\n'
