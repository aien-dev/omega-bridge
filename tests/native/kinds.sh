#!/bin/sh
# f32 and ushort array kinds of the native call ABI (docs/NATIVE-ABI.md): two Omega units with f32/ushort
# view and edit arrays, called from C and compared to C-computed values, the refusals for those kinds,
# and a negative control (fsum's add turned into sub) that must fail. Same pinned compiler as run.sh.
# The generator's one argument names the output (c, python, rust); a missing argument is a refusal.
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
frame() {  # frame <dir> <fsum source>
  "$OMC" < "$2" > "$1/fsum.bin"; "$OMC" < "$T/halve.om" > "$1/halve.bin"
  { cat "$2"; printf '\0'; printf '%08d' "$(wc -c < "$1/fsum.bin")"; cat "$1/fsum.bin"
    cat "$T/halve.om"; printf '\0'; printf '%08d' "$(wc -c < "$1/halve.bin")"; cat "$1/halve.bin"; }
}
pylib() {  # pylib <dir> <fsum source>: the python word's binding and its library, side by side
  mkdir -p "$1/py"; frame "$1" "$2" | "$O/native" python > "$1/py/omega_native.py"
  frame "$1" "$2" | "$O/native" c > "$1/py/omega_native.c"
  cc -std=gnu11 -O2 -Wall -Wextra -Werror -fPIC -shared -o "$1/py/libomega_native.so" "$1/py/omega_native.c"
}
build() {  # build <dir> <fsum source>
  frame "$1" "$2" | "$O/native" c > "$1/omega_native.c"
  cc -std=gnu11 -O2 -Wall -Wextra -Werror -o "$1/kinds" "$T/kinds.c" "$1/omega_native.c"
}
build "$O" "$T/fsum.om"
"$O/kinds"
# Declaration texts for the same frame. Python names the element types. Rust types f32/ushort as
# byte pointers (docs/NATIVE-ABI.md); a fragment-index overrun would not contain these markers.
frame "$O" "$T/fsum.om" | "$O/native" python > "$O/omega_native.py"
grep -q '_a7 = ctypes.POINTER(ctypes.c_float)' "$O/omega_native.py"
grep -q '_a10 = ctypes.POINTER(ctypes.c_uint16)' "$O/omega_native.py"
grep -q 'omega_fsum.argtypes = \[_res, _a8, _u64, _a10, _u64, _a7, _u64\]' "$O/omega_native.py"
frame "$O" "$T/fsum.om" | "$O/native" rust > "$O/omega_native.rs"
grep -q 'o_a: \*const u8, o_a_len: u64, o_h: \*const u8, o_h_len: u64, o_d: \*mut u8, o_d_len: u64' "$O/omega_native.rs"
# The f32/ushort kinds called through the generated Python binding, with refusal controls.
pylib "$O" "$T/fsum.om"
if python3 -I "$T/pykinds.py" "$O/py" > "$O/py.log" 2>&1; then echo "PASS python binding: f32/ushort calls and refusals ($(grep -c '^PASS' "$O/py.log") checks)"
else echo "FAIL python binding"; cat "$O/py.log"; exit 1; fi
# A uint array is still outside the subset: exit 110, and the previous C file is untouched.
cp "$O/omega_native.c" "$O/keep.c"
printf 'fn bad a view uint 1 to ulong\nret 0\nend\n' > "$O/bad.om"
"$OMC" < "$O/bad.om" > "$O/bad.bin"
rc=0
{ cat "$O/bad.om"; printf '\0'; printf '%08d' "$(wc -c < "$O/bad.bin")"; cat "$O/bad.bin"; } | "$O/native" c > "$O/bad.out" 2>"$O/bad.err" || rc=$?
if [ "$rc" = 110 ] && [ ! -s "$O/bad.out" ] && cmp -s "$O/omega_native.c" "$O/keep.c"; then
  echo "PASS view uint refused (exit 110), previous output untouched"
else
  echo "FAIL view uint refusal (exit $rc)"; cat "$O/bad.err"; exit 1
fi
sed 's/^put d i add get a i bitcast f32 h2b get h i$/put d i sub get a i bitcast f32 h2b get h i/' "$T/fsum.om" > "$O/mut/fsum.om"
grep -q '^put d i sub' "$O/mut/fsum.om" || { echo "FAIL mutant not applied"; exit 1; }
build "$O/mut" "$O/mut/fsum.om"
if "$O/mut/kinds" > "$O/mut/log" 2>&1; then echo "FAIL mutant fsum (add -> sub) not caught"; exit 1; fi
echo "PASS mutant fsum (add -> sub) caught ($(grep -c '^FAIL' "$O/mut/log") failing checks)"
pylib "$O/mut" "$O/mut/fsum.om"
if python3 -I "$T/pykinds.py" "$O/mut/py" > "$O/mut/py.log" 2>&1; then echo "FAIL mutant fsum not caught through the python binding"; exit 1; fi
echo "PASS mutant fsum (add -> sub) caught through the python binding ($(grep -c '^FAIL' "$O/mut/py.log") failing checks)"
echo "NATIVE-KINDS PASS"
