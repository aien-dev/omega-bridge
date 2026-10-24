#!/bin/sh
# Native call ABI v1 qualification (docs/NATIVE-ABI.md): one compiled Omega implementation of
# (a*b+c) modulo 2^64, called from C, C++, Python, Rust, Zig and Go through one generated C binding.
# OMEGA_NATIVE_OMC names the seeded compiler; its sha256 must be the pinned one below.
# A missing language toolchain is reported NOT_RUN, never PASS. Exit 0 only when every run check passed.
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
"$OMC" < "$ROOT/src/native.om" > "$O/native"; chmod +x "$O/native"
U="madd smadd fill spin mix big"
for u in $U; do "$OMC" < "$T/$u.om" > "$O/$u.bin"; done
frame() { cat "$T/$1.om"; printf '\0'; printf '%08d' "$(wc -c < "$2/$1.bin")"; cat "$2/$1.bin"; }
gen() { for u in $U; do frame $u "$1"; done | "$O/native" > "$1/omega_native.c"; }
gen "$O"
cc -std=gnu11 -O2 -Wall -Wextra -Werror -fPIC -shared -o "$O/libomega_native.so" "$O/omega_native.c"
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
cp "$T"/caller.* "$O/"
cc -std=gnu11 -O2 -Wall -Wextra -Werror -pthread "$O/caller.c" -L"$O" -lomega_native -Wl,-rpath,"$O" -o "$O/caller_c"
run c "$O/caller_c"
# Branch protection: the library built with BTI enforced, so every indirect branch into it (PLT calls, the
# per-unit entry stubs, the runtime entries) must land on a landing pad. -nostartfiles because this
# system's crti.o has no landing pad in _init; that is the C library's start code, not the binding's.
# Without the entry stubs (commit e7777ca) this caller dies with SIGILL on its first call.
mkdir -p "$O/bti"
cc -std=gnu11 -O2 -Wall -Wextra -Werror -fPIC -shared -nostartfiles -mbranch-protection=standard \
  -Wl,-z,force-bti -o "$O/bti/libomega_native.so" "$O/omega_native.c" 2> "$O/bti/cc.log"
cc -std=gnu11 -O2 -Wall -Wextra -Werror -pthread "$O/caller.c" -L"$O/bti" -lomega_native -Wl,-rpath,"$O/bti" \
  -o "$O/bti/caller_c"
if readelf -n "$O/bti/libomega_native.so" | grep -q "feature: BTI"; then
  run c-bti "$O/bti/caller_c"
else fail "c-bti build carries no BTI property"; fi
# Generator refusals: names the C side cannot carry give exit 110 and no output, never broken C.
unitin() { printf '%s' "$1"; printf '\0'; printf '%08d' "$(wc -c < "$O/madd.bin")"; cat "$O/madd.bin"; }
refuse() {
  rc=0; "$O/native" < "$O/ref.in" > "$O/ref.out" 2> /dev/null || rc=$?
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
unitin "fn m $S" > "$O/ref.in"; rc=0; "$O/native" < "$O/ref.in" > "$O/ref.out" 2> /dev/null || rc=$?
if [ "$rc" = 0 ] && [ -s "$O/ref.out" ]; then pass "generator accepts the same unit once (control)"
else fail "generator refused the control unit (exit $rc)"; fi
if command -v c++ > /dev/null; then
  c++ -std=c++17 -O2 -Wall -Wextra -Werror "$O/caller.cpp" -L"$O" -lomega_native -Wl,-rpath,"$O" -o "$O/caller_cpp"
  run cpp "$O/caller_cpp"
else notrun="$notrun c++"; fi
if command -v python3 > /dev/null; then run python python3 -I "$O/caller.py"; else notrun="$notrun python"; fi
if command -v rustc > /dev/null; then
  rustc -O --edition 2021 "$O/caller.rs" -L "$O" -C link-arg=-Wl,-rpath,"$O" -o "$O/caller_rs"
  run rust "$O/caller_rs"
else notrun="$notrun rust"; fi
if command -v zig > /dev/null; then
  (cd "$O" && zig build-exe caller.zig -L. -lomega_native -lc -rpath "$O" -femit-bin=caller_zig) && run zig "$O/caller_zig"
else notrun="$notrun zig"; fi
if command -v go > /dev/null; then
  (cd "$O" && go mod init omegacaller > /dev/null 2>&1 && go build -o caller_go caller.go) && run go "$O/caller_go"
else notrun="$notrun go"; fi
# Negative control: madd's add turned into sub must be caught.
cp "$O/smadd.bin" "$O/fill.bin" "$O/spin.bin" "$O/mix.bin" "$O/big.bin" "$O/mut/"
printf '\003\174\001\233\140\000\002\313\300\003\137\326' > "$O/mut/madd.bin"
gen "$O/mut"
cc -std=gnu11 -O2 -fPIC -shared -o "$O/mut/libomega_native.so" "$O/mut/omega_native.c"
cc -std=gnu11 -O2 -pthread "$O/caller.c" -L"$O/mut" -lomega_native -Wl,-rpath,"$O/mut" -o "$O/mut/caller_c"
if "$O/mut/caller_c" > "$O/mut/c.log" 2>&1; then fail "mutant madd (add -> sub) not caught"
else pass "mutant madd (add -> sub) caught ($(grep -c '^FAIL' "$O/mut/c.log") failing checks)"; fi
for l in $notrun; do echo "NOT_RUN $l caller: toolchain not installed"; done
if [ "$fails" -ne 0 ]; then echo "NATIVE-CALL FAIL $fails"; exit 1; fi
echo "NATIVE-CALL PASS (not run:${notrun:- none})"
