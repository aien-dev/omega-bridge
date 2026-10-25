#!/bin/sh
# Standalone seeded .om qualification, only on an already authorized AArch64 host.
# No installation, hardware command, DSO/callback qualification, or oracle fallback.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
if [ "$(uname -s):$(uname -m)" != Linux:aarch64 ]; then
    echo 'NOT_RUN seeded GGML policy: requires Linux AArch64; no emulation fallback'
    exit 77
fi
PIN=$(sed -n 's/^PIN=//p' "$ROOT/tools/native")
OMC=${OMEGA_NATIVE_OMC:?set OMEGA_NATIVE_OMC to the existing pinned seeded compiler}
[ "$(sha256sum < "$OMC" | cut -d' ' -f1)" = "$PIN" ] || {
    echo 'FAIL seeded compiler fingerprint mismatch' >&2; exit 1;
}
OUT=$ROOT/build/ggml-native
mkdir -p "$OUT"
cat "$ROOT/adapters/ggml/strict_node.om" "$ROOT/adapters/ggml/strict_snapshot.om" \
    "$ROOT/tests/ggml/placement.om" > "$OUT/placement.om"
"$OMC" < "$OUT/placement.om" > "$OUT/placement.tmp"
file "$OUT/placement.tmp" | grep -q 'ELF 64-bit.*ARM aarch64'
chmod +x "$OUT/placement.tmp"
mv "$OUT/placement.tmp" "$OUT/placement"
"$OUT/placement"
echo 'PASS standalone seeded GGML policy program'
echo 'NOT_RUN GGML callback ABI, whole-graph hook, GPU/model/hardware'
