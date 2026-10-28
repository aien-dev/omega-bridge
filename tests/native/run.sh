#!/bin/sh
# Native call ABI v1 qualification (docs/NATIVE-ABI.md): one compiled Omega implementation of
# (a*b+c) modulo 2^64, called from C, C++, Python, Rust, Zig and Go. tools/native builds the library
# and writes every language's declarations from the Omega signatures (one generator, src/native.om);
# no caller declares an Omega function by hand. OMEGA_NATIVE_OMC names the seeded compiler; its sha256
# must be the one tools/native pins. A missing caller or failed build is never a qualified PASS.
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
T=$ROOT/tests/native
O=$ROOT/build/native
PIN=$(sed -n 's/^PIN=//p' "$ROOT/tools/native")
OMC=${OMEGA_NATIVE_OMC:?set OMEGA_NATIVE_OMC to the seeded omc (omega seed/out/omc, sha256 $PIN)}
got=$(sha256sum < "$OMC" | cut -d' ' -f1)
[ "$got" = "$PIN" ] || { echo "FAIL omc sha256 $got, pinned $PIN"; exit 1; }
rm -rf "$O"; mkdir -p "$O" "$O/mut"
fails=0; notrun=""; ran=""
pass() { echo "PASS $1"; }
fail() { echo "FAIL $1"; fails=$((fails + 1)); }
U="madd smadd fill spin mix big hsum"
units=""; for u in $U; do units="$units $T/$u.om"; done
# tools/native: the generator, the units' code, the library source, the header, the python, rust, zig
# and go bindings, then the library built with the header included (a declaration that disagrees with
# its definition fails that build). Its work/ folder holds the generator and the units' code.
if OMEGA_NATIVE_OMC="$OMC" "$ROOT/tools/native" "$O" $units > "$O/tools-native.log" 2>&1; then
  pass "tools/native: library + six bindings ($(cd "$O" && cat omega_native.h omega_native.py omega_native.rs omega_native.zig omega_native.go | sha256sum | cut -c1-16))"
else fail "tools/native"; cat "$O/tools-native.log"; exit 1; fi
W=$O/work
GEN=$W/native-gen
# A unit outside the subset (here: a uchar result) is refused by name with exit 110, and a previous run's
# outputs in that folder stay as they were: nothing half-written, no scratch left behind.
printf 'fn m a ulong to uchar\nret uchar a\nend\n' > "$O/bad.om"
OMEGA_NATIVE_OMC="$OMC" "$ROOT/tools/native" "$O/keep" "$T/madd.om" > /dev/null 2>&1
h0=$(sha256sum < "$O/keep/omega_native.h")
rc=0; OMEGA_NATIVE_OMC="$OMC" "$ROOT/tools/native" "$O/keep" "$T/madd.om" "$O/bad.om" > "$O/refused.log" 2>&1 || rc=$?
if [ "$rc" = 110 ] && grep -q "refused $O/bad.om" "$O/refused.log" && [ "$(sha256sum < "$O/keep/omega_native.h")" = "$h0" ] \
   && [ -z "$(ls -A "$O/keep" | grep -v -E '^(omega_native\.(c|h|py|rs|zig|go)|libomega_native\.so|work)$')" ]; then
  pass "tools/native refuses a unit outside the subset by name (exit 110), previous outputs untouched"
else fail "tools/native refusal (exit $rc)"; cat "$O/refused.log"; ls -A "$O/keep"; fi
# Every caller takes its declarations from the generated file; none types an Omega function itself.
if grep -n -E 'uint32_t omega_|fn omega_|argtypes|CDLL|import "C"' "$T"/caller.* > "$O/hand.log"; then
  fail "a caller declares an Omega function by hand"; cat "$O/hand.log"
else pass "no caller declares an Omega function by hand"; fi
# The generated header against prototypes written by hand from the contract (tests/native/reference.c),
# independent of the generator: a disagreement is a conflicting-types error.
if cc -std=gnu11 -fsyntax-only -Wall -Wextra -Werror -include "$O/omega_native.h" "$T/reference.c" > "$O/reference.log" 2>&1; then
  pass "generated header agrees with the hand-written reference prototypes"
