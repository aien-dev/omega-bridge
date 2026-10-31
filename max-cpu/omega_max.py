"""MAX CPU harness for the Omega matmul custom op (max-cpu/omatmul.om via max-cpu/kernels).

Subcommands (run with the MAX venv python, see max-cpu/run.sh):
  check       numerics: Omega op vs numpy float64 and vs ops.matmul on the same graph
  neg-shape   bad shapes: refused by Omega (codes 1/2/3) and at graph construction
  neg-load    a kernels dir that must fail to load or execute (wrong symbol, external_call)
  measure     one op/shape in this process: cold start, warm latencies, peak RSS
  measure-all spawns one `measure` child per (op, shape, cache state)

Every graph runs on DeviceRef.CPU() only, and main() refuses (exit 2) while an accelerator is
visible, because MAX 26.7.0 Graph() otherwise opens a CUDA context. Exit 0 = the expected
outcome was observed.
"""

import argparse
import ctypes
import json
import os
import pathlib
import resource
import subprocess
import sys
import time

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent

# Error bound per K (Wolfram, evidence/MAX-CPU/README.md "Tolerances"):
#   g[n_,u_]:=n u/(1-n u); u32=2^-24; u64=2^-53
#   ref: g[K-1,u32]+g[K-1,u64]   max: 2 g[K-1,u32]
# Elementwise |C - R| <= tol * (|A| @ |B|), evaluated in float64.
TOL = {
    1: (0.0, 0.0),
    5: (2.384186363890841e-7, 4.768372718899898e-7),
    16: (8.940704726574863e-7, 1.788140941984304e-6),
    17: (9.536752276781760e-7, 1.907350451803638e-6),
    128: (7.569847202727132e-6, 1.513969437725460e-5),
    256: (1.519941546475356e-5, 3.039883087288574e-5),
}
SHAPES = [(1, 1, 1), (3, 5, 7), (16, 16, 8), (33, 17, 9), (64, 128, 32), (256, 256, 256)]


def load_omega(lib):
    # RTLD_GLOBAL puts omega2_omatmul in the process scope that the glue's dlopen(NULL) searches.
    ctypes.CDLL(str(lib), mode=ctypes.RTLD_GLOBAL)


def bf16_bits(x):
    """float32 -> bf16 bit patterns, round to nearest even."""
    u = np.asarray(x, np.float32).view(np.uint32).astype(np.uint64)
    return ((u + 0x7FFF + ((u >> 16) & 1)) >> 16).astype(np.uint16)


def bf16_round(x):
    """float32 values exactly representable in bf16 (so the in-graph cast is exact)."""
    return (bf16_bits(x).astype(np.uint32) << 16).view(np.float32).reshape(np.shape(x))


def max_mods():
    from max.driver import CPU, Buffer
    from max.dtype import DType
    from max.engine import InferenceSession
    from max.graph import DeviceRef, Graph, TensorType, ops

    return CPU, Buffer, DType, InferenceSession, DeviceRef, Graph, TensorType, ops


def build_graph(kind, M, K, N, kernels):
    CPU, Buffer, DType, InferenceSession, DeviceRef, Graph, TensorType, ops = max_mods()
    dev = DeviceRef.CPU()
    f32a = TensorType(DType.float32, [M, K], dev)
    f32b = TensorType(DType.float32, [K, N], dev)
    s3 = TensorType(DType.int64, [3], dev)
    abt = TensorType(DType.bfloat16, [M * K + K * N], dev)
    cout = [TensorType(DType.float32, [M, N], dev)]

    def cat(a, b):
        return ops.concat(
            [
                ops.reshape(ops.cast(a, DType.bfloat16), [M * K]),
                ops.reshape(ops.cast(b, DType.bfloat16), [K * N]),
            ],
            axis=0,
        )

    def omega(ab, s):
        return ops.custom("omega_matmul", device=dev, values=[ab, s], out_types=cout)[0].tensor

    if kind == "both":
        fwd, types = (lambda a, b, s: (omega(cat(a, b), s), ops.matmul(a, b))), [f32a, f32b, s3]
    elif kind == "omega":
        fwd, types = (lambda a, b, s: omega(cat(a, b), s)), [f32a, f32b, s3]
    elif kind == "omega_nocat":
        fwd, types = omega, [abt, s3]
    elif kind == "concat":
        fwd, types = cat, [f32a, f32b]
    elif kind == "matmul":
        fwd, types = (lambda a, b: ops.matmul(a, b)), [f32a, f32b]
    else:
        raise ValueError(kind)
    return Graph(f"om_{kind}_{M}x{K}x{N}", forward=fwd, input_types=types,
                 custom_extensions=[pathlib.Path(kernels)])


