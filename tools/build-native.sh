#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
tools/check-build-paths.sh
tools/verify-sources.sh
# Shared compiler is always rebuilt from source by the installation entry point.
# This incremental builder consumes only that qualified artifact.
unset OMEGA_SEED
tools/build.sh
B=build/math-native
mkdir -p "$B" build/native
cp build/bootstrap/omc "$B/omc1"
cat seed/math/core.om seed/math/cli.om > "$B/math.om"
build/bootstrap/omc < "$B/math.om" > "$B/omega-math.tmp"
[ -s "$B/omega-math.tmp" ]
for p in build/bootstrap/omc build/bridge "$B/omega-math.tmp"; do
    tools/verify-elf.sh "$p"
done
chmod +x "$B/omega-math.tmp"
mv "$B/omega-math.tmp" "$B/omega-math"
cp build/bootstrap/omc build/native/omc
cp build/bridge build/native/bridge
cp "$B/omega-math" build/native/math
build/bootstrap/omc < src/cuda-cpp.om > build/native/cuda-cpp.tmp
tools/verify-elf.sh build/native/cuda-cpp.tmp
chmod 700 build/native/cuda-cpp.tmp
mv build/native/cuda-cpp.tmp build/native/cuda-cpp
sha256sum build/native/omc build/native/bridge build/native/math build/native/cuda-cpp > build/native.sha256
printf 'PASS native converter and math, shared source-born compiler\n'
