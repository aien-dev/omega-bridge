#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-only
set -eu
cd "$(dirname "$0")/../.."
seed=${1:?usage: negative-controls.sh QUALIFIED_SEED OUTPUT_LOG}
log=${2:?provide a new output log}
control=build/attach-negative
mkdir -p "$control"
cp build/attach-test/om "$control/om"
# Deliberately make the native core claim ATTACHED before any enrollment.
# The preflight unsupported case still passes; the actual eligibility gate must fail.
sed 's/s = uchar 49/s = uchar 50/' cli/attachment-policy.om > "$control/attachment-policy.om"
"$seed" < "$control/attachment-policy.om" > "$control/attachment-policy"
chmod 755 "$control/attachment-policy"
if ATTACH_BINARY="$PWD/$control/om" node --test --test-reporter=tap --test-name-pattern='fixture handshake gates' tests/attach/attach.test.cjs > "$log" 2>&1; then
  echo 'FAIL: false attachment policy escaped the test gate' >&2
  exit 1
fi
# The named assertion, rather than startup/tooling, must be the failure.
if ! rg -q 'not ok.*fixture handshake gates' "$log" || ! rg -q "ATTACHED" "$log" || ! rg -q "SUPPORTED" "$log"; then
  echo 'FAIL: mutation was not caught by the eligibility assertion' >&2
  exit 1
fi
echo 'PASS: the gate rejects a native core that falsely reports attachment'
