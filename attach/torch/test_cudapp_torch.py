"""test_cudapp_torch.py: torch.ops.cudapp.mm / swiglu on the GB10 against torch CPU in float64.

usage: CUDAPP_TORCH_LIB=<libcudapp_attach.so> python test_cudapp_torch.py RECEIPT.json
Runs on the chip (CUDA++ opens the GB10): take /tmp/aien-gb10.lock first. Exit 0 only when every case is inside
its bound, the routes are the stated ones, and the negative control (gemm_ex mutant 1: the last k element of every
product dropped) goes red.

Bounds, reference = float64 product of the same (exactly representable) inputs, S = (|a| @ |b|) in float64:
  bf16 / f16 inputs (native HMMA, fp32 accumulation over k terms):  |c - ref| <= k * 2^-24 * S
  f32 inputs (bf16x3: 9 exact plane products per k, fp32 accumulation over 9k terms, k parts summed in double):
                                                                     |c - ref| <= 9 k * 2^-24 * S
  swiglu (CUDApp tests/gpu_elementwise_test.c tolerance):           |y - ref| <= 1e-5 |ref| + 1e-6
"""
import json
import sys

import torch

import cudapp_torch

U = 2.0 ** -24
torch.manual_seed(20261027)
rows = []


def mm_case(m, k, n, dt, mutant=0):
    a = torch.randn(m, k, dtype=torch.float64).to(dt)
    b = torch.randn(k, n, dtype=torch.float64).to(dt)
    cudapp_torch.set_gemm_mutant(mutant)
    try:
        c = torch.ops.cudapp.mm(a, b).double()
    finally:
        cudapp_torch.set_gemm_mutant(0)
    ref = a.double() @ b.double()
    s = a.double().abs() @ b.double().abs()
    terms = 9 * k if dt == torch.float32 else k
    err = (c - ref).abs()
    ratio = float((err / (terms * U * s + 1e-300)).max())
    route_want = 3 if dt == torch.float32 else 1
    ok = ratio <= 1.0 and cudapp_torch.last_route == route_want
    rows.append({"op": "cudapp::mm", "m": m, "k": k, "n": n, "dtype": str(dt).split(".")[1], "mutant": mutant,
                 "route": cudapp_torch.last_route, "route_expected": route_want,
                 "max_abs_err": float(err.max()), "max_err_over_bound": ratio, "inside_bound": ok})
    return ok


def swiglu_case(n):
    g = torch.randn(n, dtype=torch.float32) * 4
    u = torch.randn(n, dtype=torch.float32)
    y = torch.ops.cudapp.swiglu(g, u).double()
    gd, ud = g.double(), u.double()
    ref = gd / (1 + torch.exp(-gd)) * ud
    ratio = float(((y - ref).abs() / (1e-5 * ref.abs() + 1e-6)).max())
    ok = ratio <= 1.0
    rows.append({"op": "cudapp::swiglu", "n": n, "max_abs_err": float((y - ref).abs().max()),
                 "max_err_over_bound": ratio, "inside_bound": ok})
    return ok


good = True
for m, k, n in [(1, 1, 1), (3, 257, 129), (17, 2048, 96), (64, 64, 64), (5, 1809, 33)]:
    good &= mm_case(m, k, n, torch.float32)
for dt in (torch.bfloat16, torch.float16):
    for m, k, n in [(5, 300, 7), (32, 128, 64)]:
        good &= mm_case(m, k, n, dt)
for n in (1, 1000, 65536):
    good &= swiglu_case(n)

# torch.library's own operator checks (schema, fake tensor, autograd registration) on one small case each
torch.library.opcheck(torch.ops.cudapp.mm.default, (torch.randn(3, 5), torch.randn(5, 4)))
torch.library.opcheck(torch.ops.cudapp.swiglu.default, (torch.randn(7), torch.randn(7)))

# negative control: must leave the bound
caught = not mm_case(3, 257, 129, torch.float32, mutant=1)
rows[-1]["negative_control"] = True
rows[-1]["caught"] = caught

verdict = "PASS" if good and caught else "FAIL"
with open(sys.argv[1], "w") as f:
    json.dump({"schema": "CUDAPP_TORCH_V1", "torch": torch.__version__, "verdict": verdict, "cases": rows}, f, indent=1)
for r in rows:
    print(json.dumps(r))
print(verdict)
sys.exit(0 if verdict == "PASS" else 1)