else fail "generated header disagrees with tests/native/reference.c"; cat "$O/reference.log"; fi
# The embedded code must be the compiler's bytes, unchanged.
# Each unit is read at its symbol, mapped from load address to file offset through its section.
emb() {
    s=$(objdump -t "$1" | awk -v n="ombr_code_$2" '$NF==n{print $1}')
    [ -n "$s" ] || return 1
    objdump -h "$1" | awk '$2 ~ /^\./ {print $3, $4, $6}' | while read -r sz vma fo; do
        if [ $((0x$vma)) -le $((0x$s)) ] && [ $((0x$s)) -lt $((0x$vma + 0x$sz)) ]; then
            echo $((0x$s - 0x$vma + 0x$fo)); break
        fi
    done
}
ok=1; : > "$O/code.bin"
for u in $U; do
    off=$(emb "$O/libomega_native.so" $u)
    if [ -z "$off" ]; then ok=0; continue; fi
    dd if="$O/libomega_native.so" bs=1 skip="$off" count="$(wc -c < "$W/$u.bin")" 2>/dev/null > "$O/$u.emb"
    cmp -s "$W/$u.bin" "$O/$u.emb" || ok=0
    cat "$W/$u.bin" >> "$O/code.bin"
done
if [ $ok = 1 ]; then pass "embedded code == omc output, per unit ($(sha256sum < "$O/code.bin" | cut -c1-16))"
else fail "embedded code differs from omc output"; fi
run() { lang=$1; shift; ran="$ran $lang"; if "$@" > "$O/$lang.log" 2>&1; then pass "$lang caller ($(grep -c '^PASS' "$O/$lang.log") lines)"; else fail "$lang caller"; cat "$O/$lang.log"; fi; }
bld() { lang=$1; shift; if "$@" > "$O/$lang-build.log" 2>&1; then return 0; fi; fail "$lang build"; cat "$O/$lang-build.log"; return 1; }
cp "$T"/caller.* "$O/"
bld c cc -std=gnu11 -O2 -Wall -Wextra -Werror -pthread "$O/caller.c" -L"$O" -lomega_native -Wl,-rpath,"$O" -o "$O/caller_c" \
  && run c "$O/caller_c"
# Branch protection: the library built with BTI enforced, so every indirect branch into it (PLT calls, the
# per-unit entry stubs, the runtime entries) must land on a landing pad. -nostartfiles because this
# system's crti.o has no landing pad in _init; that is the C library's start code, not the binding's.
# Without the entry stubs (commit e7777ca) this caller dies with SIGILL on its first call.
if OMEGA_NATIVE_OMC="$OMC" OMEGA_NATIVE_CFLAGS="-nostartfiles -mbranch-protection=standard -Wl,-z,force-bti" \
    "$ROOT/tools/native" "$O/bti" $units > "$O/bti-native.log" 2>&1 \
  && cmp -s "$O/bti/omega_native.c" "$O/omega_native.c" \
  && bld c-bti cc -std=gnu11 -O2 -Wall -Wextra -Werror -pthread "$O/caller.c" -L"$O/bti" -lomega_native -Wl,-rpath,"$O/bti" -o "$O/bti/caller_c"; then
  if readelf -n "$O/bti/libomega_native.so" | grep -q "feature: BTI"; then run c-bti "$O/bti/caller_c"
  else fail "c-bti build carries no BTI property"; fi
else fail "c-bti library build"; cat "$O/bti-native.log" 2> /dev/null || true; fi
# Generator refusals: names the C side cannot carry give exit 110 and no output, never broken C.
unitin() { printf '%s' "$1"; printf '\0'; printf '%08d' "$(wc -c < "$W/madd.bin")"; cat "$W/madd.bin"; }
refuse() {
  rc=0; "$GEN" c < "$O/ref.in" > "$O/ref.out" 2> /dev/null || rc=$?
  if [ "$rc" = 110 ] && [ ! -s "$O/ref.out" ]; then pass "generator refuses $1"; else fail "generator accepted $1 (exit $rc)"; fi
}
S='a ulong b ulong c ulong to ulong
ret 0
end
'
unitin "fn a-b $S" > "$O/ref.in"; refuse "a unit name that is not a C identifier"
unitin "fn m a ulong a_len ulong c ulong to ulong
ret 0
end
" > "$O/ref.in"; refuse "a parameter name ending in _len"
{ unitin "fn m $S"; unitin "fn m $S"; } > "$O/ref.in"; refuse "a repeated unit name"
unitin "fn m $S" > "$O/ref.in"; rc=0; "$GEN" c < "$O/ref.in" > "$O/ref.out" 2> /dev/null || rc=$?
if [ "$rc" = 0 ] && [ -s "$O/ref.out" ]; then pass "generator accepts the same unit once (control)"
else fail "generator refused the control unit (exit $rc)"; fi
H='fn h x uint to uint
ret x
end

'
unitin "${H}fn m x uint to ulong
ret 0
end
" > "$O/ref.in"; refuse "a last (bound) function with an unsupported parameter type"
unitin "${H}fn m $S" > "$O/ref.in"; rc=0; "$GEN" c < "$O/ref.in" > "$O/ref.out" 2> /dev/null || rc=$?
if [ "$rc" = 0 ] && grep -q 'omega_m(' "$O/ref.out" && ! grep -q 'omega_h(' "$O/ref.out"; then
  pass "generator binds only the last function; an earlier helper of any type stays private"
