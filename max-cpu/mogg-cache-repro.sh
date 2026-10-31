#!/bin/sh
# MAX 26.7.0 observation: a custom-op kernel compiled from one Mojo source is reused after that
# source changes, when the package path and MODULAR_CACHE_DIR stay the same. Needs max-cpu/run.sh
# to have built $BUILD first (lib/ and extcall/kernels). Prints one line per step; exit 0 always
# reports what it saw, it does not gate anything.
#   TMPDIR=/dev/shm taskset -c 5-9 nice -n 19 ionice -c3 max-cpu/mogg-cache-repro.sh
set -eu
export CUDA_VISIBLE_DEVICES=  # MAX 26.7.0 Graph() opens a visible GPU; see run.sh
cd "$(dirname "$0")/.."
MAXPY=${MAXPY:-$HOME/workspace/maxinterop/venv/bin/python}
BUILD=${BUILD:-/dev/shm/omega-max-cpu}
R=$BUILD/mogg-repro
L=$BUILD/lib/libomega_native.so
rm -rf "$R"
mkdir -p "$R/pkg/kernels" "$R/other/kernels"
step() { # step NAME CACHE KERNELS: prints the error or "ran"
    MODULAR_CACHE_DIR=$3 "$MAXPY" max-cpu/omega_max.py neg-load --lib "$L" --kernels "$2" \
        --want 'Failed to materialize symbols' >"$R/$1.log" 2>&1 || true
    printf '%-26s %s\n' "$1" "$(grep '^got:' "$R/$1.log" | cut -c1-90)"
}
cp "$BUILD/extcall/kernels/__init__.mojo" "$R/pkg/kernels/"
step 1-extcall-cacheA "$R/pkg/kernels" "$R/cacheA"
find "$R/cacheA" -type f | sed "s|$R/||" | sort >"$R/cacheA-after-1.txt"
cp max-cpu/kernels/__init__.mojo "$R/pkg/kernels/"      # the fixed glue, same path
step 2-fixed-cacheA "$R/pkg/kernels" "$R/cacheA"
find "$R/cacheA" -type f | sed "s|$R/||" | sort >"$R/cacheA-after-2.txt"
step 3-fixed-cacheB-fresh "$R/pkg/kernels" "$R/cacheB"
cp max-cpu/kernels/__init__.mojo "$R/other/kernels/"    # the fixed glue, another path
step 4-fixed-otherpath-cacheA "$R/other/kernels" "$R/cacheA"
sha256sum "$R/pkg/kernels/__init__.mojo" "$BUILD/extcall/kernels/__init__.mojo"
if diff "$R/cacheA-after-1.txt" "$R/cacheA-after-2.txt" >/dev/null; then echo "cacheA: no new files in step 2"
else echo "cacheA: step 2 added $(comm -13 "$R/cacheA-after-1.txt" "$R/cacheA-after-2.txt" | wc -l) files"; fi
