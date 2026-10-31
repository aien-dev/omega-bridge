#!/bin/sh
# DeepInfer FlopsEstimator::floor_prefix, capped_prefix and pairs as the Omega unit flops_pairs.om:
# differential test against the pinned upstream code, mutants, the flops_estimator-omega.patch harness
# and the native callers (examples/deepinfer/README.md). Environment:
#   DEEPINFER_SRC       a deepseek-ai/DeepInfer checkout at 553741557a57df44a46fb3ab72b6aafeaf945337 (read only)
#   OMEGA_NATIVE_OMC    the seeded omc pinned by tools/native
#   OMEGA_NATIVE_OMC2   the OM-2 compiler (recorded run: omega-mv e5b32567 seed/out/omc, sha256 2c824805...)
#   SEED, RANDOM_N      random-case seed and count for diff.cpp (default 20261031, 1000000)
# Output goes to build/deepinfer. A missing toolchain is NOT_RUN, never PASS. Exit 0 only when every
# check that ran passed.
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
D=$ROOT/examples/deepinfer
O=$ROOT/build/deepinfer
SRC=${DEEPINFER_SRC:?set DEEPINFER_SRC to a DeepInfer checkout at 553741557a57df44a46fb3ab72b6aafeaf945337}
SEED=${SEED:-20261031}
RANDOM_N=${RANDOM_N:-1000000}
PIN_REV=553741557a57df44a46fb3ab72b6aafeaf945337
PIN_HDR=89fbefa41ef0f1ee79be19bb92700d446de38c3781d18227bb0044eb20e7b4f2
PIN_INC=95b16b3dafffb46ac3a3f57f41d9d296436f905e6d0ce9814e9a5ace8cb1c611
OMC=${OMEGA_NATIVE_OMC:?set OMEGA_NATIVE_OMC to the seeded omc pinned by tools/native}
OMC2=${OMEGA_NATIVE_OMC2:?set OMEGA_NATIVE_OMC2 to the OM-2 compiler}
export OMEGA_NATIVE_OMC OMEGA_NATIVE_OMC2 PYTHONDONTWRITEBYTECODE=1
export UBSAN_OPTIONS=print_stacktrace=0
fails=0; notrun=""
pass() { echo "PASS $1"; }
fail() { echo "FAIL $1"; fails=$((fails + 1)); }
sha() { sha256sum < "$1" | cut -d' ' -f1; }
rm -rf "$O"; mkdir -p "$O"

# 0. Inputs: the upstream revision and bytes, and the compilers.
HDR=$SRC/csrc/engine/flops_estimator.hpp
rev=$(git -C "$SRC" rev-parse HEAD 2> /dev/null || echo unknown)
[ "$rev" = "$PIN_REV" ] || { echo "FAIL DeepInfer HEAD $rev, pinned $PIN_REV"; exit 1; }
[ "$(sha "$HDR")" = "$PIN_HDR" ] || { echo "FAIL flops_estimator.hpp sha256 $(sha "$HDR"), pinned $PIN_HDR"; exit 1; }
sed -n 237,257p "$HDR" > "$O/upstream.inc"
[ "$(sha "$O/upstream.inc")" = "$PIN_INC" ] || { echo "FAIL upstream lines 237-257 sha256 $(sha "$O/upstream.inc")"; exit 1; }
echo "INFO DeepInfer $rev csrc/engine/flops_estimator.hpp sha256 $PIN_HDR; lines 237-257 sha256 $PIN_INC"
echo "INFO omc sha256 $(sha "$OMC"); OM-2 compiler sha256 $(sha "$OMC2"); flops_pairs.om sha256 $(sha "$D/flops_pairs.om")"
echo "INFO $(g++ --version | head -n 1)"

# 1. The library and its bindings.
if "$ROOT/tools/native" "$O" "$D/flops_pairs.om" > "$O/tools-native.log" 2>&1; then
  pass "tools/native: flops_pairs.om (OM-2) -> libomega_native.so sha256 $(sha "$O/libomega_native.so") and six bindings"
