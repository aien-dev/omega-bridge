#!/bin/sh
# Host harness smoke. A GPU run is an explicit second mode and needs SPARK_WINDOW.
set -eu
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
MAXPY=${MAXPY:-$HOME/workspace/maxinterop/venv/bin/python}
mkdir -p build
$PY gen_fixtures.py --out build/fixtures
sh build.sh
fail=0
for f in matmul-v1 gqa-causal-v1; do
    $MAXPY max_runner.py --fixture build/fixtures/$f.json --device cpu --out build/max-$f || fail=1
    $PY verify.py --fixture build/fixtures/$f.json --result build/max-$f --expect-device cpu || fail=1
done
./build/omega_runner matmul --m 4 --k 5 --n 3 --seed 680 --out build/omega-matmul-v1 || fail=1
$PY verify.py --fixture build/fixtures/matmul-v1.json --result build/omega-matmul-v1 --expect-device host-wiring || fail=1
if [ "${1:-}" = "--device" ]; then
    ./build/omega_runner matmul --m 4 --k 5 --n 3 --seed 680 --out build/omega-gpu-matmul --device || fail=1
    $PY verify.py --fixture build/fixtures/matmul-v1.json --result build/omega-gpu-matmul --expect-device gpu || fail=1
    $MAXPY max_runner.py --fixture build/fixtures/matmul-v1.json --device gpu --out build/max-gpu-matmul || fail=1
    $PY verify.py --fixture build/fixtures/matmul-v1.json --result build/max-gpu-matmul --expect-device gpu || fail=1
    ./build/omega_runner attention --base 1 --rows 2 --hq 4 --hkv 2 --hd 128 --seed 2810054072 --out build/omega-gpu-attn --device || fail=1
    $PY verify.py --fixture build/fixtures/gqa-causal-v1.json --result build/omega-gpu-attn --expect-device gpu || fail=1
    $MAXPY max_runner.py --fixture build/fixtures/gqa-causal-v1.json --device gpu --out build/max-gpu-attn || fail=1
    $PY verify.py --fixture build/fixtures/gqa-causal-v1.json --result build/max-gpu-attn --expect-device gpu || fail=1
else
    echo "DEVICE RUNS: NOT_RUN (pass --device inside an authorized spark-window)"
fi
[ $fail -eq 0 ] && echo "CONFORMANCE HARNESS PASS"
exit $fail
