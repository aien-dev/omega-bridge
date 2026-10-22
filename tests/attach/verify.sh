#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-only
# Run from unchanged committed attachment source. Outputs are append-only receipts.
set -eu
cd "$(dirname "$0")/../.."
seed=${1:?usage: verify.sh QUALIFIED_SEED NEW_EVIDENCE_DIRECTORY}
out=${2:?provide a new evidence directory}
[ ! -e "$out" ] || { echo 'evidence directory already exists' >&2; exit 1; }
[ -z "$(git status --porcelain -- cli install tests/attach docs/INSTALL.md docs/ATTACHMENT-CONTRACT.md)" ] || { echo 'commit attachment sources before qualification' >&2; exit 1; }
mkdir -p "$out"
source_sha=$(git rev-parse HEAD)
{
 date -u +%FT%TZ
 printf 'source_sha=%s\n' "$source_sha"
 uname -smr
 id -u
 cc --version
 node --version
} > "$out/environment.txt"
sha256sum "$seed" "$(command -v cc)" "$(cc -print-prog-name=cc1)" "$(command -v node)" "$(command -v sh)" "$(command -v git)" "$(command -v quiet-build)" /usr/bin/desktop-file-validate > "$out/tools.sha256"
sha256sum cli/* install/* tests/attach/* docs/INSTALL.md docs/ATTACHMENT-CONTRACT.md > "$out/sources.sha256"
cat > "$out/commands.txt" <<'COMMANDS'
quiet-build sh cli/build.sh QUALIFIED_SEED
quiet-build node --test --test-reporter=tap tests/attach/attach.test.cjs
quiet-build sh tests/attach/negative-controls.sh QUALIFIED_SEED NEGATIVE_LOG
QUALIFIED_SEED < cli/attachment-policy.om > build/attach/policy-repeat
cmp build/attach/attachment-policy build/attach/policy-repeat
env -i HOME=ISOLATED_EMPTY_HOME PATH=/usr/bin:/bin build/attach/om discover
quiet-build cc -std=c11 -D_GNU_SOURCE -DOMEGA_ATTACH_TESTING -O1 -g -Wall -Wextra -Werror -Wformat=2 -Wshadow -fsanitize=address,undefined -fno-omit-frame-pointer -o build/attach-sanitize/om cli/omega.c cli/discover.c cli/host.c cli/sandbox.c
quiet-build env ATTACH_BINARY=build/attach-sanitize/om ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 node --test --test-reporter=tap tests/attach/attach.test.cjs
COMMANDS
quiet-build sh cli/build.sh "$seed" > "$out/build.log" 2>&1
quiet-build node --test --test-reporter=tap tests/attach/attach.test.cjs > "$out/full-suite.log" 2>&1
quiet-build sh tests/attach/negative-controls.sh "$seed" "$out/negative-policy.log" > "$out/negative-result.log" 2>&1
"$seed" < cli/attachment-policy.om > build/attach/policy-repeat
cmp build/attach/attachment-policy build/attach/policy-repeat
printf 'PASS: byte-identical native policy rebuild\n' > "$out/repeatability.log"
probe_home=$(mktemp -d /tmp/om-real-discovery.XXXXXX)
trap 'rmdir "$probe_home" 2>/dev/null || true' EXIT HUP INT TERM
env -i HOME="$probe_home" PATH=/usr/bin:/bin "$PWD/build/attach/om" discover > "$out/real-discovery.json"
[ -z "$(ls -A "$probe_home")" ] || { echo 'read-only discovery changed isolated HOME' >&2; exit 1; }
printf 'PASS: real PATH inventory left isolated HOME empty; no enrollment\n' > "$out/real-home-check.log"
rmdir "$probe_home"
trap - EXIT HUP INT TERM
jq -r '.inventory[].path' "$out/real-discovery.json" | sort -u | while IFS= read -r p; do sha256sum "$p"; done > "$out/discovered-tools.sha256"
mkdir -p build/attach-sanitize
cp build/attach/attachment-policy build/attach-sanitize/attachment-policy
quiet-build cc -std=c11 -D_GNU_SOURCE -DOMEGA_ATTACH_TESTING -O1 -g -Wall -Wextra -Werror -Wformat=2 -Wshadow -fsanitize=address,undefined -fno-omit-frame-pointer -o build/attach-sanitize/om cli/omega.c cli/discover.c cli/host.c cli/sandbox.c > "$out/sanitizer-build.log" 2>&1
quiet-build env ATTACH_BINARY="$PWD/build/attach-sanitize/om" ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 node --test --test-reporter=tap tests/attach/attach.test.cjs > "$out/sanitizer-suite.log" 2>&1
sha256sum build/attach/om build/attach/attachment-policy build/attach-test/om build/attach-sanitize/om > "$out/artifacts.sha256"
passed=$(sed -n 's/^# pass //p' "$out/full-suite.log")
san_passed=$(sed -n 's/^# pass //p' "$out/sanitizer-suite.log")
jq -n --arg source_sha "$source_sha" --arg seed "$seed" --argjson tests "$passed" --argjson sanitizer_tests "$san_passed" '{source_sha:$source_sha,seed:$seed,platform:"Linux aarch64",result:"PASS",tests:$tests,sanitizer_tests:$sanitizer_tests,negative_policy:"CAUGHT",real_path_discovery:"PASS",isolated_home_restoration:"PASS",macos:"NOT_RUN",windows:"NOT_RUN",graphical_login:"NOT_RUN",headless_restart:"MISSING_IMPLEMENTATION",production_runtime_attachments:"UNSUPPORTED",converter:"NOT_AVAILABLE",actual_account_enrollment:false,parent_L481_acceptance:"OPEN"}' > "$out/receipt.json"
printf 'PASS: %s integration tests, %s sanitizer tests, mutation caught, real discovery, repeatable policy\n' "$passed" "$san_passed"
