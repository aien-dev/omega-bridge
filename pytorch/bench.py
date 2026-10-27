"""Paired, interleaved wall-clock timing of one MLP forward pass: eager PyTorch versus backend="omega".

Run (both arms in the same process, on the same pinned core, one thread each):
  CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OMEGA_OMC=<omega-mv seed/out/omc> \
    taskset -c 17 python3 pytorch/bench.py --rounds 30 --out timings.json
Writes raw per-call nanoseconds for both arms, /proc/loadavg before every sample and before and after
the run, and labels the run "taken under load" when any sample saw load1 above 8. It computes no
statistics: summarise the raw numbers separately (the receipt names the tool used).
"""

import argparse
import json
import os
import platform
import sys
import time

import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import omega_torch as ot  # noqa: E402


class MLP(nn.Module):
    def __init__(self, d=256, h=64):
        super().__init__()
        self.l1 = nn.Linear(d, d)
        self.l2 = nn.Linear(d, h)
        self.p = nn.Parameter(torch.randn(h, h) / 8.0)

    def forward(self, x):
        y = torch.relu(self.l1(x)) + x
        return torch.softmax(torch.matmul(self.l2(y), self.p), dim=-1)


def loadavg():
    with open("/proc/loadavg") as f:
        return f.read().strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=30)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    threads = len(os.sched_getaffinity(0))
    torch.set_num_threads(threads)
    rec = {"loadavg_before": loadavg(), "affinity": sorted(os.sched_getaffinity(0)), "torch_threads": threads,
           "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"), "torch": torch.__version__,
           "python": platform.python_version(), "batch": a.batch, "rounds": a.rounds}
    torch.manual_seed(0)
    m = MLP().eval()
    x = torch.randn(a.batch, 256)
    with torch.no_grad():
        c = torch.compile(m, backend="omega", fullgraph=True, dynamic=False)
        got, want = c(x), m(x)  # compile and warm both arms
        torch.testing.assert_close(got, want)
        rec["parity_max_abs"] = (got - want).abs().max().item()
        ot.reset_stats()
        eager, omega, eager_load, omega_load = [], [], [], []
        for r in range(a.rounds):  # interleaved, order alternating per round
            arms = [(eager, eager_load, m), (omega, omega_load, c)]
            if r % 2:
                arms.reverse()
            for sink, loads, f in arms:
                loads.append(loadavg())  # /proc/loadavg read before each sample, outside the timed span
                t0 = time.perf_counter_ns()
                f(x)
                sink.append(time.perf_counter_ns() - t0)
    rec["stats"] = {k: v for k, v in ot.STATS.items()}
    rec["eager_ns"], rec["omega_ns"] = eager, omega
    rec["eager_loadavg"], rec["omega_loadavg"] = eager_load, omega_load
    rec["loadavg_after"] = loadavg()
    load1 = [float(s.split()[0]) for s in eager_load + omega_load]
    rec["max_load1"] = max(load1)
    rec["label"] = "taken under load (load1 > 8)" if max(load1) > 8 else "load1 <= 8 for every sample"
    with open(a.out, "w") as f:
        json.dump(rec, f, indent=1)
    print(json.dumps({k: rec[k] for k in ("loadavg_before", "loadavg_after", "max_load1", "label", "affinity",
                                          "torch_threads", "parity_max_abs", "stats")}))


if __name__ == "__main__":
    main()
