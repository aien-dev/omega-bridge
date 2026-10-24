#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Independent judge for one conformance run.

Reads the frozen fixture, checks every declared input checksum, reads the raw
f32 output a runner wrote, and compares it with the oracle from oracle.py. It
also proves the detector is not vacuous: a scaled output, a swapped element and
(for attention) the wrong head map must all fail.

  verify.py --fixture F.json --result PREFIX [--expect-device cpu|gpu]
"""
import argparse
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oracle  # noqa: E402



def bits16(items):
    return [oracle.bf16_from_bits(int(x, 16)) for x in items]


def bits32(items):
    return [oracle.f32_from_bits(int(x, 16)) for x in items]


def read_f32(path):
    with open(path, "rb") as f:
        b = f.read()
    if len(b) % 4:
        raise ValueError("output is not a multiple of 4 bytes")
    return list(struct.unpack("<%df" % (len(b) // 4), b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--result", required=True)
    ap.add_argument("--expect-device", default=None)
    args = ap.parse_args()
    f = json.load(open(args.fixture))
    meta = json.load(open(args.result + ".json"))
    checks = 0
    fails = 0

    def check(cond, msg):
        nonlocal checks, fails
        checks += 1
        if not cond:
            fails += 1
            print("FAIL:", msg)

    if args.expect_device:
        check(meta.get("device") == args.expect_device, f"device {meta.get('device')} != {args.expect_device}")
    if meta.get("device") == "gpu":
        check(bool(meta.get("spark_window")), "GPU result has no SPARK_WINDOW identifier")

    if f["name"] == "matmul-v1":
        for key in ("a", "b"):
            check(oracle.input_checksum(f["inputs"][key]) == f["input_sha256"][key],
                  f"input {key} checksum stale")
        m, k, n = (f["shape"][x] for x in ("m", "k", "n"))
        ref = oracle.matmul_bf16_ref(
            [int(x, 16) for x in f["inputs"]["a"]],
            [int(x, 16) for x in f["inputs"]["b"]], m, k, n)
        got = read_f32(args.result + ".bin")
        check(len(got) == m * n, f"output length {len(got)} != {m*n}")
        check(oracle.matmul_matches(got, ref), "output does not match the fp64 reference")
        check(meta.get("shape") == [m, n], "runner shape mismatch")
        mut = list(got)
        mut[0] = mut[0] * 1.01 + (1e-3 if mut[0] == 0 else 0.0)
        check(not oracle.matmul_matches(mut, ref), "detector missed a 1% output mutation")
        if len(mut) > 1:
            mut = list(got)
            mut[0], mut[1] = mut[1], mut[0]
            check(not oracle.matmul_matches(mut, ref), "detector missed a swapped element")
    elif f["name"] == "gqa-causal-v1":
        for key in ("q", "k", "v"):
            check(oracle.input_checksum(f["inputs"][key]) == f["input_sha256"][key],
                  f"input {key} checksum stale")
        s = f["shape"]
        q = bits32(f["inputs"]["q"]); k = bits32(f["inputs"]["k"]); v = bits32(f["inputs"]["v"])
        ref = oracle.attention_ref(q, k, v, s["base"], s["hq"], s["hkv"], s["head_dim"])
        got = read_f32(args.result + ".bin")
        check(len(got) == len(ref), f"output length {len(got)} != {len(ref)}")
        check(oracle.attention_matches(got, ref), "output does not match the fp64 reference")
        check(meta.get("shape") == [s["r"], s["hq"], s["head_dim"]], "runner shape mismatch")
        wrong = oracle.attention_ref(q, k, v, s["base"], s["hq"], s["hkv"], s["head_dim"], head_map="mod")
        check(not oracle.attention_matches(got, wrong), "detector missed the wrong head map")
        mut = [x * 1.01 for x in got]
        check(not oracle.attention_matches(mut, ref), "detector missed a 1% output mutation")
    else:
        check(False, "unknown fixture name")

    summary = {
        "runner": meta.get("runner"),
        "device": meta.get("device"),
        "fixture": f["name"],
        "contract_id": f["contract_id"],
        "checks": checks,
        "fail": fails,
    }
    print(json.dumps(summary, sort_keys=True))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
