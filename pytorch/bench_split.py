"""Where the Omega backend's time goes: compile, data passing and kernel, for the pytorch/bench.py model.

Run (one process for the steady-state split, plus child processes for the compile split):
  CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OMEGA_OMC=<omega-mv seed/out/omc> \
    nice -n 19 taskset -c 8 python3 pytorch/bench_split.py --rounds 30 --out split.json

Steady state, one forward pass of the bench model (all arms in this process, interleaved, the arm order
rotated every round and reversed every other round, /proc/loadavg read before every sample outside the
timed span):
  eager      m(x), eager PyTorch
  compiled   c(x), torch.compile(backend="omega"): Dynamo guards + AOT wrapper + the lowered graph
  lowered    the graph function _lower returned, called directly with the arguments AOT passes it
  stub       the same lowered graph with every kernel replaced by a stub unit: the same signature and
             shape constants, bound by the same src/native.om binding, with an empty Omega body (one
             ret). It costs everything except the kernel body: Python dispatch, output allocation,
             ctypes, the binding's argument checks, the stack switch and the return.
  op:<k>     one call_unit of step k on the tensors it saw in the forward pass, and stub:<k> the same
             call to the stub unit. Kernel body time of step k = op:<k> - stub:<k>.
  zc:<L>     one stub eadd call on three L-element float32 tensors, for L = 16 and 4194304 (16 MiB each):
             with zero-copy passing the call cost does not grow with L; a copy of 48 MiB would add ms.
  lowered_b, op_b:<k>   with --omc-b PATH --omc-b-sha256 SHA: the same graph built by a second compiler
             (for example the omega-mv #853 draft omc), interleaved with the pinned one; parity asserted.
Expected identities (checked by the summary, not here): compiled - lowered = Dynamo/AOT wrapper;
lowered - stub = sum over k of (op:<k> - stub:<k>) within noise.
Samples of the stub and zc arms repeat the call --reps times and store the per-call mean, because one
call is near the timer's resolution; every other sample is one call.

Compile (--compile-rounds child processes, alternating cold and warm): cold = an empty build cache, so
every unit runs omc and the graph's one library runs the native binder and cc once; warm = the cache that
the previous cold child filled, so the library is only dlopened. Each child records the first-call wall
time and omega_torch.TIMES, then resets Dynamo and compiles the model again: that repeat reaches _lower
with the same graph and is served by the in-process graph cache (repeat_first_call_ns).

Writes raw nanoseconds only. Statistics are computed separately (the receipt names the tool).
"""


import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import omega_torch as ot  # noqa: E402
from bench import MLP, loadavg  # noqa: E402


def stub_dir(src_dir):
    """Stub kernels: each kernel's entry function (its last fn) with an empty body."""
    d = tempfile.mkdtemp(prefix="omega-stub-")
    for f in os.listdir(src_dir):
        if f.endswith(".om"):
            with open(os.path.join(src_dir, f)) as h:
                sig = [ln for ln in h.read().splitlines() if ln.startswith("fn ")][-1]
            with open(os.path.join(d, f), "w") as h:
                h.write("note stub of %s: same entry signature, empty body (timing only)\n%s\nend\n" % (f, sig))
    return d


def capture(model, x):
    """Compile model; return (compiled callable, lowered run, the args AOT passed it, the unit calls, out)."""
    torch._dynamo.reset()
    got = {}
    orig_lower, orig_call = ot._lower, ot.call_unit

    def spy_lower(gm, ex):
        run = orig_lower(gm, ex)

        def spy_run(*a):
            got["args"] = a
            return run(*a)
        got["run"] = run
        return spy_run

    calls = []

    def spy_call(fn, name, tensors):
        calls.append((fn, name, list(tensors)))
        return orig_call(fn, name, tensors)

    ot._lower, ot.call_unit = spy_lower, spy_call
    try:
        c = torch.compile(model, backend="omega", fullgraph=True, dynamic=False)
        out = c(x)
    finally:
        ot._lower, ot.call_unit = orig_lower, orig_call
    return c, got["run"], got["args"], calls, out


def compile_child(cache):
    env = dict(os.environ, OMEGA_TORCH_CACHE=cache)
    p = subprocess.run([sys.executable, os.path.abspath(__file__), "--compile-child"], env=env,
                       capture_output=True, text=True, check=True)
    return json.loads(p.stdout.strip().splitlines()[-1])


def child():
    torch.manual_seed(0)
    m = MLP().eval()
    x = torch.randn(64, 256)
    with torch.no_grad():
        c = torch.compile(m, backend="omega", fullgraph=True, dynamic=False)
        t0 = time.perf_counter_ns()
        c(x)
        first = time.perf_counter_ns() - t0
        t0 = time.perf_counter_ns()
        c(x)
        second = time.perf_counter_ns() - t0
        times = dict(ot.TIMES)
        torch._dynamo.reset()
        c = torch.compile(m, backend="omega", fullgraph=True, dynamic=False)
        t0 = time.perf_counter_ns()
        c(x)
        repeat = time.perf_counter_ns() - t0
    print(json.dumps({"first_call_ns": first, "second_call_ns": second, "repeat_first_call_ns": repeat,
                      "repeat_lower_ns": ot.TIMES["lower"] - times["lower"], "times": times,
                      "units_built": ot.STATS["units_built"], "libraries_built": ot.STATS["libraries_built"],
                      "graph_cache_hits": ot.STATS["graph_cache_hits"]}))


