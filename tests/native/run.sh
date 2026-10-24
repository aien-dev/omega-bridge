#!/bin/sh
# Native call ABI v1 qualification (docs/NATIVE-ABI.md): one compiled Omega implementation of
# (a*b+c) modulo 2^64, called from C, C++, Python, Rust, Zig and Go through one generated C binding.
# OMEGA_NATIVE_OMC names the seeded compiler; its sha256 must be the pinned one below.
# A missing language toolchain is reported NOT_RUN, never PASS. Exit 0 only when every run check passed.
set -eu
PIN=d0603ff8fc276774ac7b438c27d146123b9a4513547fe9671e36d8e02d183e83
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
for u in madd smadd fill spin; do "$OMC" < "$T/$u.om" > "$O/$u.bin"; done
frame() { cat "$T/$1.om"; printf '\0'; printf '%08d' "$(wc -c < "$2/$1.bin")"; cat "$2/$1.bin"; }
gen() { { frame madd "$1"; frame smadd "$1"; frame fill "$1"; frame spin "$1"; } | "$O/native" > "$1/omega_native.c"; }
gen "$O"
cc -std=gnu11 -O2 -Wall -Wextra -Werror -fPIC -shared -o "$O/libomega_native.so" "$O/omega_native.c"
# The embedded code must be the compiler's bytes, unchanged.
cat "$O/madd.bin" "$O/smadd.bin" "$O/fill.bin" "$O/spin.bin" > "$O/code.bin"
at=$(objdump -t "$O/libomega_native.so" | awk '$NF=="ombr_code_madd"{print $1}')
dd if="$O/libomega_native.so" bs=1 skip=$((0x$at)) count="$(wc -c < "$O/code.bin")" 2>/dev/null > "$O/embedded.bin"
if cmp -s "$O/code.bin" "$O/embedded.bin"; then pass "embedded code == omc output ($(sha256sum < "$O/code.bin" | cut -c1-16))"
else fail "embedded code differs from omc output"; fi
run() { lang=$1; shift; if "$@" > "$O/$lang.log" 2>&1; then pass "$lang caller ($(grep -c '^PASS' "$O/$lang.log") lines)"; else fail "$lang caller"; cat "$O/$lang.log"; fi; }
cp "$T"/caller.* "$O/"
cc -std=gnu11 -O2 -Wall -Wextra -Werror "$O/caller.c" -L"$O" -lomega_native -Wl,-rpath,"$O" -o "$O/caller_c"
run c "$O/caller_c"
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
cp "$O/smadd.bin" "$O/fill.bin" "$O/spin.bin" "$O/mut/"
printf '\003\174\001\233\140\000\002\313\300\003\137\326' > "$O/mut/madd.bin"
gen "$O/mut"
cc -std=gnu11 -O2 -fPIC -shared -o "$O/mut/libomega_native.so" "$O/mut/omega_native.c"
cc -std=gnu11 -O2 "$O/caller.c" -L"$O/mut" -lomega_native -Wl,-rpath,"$O/mut" -o "$O/mut/caller_c"
if "$O/mut/caller_c" > "$O/mut/c.log" 2>&1; then fail "mutant madd (add -> sub) not caught"
else pass "mutant madd (add -> sub) caught ($(grep -c '^FAIL' "$O/mut/c.log") failing checks)"; fi
for l in $notrun; do echo "NOT_RUN $l caller: toolchain not installed"; done
if [ "$fails" -ne 0 ]; then echo "NATIVE-CALL FAIL $fails"; exit 1; fi
echo "NATIVE-CALL PASS (not run:${notrun:- none})"
