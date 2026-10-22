#!/bin/sh
# Test infrastructure only. Run under quiet-build on a shared host.
set -eu
cd "$(dirname "$0")/.."
mkdir -p evidence/native-commands
tools/bootstrap.sh --offline > evidence/native-commands/bootstrap.log 2>&1
tools/build-native.sh > evidence/native-commands/build.log 2>&1
tools/test.sh > evidence/native-commands/converter.log 2>&1
for suite in gate oracle checks robustness; do
    node "seed/math/$suite.mjs" > "evidence/native-commands/math-$suite.log" 2>&1
done
node tests/native/commands.mjs > evidence/native-commands/commands.log 2>&1
node tests/native/provenance.mjs > evidence/native-commands/provenance.log 2>&1
printf 'PASS converter, native math, installed commands and source provenance\n'
