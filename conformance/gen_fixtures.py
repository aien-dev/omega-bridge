#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
"""Write the frozen deterministic fixtures used by both runners."""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oracle
ap = argparse.ArgumentParser(); ap.add_argument("--out", default="build/fixtures"); a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
for name, fx in (("matmul-v1", oracle.make_matmul_fixture()), ("gqa-causal-v1", oracle.make_attention_fixture())):
    p = os.path.join(a.out, name + ".json")
    with open(p, "wb") as f: f.write(oracle.fixture_bytes(fx))
    print(p, fx["input_sha256"])