else fail "generator mishandled a helper before the bound function (exit $rc)"; fi
rc=0; "$GEN" < "$W/units.in" > "$O/ref.out" 2> /dev/null || rc=$?
if [ "$rc" = 110 ] && [ ! -s "$O/ref.out" ]; then pass "generator refuses a missing output word"; else fail "generator ran without an output word (exit $rc)"; fi
rc=0; "$GEN" java < "$W/units.in" > "$O/ref.out" 2> /dev/null || rc=$?
if [ "$rc" = 110 ] && [ ! -s "$O/ref.out" ]; then pass "generator refuses an unknown output word"; else fail "generator accepted the word java (exit $rc)"; fi
# The other five languages, each built against its generated binding only.
if command -v c++ > /dev/null; then
  bld cpp c++ -std=c++17 -O2 -Wall -Wextra -Werror "$O/caller.cpp" -L"$O" -lomega_native -Wl,-rpath,"$O" -o "$O/caller_cpp" \
    && run cpp "$O/caller_cpp"
else notrun="$notrun c++"; fi
if command -v python3 > /dev/null; then run python python3 -I "$O/caller.py"; else notrun="$notrun python"; fi
if command -v rustc > /dev/null; then
  # The binding declares `unsafe extern "C"` (Rust 1.82 or later), so it reads under edition 2021 and 2024 alike.
  bld rust rustc -O --edition 2021 -D warnings "$O/caller.rs" -L "$O" -C link-arg=-Wl,-rpath,"$O" -o "$O/caller_rs" \
    && run rust "$O/caller_rs"
  bld rust-2024 rustc -O --edition 2024 -D warnings "$O/caller.rs" -L "$O" -C link-arg=-Wl,-rpath,"$O" -o "$O/caller_rs24" \
    && run rust-2024 "$O/caller_rs24"
else notrun="$notrun rust"; fi
if command -v zig > /dev/null; then
  bld zig sh -c 'cd "$1" && zig build-exe caller.zig -L. -lomega_native -lc -rpath "$1" -femit-bin=caller_zig' _ "$O" \
    && run zig "$O/caller_zig"
else notrun="$notrun zig"; fi
if command -v go > /dev/null; then
  # Module omegacaller: caller.go (package main) and omeganative/ holding the generated package, the header
  # and the library. The binding bakes in no run-time path; this build names the folder through CGO_LDFLAGS.
  mkdir -p "$O/go/omeganative"; cp "$O/omega_native.go" "$O/omega_native.h" "$O/libomega_native.so" "$O/go/omeganative/"; cp "$O/caller.go" "$O/go/"
  bld go sh -c 'cd "$1" && go mod init omegacaller > /dev/null 2>&1 && CGO_LDFLAGS="-Wl,-rpath,$1/omeganative" go build -o caller_go .' _ "$O/go" \
    && run go "$O/go/caller_go"
