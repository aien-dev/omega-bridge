#!/bin/sh
# Native call ABI v1 qualification (docs/NATIVE-ABI.md): one compiled Omega implementation of
# (a*b+c) modulo 2^64, called from C, C++, Python, Rust, Zig and Go. tools/native builds the library
# and writes every language's declarations from the Omega signatures (one generator, src/native.om);
# no caller declares an Omega function by hand. OMEGA_NATIVE_OMC names the seeded compiler; its sha256
# must be the pinned one below. A missing language toolchain is reported NOT_RUN, never PASS.
# Exit 0 only when every run check passed.
set -eu
PIN=734f0a39319fbfa930bcc62cb30dbf06d47d78e126372b74f5baf478e6126b61
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
T=$ROOT/tests/native
O=$ROOT/build/native
OMC=${OMEGA_NATIVE_OMC:?set OMEGA_NATIVE_OMC to the seeded omc (omega seed/out/omc, sha256 $PIN)}
got=$(sha256sum < "$OMC" | cut -d' ' -f1)
[ "$got" = "$PIN" ] || { echo "FAIL omc sha256 $got, pinned $PIN"; exit 1; }
rm -rf "$O"; mkdir -p "$O" "$O/mut"
fails=0; notrun=""
pass() { echo "PASS $1"; }
fail() { echo "FAIL $1"; fails=$((fails + 1)); }
U="madd smadd fill spin mix big hsum"
units=""; for u in $U; do units="$units $T/$u.om"; done
# tools/native: the generator, the units' code, the library source, the header, the python, rust, zig
# and go bindings, then the library built with the header included (a declaration that disagrees with
# its definition fails that build).
if OMEGA_NATIVE_OMC="$OMC" "$ROOT/tools/native" "$O" $units > "$O/tools-native.log" 2>&1; then
  pass "tools/native: library + six bindings ($(cd "$O" && cat omega_native.h omega_native.py omega_native.rs omega_native.zig omega_native.go | sha256sum | cut -c1-16))"
else fail "tools/native"; cat "$O/tools-native.log"; exit 1; fi
GEN=$O/native-gen
# Every caller takes its declarations from the generated file; none types an Omega function itself.
if grep -n -E 'uint32_t omega_|fn omega_|argtypes|CDLL|import "C"' "$T"/caller.* > "$O/hand.log"; then
  fail "a caller declares an Omega function by hand"; cat "$O/hand.log"
else pass "no caller declares an Omega function by hand"; fi
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
    dd if="$O/libomega_native.so" bs=1 skip="$off" count="$(wc -c < "$O/$u.bin")" 2>/dev/null > "$O/$u.emb"
    cmp -s "$O/$u.bin" "$O/$u.emb" || ok=0
    cat "$O/$u.bin" >> "$O/code.bin"
done
if [ $ok = 1 ]; then pass "embedded code == omc output, per unit ($(sha256sum < "$O/code.bin" | cut -c1-16))"
else fail "embedded code differs from omc output"; fi
run() { lang=$1; shift; if "$@" > "$O/$lang.log" 2>&1; then pass "$lang caller ($(grep -c '^PASS' "$O/$lang.log") lines)"; else fail "$lang caller"; cat "$O/$lang.log"; fi; }
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
unitin() { printf '%s' "$1"; printf '\0'; printf '%08d' "$(wc -c < "$O/madd.bin")"; cat "$O/madd.bin"; }
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
rc=0; "$GEN" < "$O/units.in" > "$O/ref.out" 2> /dev/null || rc=$?
if [ "$rc" = 110 ] && [ ! -s "$O/ref.out" ]; then pass "generator refuses a missing output word"; else fail "generator ran without an output word (exit $rc)"; fi
rc=0; "$GEN" java < "$O/units.in" > "$O/ref.out" 2> /dev/null || rc=$?
if [ "$rc" = 110 ] && [ ! -s "$O/ref.out" ]; then pass "generator refuses an unknown output word"; else fail "generator accepted the word java (exit $rc)"; fi
# The other five languages, each built against its generated binding only.
if command -v c++ > /dev/null; then
  bld cpp c++ -std=c++17 -O2 -Wall -Wextra -Werror "$O/caller.cpp" -L"$O" -lomega_native -Wl,-rpath,"$O" -o "$O/caller_cpp" \
    && run cpp "$O/caller_cpp"
else notrun="$notrun c++"; fi
if command -v python3 > /dev/null; then run python python3 -I "$O/caller.py"; else notrun="$notrun python"; fi
if command -v rustc > /dev/null; then
  bld rust rustc -O --edition 2021 "$O/caller.rs" -L "$O" -C link-arg=-Wl,-rpath,"$O" -o "$O/caller_rs" \
    && run rust "$O/caller_rs"
else notrun="$notrun rust"; fi
if command -v zig > /dev/null; then
  bld zig sh -c 'cd "$1" && zig build-exe caller.zig -L. -lomega_native -lc -rpath "$1" -femit-bin=caller_zig' _ "$O" \
    && run zig "$O/caller_zig"
