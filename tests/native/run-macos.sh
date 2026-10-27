#!/bin/sh
# Native call ABI v1 on macOS arm64 (docs/NATIVE-ABI.md, "Platforms"). Two steps, because the seeded
# compiler is a Linux AArch64 executable and cannot run on macOS:
#   1. On Linux AArch64:  OMEGA_NATIVE_OMC=<seeded omc> sh tests/native/run-macos.sh bundle DIR
#      compiles the units, generates the bindings with src/native.om and writes everything the Mac needs
#      into DIR (unit code .bin files, omega_native.c, the add -> sub mutant, the host-word control,
#      the callers and this script).
#   2. On macOS arm64:    sh DIR/run-macos.sh run DIR
#      builds the generated C with clang into libomega_native.dylib and runs the C and Python callers.
# Step 2 needs only clang, the clang tools (nm, otool, llvm objdump) and python3's standard library.
# The last line is NATIVE-CALL-MACOS PASS, FAIL or NOT_RUN; only PASS exits 0.
set -eu
U="madd smadd fill spin mix big hsum"
PIN=734f0a39319fbfa930bcc62cb30dbf06d47d78e126372b74f5baf478e6126b61
mode=${1-}; D=${2-}
[ -n "$D" ] || { echo 'usage: run-macos.sh bundle|run DIR' >&2; exit 64; }
fails=0
pass() { echo "PASS $1"; }
fail() { echo "FAIL $1"; fails=$((fails + 1)); }
case $mode in
bundle)
    ROOT=$(cd "$(dirname "$0")/../.." && pwd)
    T=$ROOT/tests/native
    OMC=${OMEGA_NATIVE_OMC:?set OMEGA_NATIVE_OMC to the seeded omc (sha256 $PIN)}
    got=$(sha256sum < "$OMC" | cut -d' ' -f1)
    [ "$got" = "$PIN" ] || { echo "FAIL omc sha256 $got, pinned $PIN"; exit 1; }
    rm -rf "$D"; mkdir -p "$D/mut" "$D/hostw"
    "$OMC" < "$ROOT/src/native.om" > "$D/native"; chmod +x "$D/native"
    for u in $U; do "$OMC" < "$T/$u.om" > "$D/$u.bin"; done
    frame() { cat "$T/$1.om"; printf '\0'; printf '%08d' "$(wc -c < "$2/$1.bin")"; cat "$2/$1.bin"; }
    for u in $U; do frame $u "$D"; done | "$D/native" > "$D/omega_native.c"
    # The kit entry point must give the same binding from the same sources.
    OMEGA_NATIVE_OMC=$OMC sh "$ROOT/tools/native-binding" $(for u in $U; do echo "$T/$u.om"; done) > "$D/kit.c"
    cmp -s "$D/omega_native.c" "$D/kit.c" || { echo 'FAIL tools/native-binding output differs from the direct generator'; exit 1; }
    # Negative control: madd's add turned into sub (the same mutant as run.sh).
    for u in $U; do [ $u = madd ] || cp "$D/$u.bin" "$D/mut/"; done
    printf '\003\174\001\233\140\000\002\313\300\003\137\326' > "$D/mut/madd.bin"
    for u in $U; do frame $u "$D/mut"; done | "$D/native" > "$D/mut/omega_native.c"
    # Host-word control: a unit whose code makes a Linux system call; its binding must not build on macOS.
    OMEGA_NATIVE_OMC=$OMC sh "$ROOT/tools/native-binding" "$T/hostw.om" > "$D/hostw/omega_native.c"
    cp "$T/caller.c" "$T/caller.py" "$T/run-macos.sh" "$D/"
    rm -f "$D/native" "$D/kit.c"
    (cd "$D" && sha256sum *.bin omega_native.c mut/omega_native.c hostw/omega_native.c) > "$D/SHA256SUMS"
    echo "BUNDLE $D (omc $PIN, generated on $(uname -sm))"
    exit 0 ;;
run) ;;
*) echo 'usage: run-macos.sh bundle|run DIR' >&2; exit 64 ;;
esac
D=$(cd "$D" && pwd)
if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
    echo "NATIVE-CALL-MACOS NOT_RUN (host is $(uname -sm), not Darwin arm64)"; exit 1
fi
for t in clang nm otool objdump python3; do
    command -v $t > /dev/null || { echo "NATIVE-CALL-MACOS NOT_RUN ($t not installed)"; exit 1; }
done
echo "host $(uname -sm) $(sw_vers -productVersion 2> /dev/null || true); $(clang --version | head -n 1)"
export LC_ALL=C
(cd "$D" && shasum -a 256 -c SHA256SUMS > /dev/null) || { echo 'NATIVE-CALL-MACOS FAIL (bundle does not match SHA256SUMS)'; exit 1; }
B=$D/macos; rm -rf "$B"; mkdir -p "$B/mut"
lib() { clang -std=gnu11 -O2 -Wall -Wextra -Werror -fPIC -shared -install_name @rpath/libomega_native.dylib \
    -o "$2/libomega_native.dylib" "$1"; }