def timed(f, reps):
    t0 = time.perf_counter_ns()
    for _ in range(reps):
        f()
    return (time.perf_counter_ns() - t0) / reps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=30)
    ap.add_argument("--reps", type=int, default=100)
    ap.add_argument("--compile-rounds", type=int, default=6)
    ap.add_argument("--compile-child", action="store_true")
    ap.add_argument("--omc-b", help="a second omc, measured as the lowered_b and op_b arms")
    ap.add_argument("--omc-b-sha256", help="the sha256 that --omc-b must have (checked by omega_torch)")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.compile_child:
        return child()
    threads = len(os.sched_getaffinity(0))
    torch.set_num_threads(threads)
    rec = {"loadavg_before": loadavg(), "affinity": sorted(os.sched_getaffinity(0)), "torch_threads": threads,
           "torch": torch.__version__, "python": platform.python_version(), "rounds": a.rounds, "reps": a.reps,
           "omc_sha256": ot.OMC_SHA256, "omc_b_sha256": a.omc_b_sha256}

    # ---- compile split (child processes) ----
    comp = []
    for r in range(a.compile_rounds):
        cache = tempfile.mkdtemp(prefix="omega-cache-")
        try:
            for kind in ("cold", "warm"):
                ld = loadavg()
                s = compile_child(cache)
                s.update(kind=kind, loadavg=ld)
                comp.append(s)
        finally:
            shutil.rmtree(cache)
    rec["compile"] = comp

    # ---- steady-state split ----
    torch.manual_seed(0)
    m = MLP().eval()
    x = torch.randn(64, 256)
    stubs = stub_dir(ot.KERNEL_DIR)
    with torch.no_grad():
        want = m(x)
        c, run, args, calls, got = capture(m, x)
        torch.testing.assert_close(got, want)
        rec["parity_max_abs"] = (got - want).abs().max().item()
        real_dir = ot.KERNEL_DIR
        ot.KERNEL_DIR = stubs
        try:
            _, srun, sargs, scalls, _ = capture(m, x)
            zc = []
            for L in (16, 4194304):
                ts = [torch.randn(L), torch.randn(L), torch.empty(L)]
                zc.append(("zc:%d" % L, ot.load_unit("eadd", [("L", L)], 3), ts))
        finally:
            ot.KERNEL_DIR = real_dir
            shutil.rmtree(stubs)
        brun, bcalls = None, []
        if a.omc_b:
            pin, path = ot.OMC_SHA256, os.environ["OMEGA_OMC"]
            ot.OMC_SHA256, os.environ["OMEGA_OMC"] = a.omc_b_sha256, a.omc_b
            try:
                _, brun, bargs, bcalls, bgot = capture(m, x)
            finally:
                ot.OMC_SHA256, os.environ["OMEGA_OMC"] = pin, path
            torch.testing.assert_close(bgot, want)
            rec["parity_b_max_abs"] = (bgot - want).abs().max().item()
            assert [k for _, k, _ in bcalls] == [k for _, k, _ in calls]
        torch._dynamo.reset()
        c = torch.compile(m, backend="omega", fullgraph=True, dynamic=False)  # clean, no spies
        torch.testing.assert_close(c(x), want)
        assert [k for _, k, _ in calls] == [k for _, k, _ in scalls]
        steps = [k for _, k, _ in calls]
        rec["steps"] = steps
        arms = [("eager", lambda: m(x), 1), ("compiled", lambda: c(x), 1), ("lowered", lambda: run(*args), 1),
                ("stub", lambda: srun(*sargs), a.reps)]
        for i, ((fn, k, ts), (sfn, _, _)) in enumerate(zip(calls, scalls)):
            arms.append(("op:%d:%s" % (i, k), (lambda fn=fn, k=k, ts=ts: ot.call_unit(fn, k, ts)), 1))
            arms.append(("stub:%d:%s" % (i, k), (lambda fn=sfn, k=k, ts=ts: ot.call_unit(fn, k, ts)), a.reps))
        for name, fn, ts in zc:
            arms.append((name, (lambda fn=fn, ts=ts: ot.call_unit(fn, "eadd", ts)), a.reps))
        if brun is not None:
            arms.append(("lowered_b", lambda: brun(*bargs), 1))
            for i, (fn, k, ts) in enumerate(bcalls):
                arms.append(("op_b:%d:%s" % (i, k), (lambda fn=fn, k=k, ts=ts: ot.call_unit(fn, k, ts)), 1))
        for _, f, _ in arms:
            f()  # warm every arm once
        torch.testing.assert_close(run(*args)[0], want)  # op arms rewrote the same buffers: still parity
        if brun is not None:
            torch.testing.assert_close(brun(*bargs)[0], want)
        ns = {name: [] for name, _, _ in arms}
        lds = {name: [] for name, _, _ in arms}
        for r in range(a.rounds):
            k = r % len(arms)
            order = arms[k:] + arms[:k]  # rotate the start every round
            if r % 2:
                order.reverse()
            for name, f, reps in order:
                lds[name].append(loadavg())
                ns[name].append(timed(f, reps))
        torch.testing.assert_close(c(x), want)  # still parity after every timed call
    rec["ns"], rec["loadavg"] = ns, lds
    rec["loadavg_after"] = loadavg()
    load1 = [float(s.split()[0]) for v in lds.values() for s in v]
    load1 += [float(s["loadavg"].split()[0]) for s in comp]
    rec["max_load1"] = max(load1)
    rec["label"] = "taken under load (load1 > 8)" if max(load1) > 8 else "load1 <= 8 for every sample"
    with open(a.out, "w") as f:
        json.dump(rec, f, indent=1)
    print(json.dumps({k: rec.get(k) for k in ("loadavg_before", "loadavg_after", "max_load1", "label", "steps",
                                              "parity_max_abs", "parity_b_max_abs")}))


if __name__ == "__main__":
    main()