def session():
    CPU = max_mods()[0]
    return max_mods()[3](devices=[CPU()])


def inputs(kind, a, b, shape):
    Buffer, DType = max_mods()[1], max_mods()[2]
    s = Buffer.from_numpy(np.array(shape, np.int64))
    if kind == "omega_nocat":
        ab = np.concatenate([bf16_bits(a).ravel(), bf16_bits(b).ravel()])
        return [Buffer.from_numpy(ab).view(DType.bfloat16), s]
    fa, fb = Buffer.from_numpy(np.ascontiguousarray(a)), Buffer.from_numpy(np.ascontiguousarray(b))
    return [fa, fb, s] if kind in ("both", "omega") else [fa, fb]


def judge(c, r, a, b, tol):
    """max ratio |c-r| / (tol*|A||B|); <= 1 passes. Zero tolerance means exact equality."""
    bound = tol * (np.abs(a.astype(np.float64)) @ np.abs(b.astype(np.float64)))
    err = np.abs(c.astype(np.float64) - r.astype(np.float64))
    if tol == 0.0:
        return (0.0 if np.array_equal(err, np.zeros_like(err)) else float("inf")), float(err.max())
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(bound > 0, err / bound, np.where(err > 0, np.inf, 0.0))
    return float(ratio.max()), float(err.max())


def cases(M, K, N, rng):
    out = [("random", bf16_round(rng.standard_normal((M, K)).astype(np.float32)),
            bf16_round(rng.standard_normal((K, N)).astype(np.float32)))]
    out.append(("zeros", np.zeros((M, K), np.float32), np.zeros((K, N), np.float32)))
    if K == N:
        out.append(("identity", out[0][1], np.eye(K, dtype=np.float32)))
    if (M, K, N) == (16, 16, 8):
        big = np.float32(2.0**60)
        out.append(("large", out[0][1] * big, out[0][2] * big))
    return out