caller() { clang -std=gnu11 -O2 -Wall -Wextra -Werror -pthread "$D/caller.c" -L"$1" -lomega_native \
    -Wl,-rpath,"$1" -o "$1/caller_c"; }
lib "$D/omega_native.c" "$B"
pass "clang built libomega_native.dylib ($(otool -hv "$B/libomega_native.dylib" | awk 'END{print $2, $5}'))"
# The embedded code must be the compiler's bytes, unchanged. embeq LIB UNIT BIN compares UNIT's bytes in
# LIB with BIN, mapping the symbol address to a file offset through the __TEXT,__text section.
embeq() {
    sect=$(otool -l "$1" | awk '/sectname __text$/{t=1} t&&$1=="addr"{a=$2} t&&$1=="offset"{print a, $2; exit}')
    s=$(nm "$1" | awk -v n="_ombr_code_$2" '$3==n{print $1}')
    [ -n "$s" ] && [ -n "$sect" ] || return 1
    off=$((0x$s - ${sect% *} + ${sect#* }))
    dd if="$1" bs=1 skip="$off" count="$(wc -c < "$3")" 2> /dev/null > "$B/emb.bin"
    cmp -s "$3" "$B/emb.bin"
}
ok=1
for u in $U; do embeq "$B/libomega_native.dylib" $u "$D/$u.bin" || { ok=0; echo "  $u differs"; }; done
if [ $ok = 1 ]; then pass "embedded code == omc output, per unit ($(cat $(for u in $U; do echo "$D/$u.bin"; done) | shasum -a 256 | cut -c1-16))"
else fail "embedded code differs from omc output"; fi
# macOS reserves x18 (the platform register); the embedded code must neither read nor write it.
# x18dis FILE START LEN prints the instructions of [START, START+LEN) that name x18 or w18.
x18dis() { objdump -d --no-show-raw-insn --start-address="$2" --stop-address=$(($2 + $3)) "$1" | grep -E '^ *[0-9a-f]+:' > "$B/dis.txt" || true
    grep -wE '[xw]18' "$B/dis.txt" || true; }
ok=1; n=0
for u in $U; do
    s=$(nm "$B/libomega_native.dylib" | awk -v n="_ombr_code_$u" '$3==n{print $1}')
    hit=$(x18dis "$B/libomega_native.dylib" $((0x$s)) "$(wc -c < "$D/$u.bin")")
    n=$((n + $(wc -l < "$B/dis.txt")))
    [ -z "$hit" ] || { ok=0; echo "  $u: $hit"; }
done
# Control for the check itself: an instruction that writes x18 must be found.
printf '.text\n.globl _x\n_x:\nmov x18, x0\nret\n' > "$B/x18.s"
clang -c -o "$B/x18.o" "$B/x18.s"
ctl=$(x18dis "$B/x18.o" 0 8)
if [ $ok = 1 ] && [ -n "$ctl" ]; then pass "no x18/w18 in the embedded code ($n instructions; control found: $(echo $ctl | sed 's/^[0-9a-f]*: *//'))"
else fail "x18 check (units clean: $ok; control found: ${ctl:-nothing})"; fi
caller "$B"
if "$B/caller_c" > "$B/c.log" 2>&1; then pass "c caller ($(grep -c '^PASS' "$B/c.log") lines)"; else fail "c caller"; cat "$B/c.log"; fi
cp "$D/caller.py" "$B/"
if python3 -I "$B/caller.py" > "$B/python.log" 2>&1; then pass "python caller ($(grep -c '^PASS' "$B/python.log") lines)"
else fail "python caller"; cat "$B/python.log"; fi
# Negative control: madd's add turned into sub must be caught.
lib "$D/mut/omega_native.c" "$B/mut"; caller "$B/mut"
if embeq "$B/mut/libomega_native.dylib" madd "$D/madd.bin"; then fail "byte check missed the mutant madd"
elif embeq "$B/mut/libomega_native.dylib" madd "$D/mut/madd.bin"; then pass "byte check: mutant library holds the mutant madd, not omc's"
else fail "mutant madd not embedded as generated"; fi
if "$B/mut/caller_c" > "$B/mut/c.log" 2>&1; then fail "mutant madd (add -> sub) not caught"
else pass "mutant madd (add -> sub) caught ($(grep -c '^FAIL' "$B/mut/c.log") failing checks)"; fi
# Host-word control: Linux system calls in a unit's code must stop the macOS build with the generator's reason.
if clang -std=gnu11 -fPIC -shared -o "$B/hostw.dylib" "$D/hostw/omega_native.c" 2> "$B/hostw.log"; then
    fail "host-word unit built on macOS"
elif grep -q 'unit hostw makes Linux system calls' "$B/hostw.log"; then pass "host-word unit refused on macOS (#error)"
else fail "host-word unit failed for another reason"; cat "$B/hostw.log"; fi
if [ "$fails" -ne 0 ]; then echo "NATIVE-CALL-MACOS FAIL $fails"; exit 1; fi
echo "NATIVE-CALL-MACOS PASS"
