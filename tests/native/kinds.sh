#!/bin/sh
# f32 and ushort array kinds of the native call ABI (docs/NATIVE-ABI.md): two Omega units with f32/ushort
# view and edit arrays, called from C and compared to C-computed values, the refusals for those kinds,
# and a negative control (fsum's add turned into sub) that must fail. Same pinned compiler as run.sh.
set -eu
PIN=734f0a39319fbfa930bcc62cb30dbf06d47d78e126372b74f5baf478e6126b61
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
T=$ROOT/tests/native
O=$ROOT/build/native-kinds
OMC=${OMEGA_NATIVE_OMC:?set OMEGA_NATIVE_OMC to the seeded omc (omega seed/out/omc, sha256 $PIN)}
got=$(sha256sum < "$OMC" | cut -d' ' -f1)
[ "$got" = "$PIN" ] || { echo "FAIL omc sha256 $got, pinned $PIN"; exit 1; }
rm -rf "$O"; mkdir -p "$O/mut"
"$OMC" < "$ROOT/src/native.om" > "$O/native"; chmod +x "$O/native"
build() {  # build <dir> <fsum source>
  "$OMC" < "$2" > "$1/fsum.bin"; "$OMC" < "$T/halve.om" > "$1/halve.bin"
  { cat "$2"; printf '\0'; printf '%08d' "$(wc -c < "$1/fsum.bin")"; cat "$1/fsum.bin"
    cat "$T/halve.om"; printf '\0'; printf '%08d' "$(wc -c < "$1/halve.bin")"; cat "$1/halve.bin"; } | "$O/native" > "$1/omega_native.c"
  cc -std=gnu11 -O2 -Wall -Wextra -Werror -o "$1/kinds" "$T/kinds.c" "$1/omega_native.c"
}
build "$O" "$T/fsum.om"
"$O/kinds"
sed 's/^put d i add get a i bitcast f32 h2b get h i$/put d i sub get a i bitcast f32 h2b get h i/' "$T/fsum.om" > "$O/mut/fsum.om"
grep -q '^put d i sub' "$O/mut/fsum.om" || { echo "FAIL mutant not applied"; exit 1; }
build "$O/mut" "$O/mut/fsum.om"
if "$O/mut/kinds" > "$O/mut/log" 2>&1; then echo "FAIL mutant fsum (add -> sub) not caught"; exit 1; fi
echo "PASS mutant fsum (add -> sub) caught ($(grep -c '^FAIL' "$O/mut/log") failing checks)"
echo "NATIVE-KINDS PASS"