else notrun="$notrun zig"; fi
if command -v go > /dev/null; then
  # Module omegacaller: caller.go (package main) and omeganative/ holding the generated package and the library.
  mkdir -p "$O/go/omeganative"; cp "$O/omega_native.go" "$O/libomega_native.so" "$O/go/omeganative/"; cp "$O/caller.go" "$O/go/"
  bld go sh -c 'cd "$1" && go mod init omegacaller > /dev/null 2>&1 && go build -o caller_go .' _ "$O/go" \
    && run go "$O/go/caller_go"
else notrun="$notrun go"; fi
# Negative control 1: madd's add turned into sub in the embedded code must be caught by the C caller.
frame() { cat "$T/$1.om"; printf '\0'; printf '%08d' "$(wc -c < "$2/$1.bin")"; cat "$2/$1.bin"; }
cp "$O/smadd.bin" "$O/fill.bin" "$O/spin.bin" "$O/mix.bin" "$O/big.bin" "$O/hsum.bin" "$O/mut/"
printf '\003\174\001\233\140\000\002\313\300\003\137\326' > "$O/mut/madd.bin"
for u in $U; do frame $u "$O/mut"; done | "$GEN" c > "$O/mut/omega_native.c"
cc -std=gnu11 -O2 -fPIC -shared -Wl,-soname,libomega_native.so -include "$O/omega_native.h" -o "$O/mut/libomega_native.so" "$O/mut/omega_native.c"
cc -std=gnu11 -O2 -pthread "$O/caller.c" -L"$O/mut" -lomega_native -Wl,-rpath,"$O/mut" -o "$O/mut/caller_c"
if "$O/mut/caller_c" > "$O/mut/c.log" 2>&1; then fail "mutant madd (add -> sub) not caught"
else pass "mutant madd (add -> sub) caught ($(grep -c '^FAIL' "$O/mut/c.log") failing checks)"; fi
# Negative control 2: one wrong scalar type in each generated binding (a one-byte change to the
# generator's text) must be caught by that language's build or run. The real library is used.
gmut() {
  name=$1; ex=$2; w=$3; ext=$4; shift 4; M=$O/mut/$w; mkdir -p "$M"
  sed "$ex" "$ROOT/src/native.om" > "$M/native.om"
  if cmp -s "$M/native.om" "$ROOT/src/native.om"; then fail "mutant $name did not change the generator"; return 0; fi
  if ! "$OMC" < "$M/native.om" > "$M/gen" 2> /dev/null; then fail "mutant $name: generator did not build"; return 0; fi
  chmod +x "$M/gen"
  if ! "$M/gen" "$w" < "$O/units.in" > "$M/omega_native.$ext" 2> /dev/null; then fail "mutant $name: generator refused"; return 0; fi
  if cmp -s "$M/omega_native.$ext" "$O/omega_native.$ext"; then fail "mutant $name: binding unchanged"; return 0; fi
  if "$@" > "$M/check.log" 2>&1; then fail "mutant $name not caught"; else pass "mutant $name caught"; fi
}
gmut "h scalar uint64_t -> uint32_t" 's/, uint64_t o_~/, uint32_t o_~/' h h \
  cc -std=gnu11 -O2 -fPIC -shared -include "$O/mut/h/omega_native.h" -o "$O/mut/h/lib.so" "$O/omega_native.c"
if command -v python3 > /dev/null; then
  gmut "python scalar c_uint64 -> c_uint32" 's/_u64 = ctypes.c_uint64/_u64 = ctypes.c_uint32/' python py \
    sh -c 'cp "$1/caller.py" "$1/libomega_native.so" "$1/mut/python/" && python3 -I "$1/mut/python/caller.py"' _ "$O"
fi
if command -v rustc > /dev/null; then
  gmut "rust scalar u64 -> u32" 's/: u64~: \*mut u64/: u32~: *mut u64/' rust rs \
    sh -c 'cp "$1/caller.rs" "$1/mut/rust/" && rustc -O --edition 2021 "$1/mut/rust/caller.rs" -L "$1" -C link-arg=-Wl,-rpath,"$1" -o "$1/mut/rust/caller_rs" && "$1/mut/rust/caller_rs"' _ "$O"
fi
if command -v zig > /dev/null; then
  gmut "zig scalar u64 -> u32" 's/: u64~: ?\[\*\]u64/: u32~: ?[*]u64/' zig zig \
    sh -c 'cp "$1/caller.zig" "$1/mut/zig/" && cd "$1/mut/zig" && zig build-exe caller.zig -L "$1" -lomega_native -lc -rpath "$1" -femit-bin=caller_zig && ./caller_zig' _ "$O"
fi
if command -v go > /dev/null; then
  gmut "go scalar uint64 -> uint32" 's/ uint64~ unsafe.Pointer/ uint32~ unsafe.Pointer/' go go \
    sh -c 'mkdir -p "$1/mut/go/omeganative" && mv "$1/mut/go/omega_native.go" "$1/mut/go/omeganative/" && cp "$1/libomega_native.so" "$1/mut/go/omeganative/" && cp "$1/caller.go" "$1/mut/go/" && cd "$1/mut/go" && go mod init omegacaller && go build -o caller_go . && ./caller_go' _ "$O"
fi
for l in $notrun; do echo "NOT_RUN $l caller: toolchain not installed"; done
if [ "$fails" -ne 0 ]; then echo "NATIVE-CALL FAIL $fails"; exit 1; fi
echo "NATIVE-CALL PASS (not run:${notrun:- none})"