else notrun="$notrun go"; fi
# Negative control 1: madd's add turned into sub in the embedded code must be caught by the C caller.
frame() { cat "$T/$1.om"; printf '\0'; printf '%08d' "$(wc -c < "$2/$1.bin")"; cat "$2/$1.bin"; }
cp "$W/smadd.bin" "$W/fill.bin" "$W/spin.bin" "$W/mix.bin" "$W/big.bin" "$W/hsum.bin" "$O/mut/"
printf '\003\174\001\233\140\000\002\313\300\003\137\326' > "$O/mut/madd.bin"
for u in $U; do frame $u "$O/mut"; done | "$GEN" c > "$O/mut/omega_native.c"
cc -std=gnu11 -O2 -fPIC -shared -Wl,-soname,libomega_native.so -include "$O/omega_native.h" -o "$O/mut/libomega_native.so" "$O/mut/omega_native.c"
cc -std=gnu11 -O2 -pthread "$O/caller.c" -L"$O/mut" -lomega_native -Wl,-rpath,"$O/mut" -o "$O/mut/caller_c"
if "$O/mut/caller_c" > "$O/mut/c.log" 2>&1; then fail "mutant madd (add -> sub) not caught"
else pass "mutant madd (add -> sub) caught ($(grep -c '^FAIL' "$O/mut/c.log") failing checks)"; fi
# Negative control 2: one wrong scalar type in each generated binding (one word changed on the generator's
# text line) must be caught by that language's build or run, for the stated reason. The real library is used.
gmut() {
  name=$1; ex=$2; w=$3; ext=$4; pat=$5; shift 5; M=$O/mut/$w; mkdir -p "$M"
  sed "$ex" "$ROOT/src/native.om" > "$M/native.om"
  n=$(diff "$ROOT/src/native.om" "$M/native.om" | grep -c '^<' || true)
  if [ "$n" != 1 ]; then fail "mutant $name changed $n generator lines, not 1"; return 0; fi
  if ! "$OMC" < "$M/native.om" > "$M/gen" 2> /dev/null; then fail "mutant $name: generator did not build"; return 0; fi
  chmod +x "$M/gen"
  if ! "$M/gen" "$w" < "$W/units.in" > "$M/omega_native.$ext" 2> /dev/null; then fail "mutant $name: generator refused"; return 0; fi
  if cmp -s "$M/omega_native.$ext" "$O/omega_native.$ext"; then fail "mutant $name: binding unchanged"; return 0; fi
  if "$@" > "$M/check.log" 2>&1; then fail "mutant $name not caught"
  elif grep -q -E "$pat" "$M/check.log"; then
    pass "mutant $name caught: $(grep -m1 -E "$pat" "$M/check.log" | sed 's/^[[:space:]]*//' | cut -c1-80)"
  else fail "mutant $name failed for another reason (expected /$pat/)"; cat "$M/check.log"; fi
}
gmut "h scalar uint64_t -> uint32_t" '/^text tb /s/, uint64_t o_~/, uint32_t o_~/' h h 'conflicting types for' \
  cc -std=gnu11 -O2 -fPIC -shared -include "$O/mut/h/omega_native.h" -o "$O/mut/h/lib.so" "$O/omega_native.c"
if command -v python3 > /dev/null; then
  gmut "python scalar c_uint64 -> c_uint32" '/^text tb /s/return ctypes.c_uint64(v)/return ctypes.c_uint32(v)/' python py '^FAIL madd' \
    sh -c 'cp "$1/caller.py" "$1/libomega_native.so" "$1/mut/python/" && python3 -I "$1/mut/python/caller.py"' _ "$O"
fi
if command -v rustc > /dev/null; then
  gmut "rust scalar u64 -> u32" '/^text tb /s/: u64~: \*mut u64/: u32~: *mut u64/' rust rs 'mismatched types' \
    sh -c 'cp "$1/caller.rs" "$1/mut/rust/" && rustc -O --edition 2021 "$1/mut/rust/caller.rs" -L "$1" -C link-arg=-Wl,-rpath,"$1" -o "$1/mut/rust/caller_rs" && "$1/mut/rust/caller_rs"' _ "$O"
fi
if command -v zig > /dev/null; then
  gmut "zig scalar u64 -> u32" '/^text tb /s/: u64~: ?\[\*\]u64/: u32~: ?[*]u64/' zig zig 'cannot represent integer value|expected type' \
    sh -c 'cp "$1/caller.zig" "$1/mut/zig/" && cd "$1/mut/zig" && zig build-exe caller.zig -L "$1" -lomega_native -lc -rpath "$1" -femit-bin=caller_zig && ./caller_zig' _ "$O"
fi
if command -v go > /dev/null; then
  gmut "go scalar uint64 -> uint32" '/^text tb /s/ uint64~ unsafe.Pointer/ uint32~ unsafe.Pointer/' go go 'cannot use' \
    sh -c 'mkdir -p "$1/mut/go/omeganative" && mv "$1/mut/go/omega_native.go" "$1/mut/go/omeganative/" && cp "$1/omega_native.h" "$1/libomega_native.so" "$1/mut/go/omeganative/" && cp "$1/caller.go" "$1/mut/go/" && cd "$1/mut/go" && go mod init omegacaller && CGO_LDFLAGS="-Wl,-rpath,$1/mut/go/omeganative" go build -o caller_go . && ./caller_go' _ "$O"
fi
if python3 "$T/test_private_symbols.py"; then pass "private linkage and thread isolation"; else fail "private linkage regression"; fi
for l in $notrun; do echo "NOT_RUN $l caller: toolchain not installed"; done
if [ "$fails" -eq 0 ]; then
  for l in c c-bti cpp python rust zig go; do
    case " $ran " in *" $l "*) ;; *) case " $notrun " in *" $l "*) ;; *) fail "$l caller not executed" ;; esac ;; esac
  done
fi
if [ "$fails" -ne 0 ]; then echo "NATIVE-CALL FAIL $fails (not run:${notrun:- none})"; exit 1; fi
if [ -n "$notrun" ]; then echo "NATIVE-CALL NOT_RUN (not run:$notrun)"; exit 1; fi
echo "NATIVE-CALL PASS (not run: none)"