def cmd_check(args):
    load_omega(args.lib)
    sess, rng, rows, ok = session(), np.random.default_rng(args.seed), [], True
    for M, K, N in SHAPES:
        t = time.monotonic()
        model = sess.load(build_graph("both", M, K, N, args.kernels))
        load_s = time.monotonic() - t
        tref, tmax = TOL[K]
        for name, a, b in cases(M, K, N, rng):
            o = model.execute(*inputs("both", a, b, [M, K, N]))
            c, r = o[0].to_numpy(), o[1].to_numpy()
            ref = a.astype(np.float64) @ b.astype(np.float64)
            rr, er = judge(c, ref, a, b, tref)
            rm, em = judge(c, r, a, b, tmax)
            exact = name in ("zeros", "identity")
            passed = rr <= 1.0 and rm <= 1.0 and (not exact or np.array_equal(c, ref.astype(np.float32)))
            ok &= bool(passed) and bool(np.isfinite(c).all())
            row = dict(shape=[M, K, N], case=name, load_s=load_s, tol_ref=tref, tol_max=tmax,
                       ratio_ref=rr, maxerr_ref=er, ratio_max=rm, maxerr_max=em,
                       result="PASS" if passed else "FAIL")
            rows.append(row)
            print(f"{M}x{K}x{N} {name:8s} ratio_ref={rr:.3g} maxerr_ref={er:.3g} "
                  f"ratio_max={rm:.3g} maxerr_max={em:.3g} {row['result']}", flush=True)
    pathlib.Path(args.out).write_text(json.dumps(dict(lib=str(args.lib), rows=rows), indent=1))
    print("OMEGA_MAX_CHECK:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def cmd_neg_shape(args):
    load_omega(args.lib)
    CPU, Buffer, DType, InferenceSession, DeviceRef, Graph, TensorType, ops = max_mods()
    M, K, N = 16, 16, 8
    model = session().load(build_graph("omega", M, K, N, args.kernels))
    rng = np.random.default_rng(args.seed)
    a = bf16_round(rng.standard_normal((M, K)).astype(np.float32))
    b = bf16_round(rng.standard_normal((K, N)).astype(np.float32))
    rows, ok = [], True
    # ab holds 16*16+16*8 = 384 elements, c holds 128; only the declared shape changes.
    refused = "omega_matmul refused: status 0 result "
    for shape, want in (([16, 15, 8], refused + "2"), ([5000, 16, 8], refused + "1"),
                        ([0, 16, 8], refused + "1"), ([12, 16, 12], refused + "3")):
        try:
            model.execute(*inputs("omega", a, b, shape))
            got = "returned"
        except Exception as e:  # MAX surfaces the glue's raise as an execution error
            got = str(e) or repr(e)
        hit = want in got
        ok &= hit
        rows.append(dict(shape=shape, want=want, got=got, result="PASS" if hit else "FAIL"))
        print(f"shape={shape} want '{want}' got: {got} -> {'PASS' if hit else 'FAIL'}", flush=True)
    # The refused calls must leave the model usable and correct.
    c = model.execute(*inputs("omega", a, b, [M, K, N]))[0].to_numpy()
    ratio, _ = judge(c, a.astype(np.float64) @ b.astype(np.float64), a, b, TOL[K][0])
    ok &= ratio <= 1.0
    rows.append(dict(after_refusals="valid call", ratio_ref=ratio, result="PASS" if ratio <= 1 else "FAIL"))
    print(f"valid call after refusals ratio_ref={ratio:.3g} {'PASS' if ratio <= 1 else 'FAIL'}")
    try:
        dev = DeviceRef.CPU()
        Graph("om_bad_matmul", forward=lambda x, y: ops.matmul(x, y),
              input_types=[TensorType(DType.float32, [16, 16], dev), TensorType(DType.float32, [15, 8], dev)])
        got, hit = "constructed", False
    except Exception as e:
        got, hit = str(e).strip().splitlines()[0], True
    ok &= hit
    rows.append(dict(graph="ops.matmul [16,16]x[15,8]", got=got, result="PASS" if hit else "FAIL"))
    print(f"graph construction ops.matmul [16,16]x[15,8]: {got} -> {'PASS' if hit else 'FAIL'}")
    pathlib.Path(args.out).write_text(json.dumps(rows, indent=1))
    print("OMEGA_MAX_NEG_SHAPE:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def cmd_neg_load(args):
    """Expect the kernels dir to fail (load or execute) with `args.want` in the error."""
    load_omega(args.lib)
    M, K, N = 16, 16, 8
    a, b = np.ones((M, K), np.float32), np.ones((K, N), np.float32)
    try:
        model = session().load(build_graph("omega", M, K, N, args.kernels))
        model.execute(*inputs("omega", a, b, [M, K, N]))
        got = "ran"
    except Exception as e:
        got = str(e)
    hit = args.want in got
    print(f"kernels={args.kernels}\nwant '{args.want}'\ngot: {got}")
    print("OMEGA_MAX_NEG_LOAD:", "PASS" if hit else "FAIL")
    return 0 if hit else 1


def cmd_measure(args):
    load_omega(args.lib)
    M, K, N = args.shape
    rng = np.random.default_rng(args.seed)
    a = bf16_round(rng.standard_normal((M, K)).astype(np.float32))
    b = bf16_round(rng.standard_normal((K, N)).astype(np.float32))
    model = session().load(build_graph(args.op, M, K, N, args.kernels))
    ins = inputs(args.op, a, b, [M, K, N])
    u16 = max_mods()[2].uint16
    # numpy has no bf16: the concat-only graph's output is read back through a uint16 view.
    done = (lambda o: o[0].view(u16).to_numpy()) if args.op == "concat" else (lambda o: o[0].to_numpy())
    done(model.execute(*ins))
    first = time.monotonic_ns()
    for _ in range(args.warmup):
        done(model.execute(*ins))
    lat = []
    for _ in range(args.iters):
        t = time.perf_counter_ns()
        done(model.execute(*ins))
        lat.append(time.perf_counter_ns() - t)
    rec = dict(op=args.op, shape=[M, K, N], cache=args.cache, cold_ns=first - args.t0,
               iters=args.iters, warmup=args.warmup, lat_ns=lat,
               p50_ns_numpy=float(np.percentile(lat, 50)), p99_ns_numpy=float(np.percentile(lat, 99)),
               maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
               affinity=sorted(os.sched_getaffinity(0)))
    pathlib.Path(args.out).write_text(json.dumps(rec))
    print(f"{args.op} {M}x{K}x{N} cache={args.cache} cold_ms={rec['cold_ns']/1e6:.1f} "
          f"p50_us={rec['p50_ns_numpy']/1e3:.2f} p99_us={rec['p99_ns_numpy']/1e3:.2f} "
          f"maxrss_kib={rec['maxrss_kib']}", flush=True)
    return 0


def cmd_measure_all(args):
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for M, K, N in ((16, 16, 8), (256, 256, 256)):
        for op in ("omega", "omega_nocat", "concat", "matmul"):
            cache = out / f"cache-{op}-{M}x{K}x{N}"
            for state in ("fresh", "warm"):
                if state == "fresh":
                    subprocess.run(["rm", "-rf", str(cache)], check=True)
                f = out / f"{op}-{M}x{K}x{N}-{state}.json"
                env = dict(os.environ, MODULAR_CACHE_DIR=str(cache))
                cmd = [sys.executable, __file__, "measure", "--lib", str(args.lib), "--kernels",
                       str(args.kernels), "--op", op, "--shape", str(M), str(K), str(N),
                       "--iters", str(args.iters), "--cache", state, "--out", str(f),
                       "--t0", str(time.monotonic_ns())]
                subprocess.run(cmd, check=True, env=env)
                r = json.loads(f.read_text())
                rows.append([op, f"{M}x{K}x{N}", state, r["cold_ns"], r["iters"],
                             r["p50_ns_numpy"], r["p99_ns_numpy"], r["maxrss_kib"]])
    head = ["op", "shape", "cache", "cold_ns", "iters", "p50_ns", "p99_ns", "maxrss_kib"]
    (out / "summary.tsv").write_text("\n".join("\t".join(map(str, x)) for x in [head] + rows) + "\n")
    print((out / "summary.tsv").read_text())
    return 0


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("check", "neg-shape", "neg-load", "measure", "measure-all"):
        s = sub.add_parser(name)
        s.add_argument("--lib", required=True)
        s.add_argument("--kernels", default=str(HERE / "kernels"))
        s.add_argument("--seed", type=int, default=20261030)
        s.add_argument("--out", required=name != "neg-load")
        if name == "neg-load":
            s.add_argument("--want", required=True)
        if name in ("measure", "measure-all"):
            s.add_argument("--iters", type=int, default=300)
        if name == "measure":
            s.add_argument("--op", required=True,
                           choices=["omega", "omega_nocat", "concat", "matmul"])
            s.add_argument("--shape", type=int, nargs=3, required=True)
            s.add_argument("--warmup", type=int, default=20)
            s.add_argument("--cache", default="fresh")
            s.add_argument("--t0", type=int, required=True)
    a = p.parse_args()
    # MAX 26.7.0 Graph() creates an Accelerator() (a CUDA context) whenever one is visible, even
    # for an all-CPU graph. Refuse unless the GPU is hidden: run.sh exports CUDA_VISIBLE_DEVICES=.
    from max.driver import accelerator_count

    if accelerator_count() != 0:
        print("omega_max.py: an accelerator is visible; export CUDA_VISIBLE_DEVICES= "
              "(this harness must not open the GPU)", file=sys.stderr)
        sys.exit(2)
    fn = {"check": cmd_check, "neg-shape": cmd_neg_shape, "neg-load": cmd_neg_load,
          "measure": cmd_measure, "measure-all": cmd_measure_all}[a.cmd]
    sys.exit(fn(a))


if __name__ == "__main__":
    main()
