#!/bin/sh
# IR/reference-only policy mutants. A build failure, trap, signal, or arbitrary
# nonzero status is INVALID, never a caught control. Expected case IDs are
# independent literal assertions in placement.om.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
sh "$ROOT/tests/ggml/run-source-controls.sh"
sh "$ROOT/tests/ggml/run-reference.sh"
OUT=$ROOT/build/ggml-reference
mkdir -p "$OUT/controls"
control() {
    name=$1 want=$2 unit=$3 expression=$4
    dir=$OUT/controls/$name
    mkdir -p "$dir"
    sed "$expression" "$ROOT/adapters/ggml/$unit.om" > "$dir/mutant.om"
    if cmp -s "$dir/mutant.om" "$ROOT/adapters/ggml/$unit.om"; then
        echo "INVALID $name: source unchanged" >&2; exit 1
    fi
    if [ "$unit" = strict_node ]; then
        cat "$dir/mutant.om" "$ROOT/adapters/ggml/strict_snapshot.om" "$ROOT/tests/ggml/placement.om"
    else
        cat "$ROOT/adapters/ggml/strict_node.om" "$dir/mutant.om" "$ROOT/tests/ggml/placement.om"
    fi | sed '/^note /d' > "$dir/placement.om"
    "$OUT/omegese" emit "$dir/placement.om" "$dir/placement.json" > "$dir/build.log"
    "$OUT/omega_emit" emit "$dir/placement.json" "$dir/placement.oscir" >> "$dir/build.log"
    rc=0
    "$OUT/reference" "$dir/placement.oscir" > "$dir/run.log" 2>&1 || rc=$?
    if [ "$rc" != 1 ] || [ "$(cat "$dir/run.log")" != "reference trap=0 result=$want" ]; then
        echo "INVALID/UNCAUGHT $name: rc=$rc, expected assertion $want" >&2
        cat "$dir/run.log" >&2; exit 1
    fi
    echo "CAUGHT $name: assertion $want (host reference only)"
}
control broad-get-rows 2 strict_node '/^fn strictnode /a\
if eq op 40\
ret 0\
end'
control cpu-transformer 2 strict_node 's/^if and eq role 3 ne backend 2$/if bool false/'
control cont-as-metadata 52 strict_node 's/allowed = or eq op 0 /allowed = or eq op 35 or eq op 0 /'
control wrong-glu-subtype 14 strict_node 's/^if ne detail 2$/if bool false/'
control missing-nodes 44 strict_snapshot 's/^if ne observed expected$/if bool false/'
control stale-graph 46 strict_snapshot 's/^if or eq graph 0 ne graph currentgraph$/if eq graph 0/'
control stale-residency 48 strict_snapshot 's/^if or eq residency 0 ne residency currentresidency$/if eq residency 0/'
control empty-graph 41 strict_snapshot 's/^if or eq observed 0 eq expected 0$/if bool false/'
echo 'PASS 8/8 host-reference controls; no native/hardware qualification'