else fail "tools/native"; cat "$O/tools-native.log"; exit 1; fi
grep -o 'omega-ident [^"]*' "$O/omega_native.h" | head -n 1 | sed 's/^/INFO /'

# 2. Upstream (UBSan) against Omega against the oracles.
UBSAN="-fsanitize=undefined,signed-integer-overflow -fno-sanitize-recover=all"
diffbin() { g++ -std=c++20 -O1 -Wall -Wextra -Werror $UBSAN -I "$1" -I "$O" "$D/diff.cpp" -L"$1" -lomega_native -Wl,-rpath,"$1" -o "$1/diff"; }
diffbin "$O"
if "$O/diff" grid > "$O/grid.log" 2>&1; then pass "C++ grid (upstream = Omega = enumeration)"; else fail "C++ grid"; fi
sed 's/^/  /' "$O/grid.log"
if "$O/diff" random "$SEED" "$RANDOM_N" > "$O/random.log" 2>&1; then pass "C++ random (upstream = Omega = step model = second closed form; overflow -> trap 1)"
else fail "C++ random"; fi
sed 's/^/  /' "$O/random.log"

# boundary BIN: the Omega side of each boundary case; prints the number of failing cases.
boundary() {
  bin=$1; bad=0
  while IFS='|' read -r lhs want; do
    case "$lhs" in '#'* | '') continue;; esac
    want=$(echo $want)
    got=$("$bin" om $lhs 2>&1 || true)
    case "$want" in
      ovf) exp="status 1 value 0 kept 1";;
      dom) exp="status 9 value 0 kept 1";;
      *) exp="status 0 value $want kept 1";;
    esac
    [ "$got" = "$exp" ] || bad=$((bad + 1))
  done
  echo $bad
}
bfails=0; bn=0
while IFS='|' read -r lhs want; do
  case "$lhs" in '#'* | '') continue;; esac
  want=$(echo $want); lhs=$(echo $lhs); bn=$((bn + 1))
  om=$("$O/diff" om $lhs 2>&1 || true)
  up=$("$O/diff" up $lhs 2>&1) && urc=0 || urc=$?
  upline=$(printf '%s\n' "$up" | grep -m 1 -o 'runtime error: .*\|^value .*' || echo "exit $urc")
  case "$want" in
    ovf) ok=0; [ "$om" = "status 1 value 0 kept 1" ] && [ $urc != 0 ] && printf '%s' "$up" | grep -q 'signed integer overflow' && ok=1;;
    dom) ok=0; [ "$om" = "status 9 value 0 kept 1" ] && ok=1;;
    *) ok=0; [ "$om" = "status 0 value $want kept 1" ] && [ "$up" = "value $want" ] && ok=1;;
  esac
  [ $ok = 1 ] || bfails=$((bfails + 1))
  echo "  BOUNDARY $([ $ok = 1 ] && echo ok || echo BAD) $lhs | want $want | omega: $om | upstream: $upline"
done < "$D/boundary.txt"
if [ $bfails = 0 ]; then pass "boundary: $bn cases (values equal; ovf: Omega trap 1 and UBSan signed integer overflow; dom: Omega trap 9)"
else fail "boundary: $bfails of $bn cases"; fi

# 3. The generated Python binding against Python oracles.
if command -v python3 > /dev/null; then
  if python3 -I "$D/diff.py" "$O" "$D/boundary.txt" "$SEED" 200000 > "$O/py.log" 2>&1; then pass "Python binding differential"; else fail "Python binding differential"; fi
  sed 's/^/  /' "$O/py.log"
else notrun="$notrun python-differential"; fi

