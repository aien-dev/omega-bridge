#!/bin/sh
# Test infrastructure only. Run under quiet-build on a shared host.
set -eu
cd "$(dirname "$0")/.."
mkdir -p evidence/native-commands
tools/bootstrap.sh --offline > evidence/native-commands/bootstrap.log 2>&1
tools/build-native.sh > evidence/native-commands/build.log 2>&1
tools/test.sh > evidence/native-commands/converter.log 2>&1
for suite in gate oracle sign-fixtures whitespace checks robustness; do
    node "seed/math/$suite.mjs" > "evidence/native-commands/math-$suite.log" 2>&1
done
node tests/native/commands.mjs > evidence/native-commands/commands.log 2>&1
node tests/native/review-regression.mjs > evidence/native-commands/review-regression.log 2>&1
node tests/native/provenance.mjs > evidence/native-commands/provenance.log 2>&1
mkdir -p evidence/native-path-safety
L529_REPORT="$PWD/evidence/native-path-safety/full-gate-paths.json" node tests/native/path-safety.mjs > evidence/native-path-safety/full-gate-paths.log 2>&1
printf 'PASS converter, native math, installed commands, source provenance and path safety\n'
