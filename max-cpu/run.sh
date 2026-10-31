#!/bin/sh
# Reproduce the MAX CPU route for the Omega matmul custom op (evidence/MAX-CPU/README.md).
# Run from anywhere, pinned:  TMPDIR=/dev/shm taskset -c 10-14 nice -n 19 ionice -c3 max-cpu/run.sh
# CPU only: every graph is built on DeviceRef.CPU(); nothing here opens the GPU.
set -eu
cd "$(dirname "$0")/.."
MAXPY=${MAXPY:-$HOME/workspace/maxinterop/venv/bin/python}
OMEGA_REPO=${OMEGA_REPO:-$HOME/workspace/omega}
BUILD=${BUILD:-/dev/shm/omega-max-cpu}
EV=${EV:-$PWD/evidence/MAX-CPU/raw}
ITERS=${ITERS:-300}
OMC1_REV=55f9b0af OMC1_SHA=734f0a39319fbfa930bcc62cb30dbf06d47d78e126372b74f5baf478e6126b61
OMC2_REV=ec07d25d OMC2_SHA=499236398aabc652e2dae27fe4bdc4c5db3d3726314356e0dbef23e3345803ec
GLUE_CALL='process.get_function[UInt32]("omega2_omatmul")('
# Mutant: A's row stride N instead of K (one token). A transposed C write (C[j*M+i]) does not
# compile: brow is already at the 16-live-value limit (omc error 12).
MUT_FROM='ai = mul i k'
MUT_TO='ai = mul i n'

rm -rf "$BUILD"
mkdir -p "$BUILD/omc" "$EV"
for v in 1 2; do
    eval rev=\$OMC${v}_REV sha=\$OMC${v}_SHA
    git -C "$OMEGA_REPO" show "$rev:seed/out/omc" >"$BUILD/omc/omc$v"
    chmod +x "$BUILD/omc/omc$v"
    echo "$sha  $BUILD/omc/omc$v" | sha256sum -c -
done
export OMEGA_NATIVE_OMC="$BUILD/omc/omc1" OMEGA_NATIVE_OMC2="$BUILD/omc/omc2"

once() { # once FILE FROM: FROM must occur exactly once
    n=$(grep -cF -- "$2" "$1" || true)
    [ "$n" = 1 ] || { echo "run.sh: '$2' occurs $n times in $1" >&2; exit 2; }
}
swap() { # swap SRC DST FROM TO
    once "$1" "$3"
    FROM=$3 TO=$4 "$MAXPY" -c 'import os,sys; s=open(sys.argv[1]).read(); open(sys.argv[2],"w").write(s.replace(os.environ["FROM"],os.environ["TO"]))' "$1" "$2"
    once "$2" "$4"
}

# Omega library, and the transposed-write mutant (negative control c).
tools/native "$BUILD/lib" max-cpu/omatmul.om >"$EV/build-lib.log" 2>&1
mkdir -p "$BUILD/mut"
swap max-cpu/omatmul.om "$BUILD/mut/omatmul.om" "$MUT_FROM" "$MUT_TO"
tools/native "$BUILD/lib-mutant" "$BUILD/mut/omatmul.om" >"$EV/build-mutant.log" 2>&1
grep -h 'omega-ident' "$BUILD/lib/omega_native.h" "$BUILD/lib-mutant/omega_native.h" >"$EV/idents.txt" || true

# Glue variants (negative control a): a missing symbol, and the plain external_call route.
mkdir -p "$BUILD/wrongsym/kernels" "$BUILD/extcall/kernels"
swap max-cpu/kernels/__init__.mojo "$BUILD/wrongsym/kernels/__init__.mojo" "$GLUE_CALL" \
    'process.get_function[UInt32]("omega2_omatmul_missing")('
swap max-cpu/kernels/__init__.mojo "$BUILD/extcall/kernels/__init__.mojo" "$GLUE_CALL" \
    'external_call["omega2_omatmul", UInt32]('

# Each run gets an empty MAX cache: MAX 26.7.0 reuses compiled kernels across glue edits.
run() { # run NAME ARGS...
    name=$1; shift
    rm -rf "$BUILD/cache-$name"
    MODULAR_CACHE_DIR="$BUILD/cache-$name" "$MAXPY" max-cpu/omega_max.py "$@" >"$EV/$name.log" 2>&1
}
fail=0
L="--lib $BUILD/lib/libomega_native.so"
run check check $L --out "$EV/check.json" || fail=1
run neg-shape neg-shape $L --out "$EV/neg-shape.json" || fail=1
run neg-wrongsym neg-load $L --kernels "$BUILD/wrongsym/kernels" \
    --want 'symbol not found: omega2_omatmul_missing' || fail=1
run neg-extcall neg-load $L --kernels "$BUILD/extcall/kernels" \
    --want 'Failed to materialize symbols' || fail=1
grep -qF 'Symbols not found: [ omega2_omatmul ]' "$EV/neg-extcall.log" || fail=1
if run neg-mutant check --lib "$BUILD/lib-mutant/libomega_native.so" --out "$EV/neg-mutant.json"; then
    echo "neg-mutant: the A-stride mutant passed the numeric check" >&2; fail=1
else
    grep -q 'OMEGA_MAX_CHECK: FAIL' "$EV/neg-mutant.log" || fail=1
fi
for f in check neg-shape neg-wrongsym neg-extcall neg-mutant; do
    printf '%-13s %s\n' "$f" "$(grep -h 'OMEGA_MAX_' "$EV/$f.log" | tail -1)"
done
if [ "${MEASURE:-1}" = 1 ]; then
    "$MAXPY" max-cpu/omega_max.py measure-all $L --iters "$ITERS" --out "$EV/measure" \
        >"$EV/measure.log" 2>&1 || fail=1
    rm -rf "$EV"/measure/cache-*
fi
[ $fail -eq 0 ] && echo "OMEGA MAX CPU: PASS (controls green, negatives red as expected)"
exit $fail