# 4. flops_estimator-omega.patch: the patched header against the original (no torch: stub TORCH_CHECK).
P=$O/patch; mkdir -p "$P/a" "$P/b"
cp "$HDR" "$P/a/flops_estimator.hpp"; cp "$HDR" "$P/b/flops_estimator.hpp"; chmod u+w "$P/b/flops_estimator.hpp"
if patch -s -p3 -d "$P/b" < "$D/flops_estimator-omega.patch"; then pass "flops_estimator-omega.patch applies to the pinned header (patched sha256 $(sha "$P/b/flops_estimator.hpp"))"
else fail "patch does not apply"; fi
for s in a b; do
  n=$([ $s = a ] && echo orig || echo patched)
  awk '/^    struct QueryRange \{/{on=1} on{print} on&&/int64_t count\(/{c=1} c&&/^    \};/{exit}' "$P/$s/flops_estimator.hpp" > "$P/$n-types.inc"
  awk '/^    \/\/ Sum floor\(t \/ ratio\)/{on=1} on{print} on&&/^        return \{full, consumer\};/{r=1; next} r&&/^    }$/{exit}' "$P/$s/flops_estimator.hpp" > "$P/$n-fns.inc"
done
echo "INFO extracted regions: $(wc -l < "$P/orig-types.inc")+$(wc -l < "$P/orig-fns.inc") original lines, $(wc -l < "$P/patched-types.inc")+$(wc -l < "$P/patched-fns.inc") patched lines"
patchbin() { g++ -std=c++20 -O1 -Wall -Wextra -Werror $UBSAN -I "$P" -I "$1" "$D/patched.cpp" -L"$1" -lomega_native -Wl,-rpath,"$1" -o "$1/patched"; }
patchbin "$O"
if "$O/patched" > "$P/patched.log" 2>&1; then pass "patched header = original on PairTerm::count and query_ranges; Omega traps reach TORCH_CHECK"
else fail "patched header harness"; fi
sed 's/^/  /' "$P/patched.log"
# The whole patched header against the torch C++ headers (syntax only), when a torch install is given.
TORCH_INC=${TORCH_INC:-}
if [ -n "$TORCH_INC" ] && [ -f "$TORCH_INC/torch/extension.h" ]; then
  PYINC=$(python3 -c 'import sysconfig; print(sysconfig.get_paths()["include"])')
  for s in a b; do
    if g++ -std=c++20 -fsyntax-only -w -x c++ -I "$P/$s" -I "$O" -I "$TORCH_INC" -I "$TORCH_INC/torch/csrc/api/include" -I "$PYINC" \
      - < /dev/null -include "$P/$s/flops_estimator.hpp" > "$P/torch-$s.log" 2>&1; then
      pass "whole $([ $s = a ] && echo original || echo patched) header compiles against torch headers ($TORCH_INC)"
    else fail "whole $s header against torch headers"; cat "$P/torch-$s.log"; fi
  done
else notrun="$notrun torch-header-compile"; fi

# 5. Mutants: each must be caught. M1 floor_prefix a = blocks * n; M2 capped_prefix max for min;
# M3 floor_prefix without requires gt ratio 0. Same unit name, own folder.
mutant() {
  M=$O/mut-$1; mkdir -p "$M/src"
  sed "$2" "$D/flops_pairs.om" > "$M/src/flops_pairs.om"
  if cmp -s "$D/flops_pairs.om" "$M/src/flops_pairs.om"; then fail "mutant $1 did not change the unit"; return; fi
  "$ROOT/tools/native" "$M" "$M/src/flops_pairs.om" > "$M/tools-native.log" 2>&1 || { fail "mutant $1 build"; cat "$M/tools-native.log"; return; }
  diffbin "$M"
  "$M/diff" grid > "$M/grid.log" 2>&1 || true
  gm=$(sed -n 's/.*mismatches=//p' "$M/grid.log" | awk '{s+=$1} END {print s+0}')
  bm=$(boundary "$M/diff" < "$D/boundary.txt")
  pm=NOT_RUN
  if [ "$1" = M1 ]; then patchbin "$M"; "$M/patched" > "$M/patched.log" 2>&1 || true; pm=$(sed -n 's/^PATCH total mismatches=//p' "$M/patched.log"); fi
  if [ $((gm + bm)) -gt 0 ]; then pass "mutant $1 caught: grid mismatches=$gm boundary failures=$bm patch-harness mismatches=$pm"
  else fail "mutant $1 not caught (grid $gm, boundary $bm)"; fi
}
mutant M1 's/^a = mul blocks add n 1$/a = mul blocks n/'
mutant M2 's/^if lt n stop$/if gt n stop/'
mutant M3 '13{/^requires gt ratio 0$/d}'

