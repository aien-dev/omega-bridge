#!/bin/sh
# One-shot GB10 device qualification for the MAX interop work. Requires an
# authorized window: the ledger (--ledger) must be in the coordinator's
# CHIP-RESERVED allow-list, otherwise spark-window exits 3 and this stops.
#
#   sh tools/run-device-window.sh --ledger L679
#
# Does, in order, inside ONE window: loads/launches the exported cubins through
# the vendor driver, then runs the separate-process Omega/MAX conformance with
# --device. Never resets the GPU, changes the driver, or touches the serving
# process. All results carry the SPARK_WINDOW id.
set -eu
ledger=""
while [ $# -gt 0 ]; do case $1 in --ledger) ledger=$2; shift 2 ;; *) echo "unknown $1" >&2; exit 2 ;; esac; done
[ -n "$ledger" ] || { echo "usage: run-device-window.sh --ledger ID" >&2; exit 2; }

here=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cudapp="$here/../cudapp"
name="maxinterop-device-$ledger"

if [ -z "${SPARK_WINDOW:-}" ]; then
  spark-window open "$name" --ledger "$ledger" --gb10 shared --quiet none --lease 10
  opened=1
else
  opened=0
fi
trap '[ "$opened" = 1 ] && spark-window close "$name" 2>/dev/null || true' EXIT

# 1. Load/run the exported cubins through the vendor driver (probe refuses without SPARK_WINDOW).
spark-window run "$cudapp/build/cubin_probe" \
  "$cudapp/evidence/MAX-INTEROP/68/matmul-16x16x8.cubin" omega_matmul_bf16 16 16 8
spark-window run "$cudapp/build/cubin_probe" \
  "$cudapp/evidence/MAX-INTEROP/68/attention-hd128-gqa8.cubin" omega_gqa_attention_causal 2 8 1

# 2. Separate-process Omega and MAX GPU runs, judged by the independent oracle.
spark-window run "$here/conformance/run.sh" --device
