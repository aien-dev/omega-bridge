"""Milestone 1 checks for torch.compile(backend="omega"). CPU only; the oracle is eager PyTorch.

Run: CUDA_VISIBLE_DEVICES= OMEGA_OMC=<omega-mv seed/out/omc> python3 -m unittest -v pytorch/tests/test_omega_torch.py
Tolerance: torch.testing.assert_close float32 defaults (rtol 1.3e-6, atol 1e-5) against eager float32.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import torch
import torch.nn as nn

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import omega_torch as ot  # noqa: E402

torch.manual_seed(0)


def compiled(fn):
    torch._dynamo.reset()
    return torch.compile(fn, backend="omega", fullgraph=True, dynamic=False)


def run_both(fn, *args):
    ot.reset_stats()
    with torch.no_grad():
        got = compiled(fn)(*args)
        want = fn(*args)
    return got, want


def two_ulp(got, ref64):
    """|got - ref| <= 2^-22 |ref| elementwise: two float32 ulps from a float64 eager reference."""
    return bool(((got.double() - ref64).abs() <= ref64.abs() * 2.0 ** -22).all())


class MLP(nn.Module):
    def __init__(self, i=16, h=32, o=8):
        super().__init__()
        self.l1 = nn.Linear(i, h)
        self.l2 = nn.Linear(h, o)
        self.p = nn.Parameter(torch.randn(o, o))

    def forward(self, x, y):
        h = torch.relu(self.l1(x)) + y
        z = torch.matmul(self.l2(h), self.p)
        return torch.softmax(z, dim=-1)


class Ops(unittest.TestCase):
    """One op at a time, each through an Omega kernel, against eager float32."""

    def check(self, fn, *args, kernels):
        got, want = run_both(fn, *args)
        torch.testing.assert_close(got, want)
        self.assertEqual(ot.STATS["eager_fallback_calls"], 0)
        for k in kernels:
            self.assertGreaterEqual(ot.STATS["per_op"].get(k, 0), 1, (k, ot.STATS))

    def test_mm(self):
        self.check(torch.mm, torch.randn(5, 7), torch.randn(7, 3), kernels=["mm"])

    def test_addmm(self):
        self.check(torch.addmm, torch.randn(3), torch.randn(5, 7), torch.randn(7, 3), kernels=["addmm"])

    def test_linear(self):
        lin = nn.Linear(7, 3)
        self.check(lin, torch.randn(5, 7), kernels=["linear"])
        self.assertNotIn("tr", ot.STATS["per_op"])

    def test_permute(self):
        self.check(lambda x, y: x.t() + y, torch.randn(4, 6), torch.randn(6, 4), kernels=["tr", "eadd"])

    def test_add(self):
        self.check(torch.add, torch.randn(3, 5), torch.randn(3, 5), kernels=["eadd"])

    def test_relu(self):
        x = torch.randn(4, 9)
        x[0, 0] = float("nan")
        x[0, 1] = float("-inf")
        x[0, 2] = float("inf")
        got, want = run_both(torch.relu, x)
        torch.testing.assert_close(got, want, equal_nan=True)
        self.assertEqual(ot.STATS["per_op"], {"relu": 1})

    def test_softmax(self):
        x = torch.randn(6, 11) * 40.0
        x[1, 3] = float("-inf")
        self.check(lambda t: torch.softmax(t, dim=-1), x, kernels=["softmax"])

    def test_softmax_two_ulp_of_float64(self):
        # Stricter than the float32 default: within 2^-22 relative (2 float32 ulps) of eager float64.
        # The default (atol 1e-5) cannot see an exp truncated at degree 4 (measured 4.9e-5 relative).
        x = torch.randn(6, 11) * 4.0
        got, _ = run_both(lambda t: torch.softmax(t, dim=-1), x)
        self.assertTrue(two_ulp(got, torch.softmax(x.double(), dim=-1)))

    def test_softmax_wolfram(self):
        # WolframLanguageEvaluator: Exp[k]/(Exp[1]+Exp[2]+Exp[3]), k = 1, 2, 3, to 20 digits ->
        # 0.090030573170380457998, 0.24472847105479765247, 0.66524095577482188953.
        # Omega must give the float32 nearest to each exact value (one rounding of an f64 result).
        exact = torch.tensor([[0.090030573170380457998, 0.24472847105479765247,
                               0.66524095577482188953]], dtype=torch.float64).to(torch.float32)
        got, _ = run_both(lambda t: torch.softmax(t, dim=-1), torch.tensor([[1.0, 2.0, 3.0]]))
        self.assertTrue(torch.equal(got, exact), (got, exact))

    def test_mm_exact_integers(self):
        # Small integers: every product and sum is exact in f32, so Omega and eager must agree bitwise.
        a = torch.randint(-9, 10, (6, 5)).float()
        b = torch.randint(-9, 10, (5, 4)).float()
        got, want = run_both(torch.mm, a, b)
        self.assertTrue(torch.equal(got, want))


class Model(unittest.TestCase):
    def test_mlp_parity_and_all_omega(self):
        m = MLP().eval()
        x, y = torch.randn(4, 16), torch.randn(4, 32)
        got, want = run_both(m, x, y)
        torch.testing.assert_close(got, want)
        s = ot.STATS
        self.assertEqual(s["eager_fallback_calls"], 0)
        self.assertEqual(s["per_op"], {"linear": 2, "relu": 1, "eadd": 1, "mm": 1, "softmax": 1})
        # Independent float64 eager reference: Omega's error is no larger than eager float32's plus 1e-7.
        with torch.no_grad():
            ref = m.double()(x.double(), y.double())
        err_o = (got.double() - ref).abs().max().item()
        err_e = (want.double() - ref).abs().max().item()
        self.assertLessEqual(err_o, err_e + 1e-7, (err_o, err_e))


class FailClosed(unittest.TestCase):
    def test_unsupported_op_raises_and_runs_nothing(self):
        ot.set_fallback(())
        ot.reset_stats()
        with torch.no_grad(), self.assertRaises(Exception) as cm:
            compiled(lambda x: torch.tanh(x) + x)(torch.randn(3, 3))
        self.assertIn("OmegaRefused", repr(cm.exception) + str(cm.exception))
        self.assertIn("aten.tanh.default", str(cm.exception))
        self.assertEqual(ot.STATS["omega_calls"], 0)
        self.assertEqual(ot.STATS["eager_fallback_calls"], 0)

    def test_broadcast_add_refused(self):
        with torch.no_grad(), self.assertRaises(Exception) as cm:
            compiled(lambda a, b: a + b)(torch.randn(3, 4), torch.randn(4))
        self.assertIn("broadcasting", str(cm.exception))

    def test_explicit_fallback_is_counted(self):
        ot.set_fallback({"aten.tanh.default"})
        try:
            got, want = run_both(lambda x: torch.tanh(x) + x, torch.randn(3, 3))
        finally:
            ot.set_fallback(())
        torch.testing.assert_close(got, want)
        self.assertEqual(ot.STATS["eager_fallback_calls"], 1)
        self.assertEqual(ot.STATS["per_op"], {"eadd": 1})

    def test_array_limit_refused(self):
        with torch.no_grad(), self.assertRaises(Exception) as cm:
            compiled(torch.relu)(torch.zeros(4097, 4096))
        self.assertIn("above the Omega array limit 16777216", str(cm.exception))

    def test_wrong_length_status_32(self):
        fn = ot.load_unit("relu", [("L", 4)], 2)
        with self.assertRaises(ot.OmegaCallError) as cm:
            ot.call_unit(fn, "relu", [torch.zeros(5), torch.zeros(4)])
        self.assertIn("status 32", str(cm.exception))


class NegativeControl(unittest.TestCase):
    """Deliberately wrong kernels must make the parity checks fail."""

    def mutate(self, name, old, new):
        d = tempfile.mkdtemp(prefix="omega-torch-mut-")
        for f in os.listdir(ot.KERNEL_DIR):
            shutil.copy(os.path.join(ot.KERNEL_DIR, f), d)
        p = os.path.join(d, name + ".om")
        with open(p) as f:
            src = f.read()
        self.assertIn(old, src)
        with open(p, "w") as f:
            f.write(src.replace(old, new, 1))
        return d

    def with_kernels(self, d, fn, *args):
        saved = ot.KERNEL_DIR
        ot.KERNEL_DIR = d
        try:
            return run_both(fn, *args)
        finally:
            ot.KERNEL_DIR = saved

    def test_mutant_linear_caught(self):
        d = self.mutate("linear", "s = add s mul", "s = sub s mul")
        got, want = self.with_kernels(d, MLP().eval(), torch.randn(4, 16), torch.randn(4, 32))
        with self.assertRaises(AssertionError):
            torch.testing.assert_close(got, want)

    def test_mutant_relu_caught(self):
        d = self.mutate("relu", "if lt v 0.0f32", "if gt v 0.0f32")
        got, want = self.with_kernels(d, torch.relu, torch.randn(4, 9))
        with self.assertRaises(AssertionError):
            torch.testing.assert_close(got, want)

    def test_mutant_softmax_caught(self):
        # exp truncated at degree 4 instead of 13: 4.9e-5 relative error, which the float32 default
        # tolerance (atol 1e-5) misses on probabilities this small; the two-ulp float64 check catches it.
        d = self.mutate("softmax", "for j ulong 13\nn = f64 sub 13 j", "for j ulong 4\nn = f64 sub 4 j")
        x = torch.randn(6, 11) * 4.0
        got, _ = self.with_kernels(d, lambda t: torch.softmax(t, dim=-1), x)
        self.assertFalse(two_ulp(got, torch.softmax(x.double(), dim=-1)))


class Binding(unittest.TestCase):
    """src/native.om: f32 arrays and const-named lengths are bound; anything else is refused."""

    def gen(self, src):
        with tempfile.NamedTemporaryFile() as t:
            ot._compile_om(src.encode(), t.name)
            code = t.read()
        frame = src.encode() + b"\0" + b"%08d" % len(code) + code
        p = subprocess.run([ot._native()], input=frame, capture_output=True)
        return p.returncode, p.stdout.decode()

    def test_const_f32_bound(self):
        rc, c = self.gen("const L ulong 6\nfn k a view f32 L o edit f32 L to void\nput o 0 get a 0\nend\n")
        self.assertEqual(rc, 0)
        self.assertRegex(c, r"ombr_span_add\(sp, &ns, o_a, o_a_len, 6u, 4u, 0\)")
        self.assertRegex(c, r"ombr_span_add\(sp, &ns, o_o, o_o_len, 6u, 4u, 1\)")

    def test_const_not_ulong_refused(self):
        # The compiler accepts a uint constant as a length; the binding reads only "const NAME ulong N".
        rc, c = self.gen("const L uint 6\nfn k a view f32 L to void\nret\nend\n")
        self.assertEqual((rc, c), (110, ""))

    def test_f64_array_refused(self):
        rc, c = self.gen("fn k a view f64 4 to void\nret\nend\n")
        self.assertEqual((rc, c), (110, ""))


if __name__ == "__main__":
    unittest.main()