# 6. Native callers. No caller declares an Omega function by hand.
C=$D/callers
if grep -n -E 'uint32_t omega|fn omega|argtypes|CDLL|import "C"' "$C"/caller.* "$D/diff.cpp" "$D/patched.cpp" "$D/diff.py" > "$O/hand.log"; then
  fail "a caller declares an Omega function by hand"; cat "$O/hand.log"
else pass "no caller declares an Omega function by hand"; fi
ran=""
run() { lang=$1; shift; if "$@" > "$O/$lang.log" 2>&1; then pass "$lang caller ($(grep -c '^PASS' "$O/$lang.log") checks)"; ran="$ran $lang"; else fail "$lang caller"; cat "$O/$lang.log"; fi; }
bld() { lang=$1; shift; if "$@" > "$O/$lang-build.log" 2>&1; then return 0; fi; fail "$lang build"; cat "$O/$lang-build.log"; return 1; }
cp "$C"/caller.* "$O/"
if command -v cc > /dev/null; then
  bld c cc -std=gnu11 -O2 -Wall -Wextra -Werror -I "$O" "$O/caller.c" -L"$O" -lomega_native -Wl,-rpath,"$O" -o "$O/caller_c" && run c "$O/caller_c"
  if OMEGA_NATIVE_CFLAGS="-nostartfiles -mbranch-protection=standard -Wl,-z,force-bti" "$ROOT/tools/native" "$O/bti" "$D/flops_pairs.om" > "$O/bti-native.log" 2>&1 \
    && bld c-bti cc -std=gnu11 -O2 -Wall -Wextra -Werror -I "$O/bti" "$O/caller.c" -L"$O/bti" -lomega_native -Wl,-rpath,"$O/bti" -o "$O/bti/caller_c"; then
    if readelf -n "$O/bti/libomega_native.so" | grep -q "feature: BTI"; then run c-bti "$O/bti/caller_c"; else fail "c-bti library carries no BTI property"; fi
  else fail "c-bti library build"; cat "$O/bti-native.log"; fi
else notrun="$notrun c c-bti"; fi
if command -v c++ > /dev/null; then
  bld cpp c++ -std=c++17 -O2 -Wall -Wextra -Werror -I "$O" "$O/caller.cpp" -L"$O" -lomega_native -Wl,-rpath,"$O" -o "$O/caller_cpp" && run cpp "$O/caller_cpp"
else notrun="$notrun cpp"; fi
if command -v python3 > /dev/null; then run python python3 -I "$O/caller.py" "$O"; else notrun="$notrun python"; fi
if command -v rustc > /dev/null; then
  bld rust rustc -O --edition 2021 -D warnings "$O/caller.rs" -L "$O" -C link-arg=-Wl,-rpath,"$O" -o "$O/caller_rs" && run rust "$O/caller_rs"
else notrun="$notrun rust"; fi
if command -v zig > /dev/null; then
  bld zig sh -c 'cd "$1" && zig build-exe caller.zig -L. -lomega_native -lc -rpath "$1" -femit-bin=caller_zig' _ "$O" && run zig "$O/caller_zig"
else notrun="$notrun zig"; fi
if command -v go > /dev/null; then
  G=$O/go; mkdir -p "$G/omeganative"
  cp "$O/omega_native.go" "$O/omega_native.h" "$O/libomega_native.so" "$G/omeganative/"; cp "$O/caller.go" "$G/"
  bld go sh -c 'cd "$1" && go mod init omegacaller > /dev/null 2>&1 && CGO_LDFLAGS="-Wl,-rpath,$1/omeganative" go build -o caller_go .' _ "$G" && run go "$G/caller_go"
else notrun="$notrun go"; fi
[ "$(echo $ran)" = "c c-bti cpp python rust zig go" ] && echo "NATIVE-CALL PASS (c c-bti cpp python rust zig go)"

echo "RESULT failures=$fails NOT_RUN:${notrun:- none}"
[ $fails = 0 ] && echo "DEEPINFER-FLOPS PASS" || echo "DEEPINFER-FLOPS FAIL"
exit $fails
