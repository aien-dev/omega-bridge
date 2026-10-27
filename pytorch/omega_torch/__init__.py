"""torch.compile(model, backend="omega"): core-ATen graphs run on Omega-generated AArch64 kernels.

Interim Python glue (migration step, not the destination). This module only registers the backend,
walks the FX graph, allocates output tensors and calls compiled Omega units through the omega-bridge
native call ABI v1 (docs/NATIVE-ABI.md). It never computes a tensor value: every value an output holds
was written by machine code the seeded Omega compiler produced from pytorch/kernels/*.om.

Successor (named in docs/OMEGA-TORCH.md): the graph walk, shape specialisation and op dispatch move to
an Omega unit behind the same bridge C ABI, driven from a PrivateUse1 "omega" device, so the Python
side shrinks to the device registration PyTorch itself requires.

Fail closed: an op outside SUPPORTED raises OmegaRefused at compile time, listing every refused node.
An eager fallback happens only for ops the caller names in OMEGA_TORCH_FALLBACK (or set_fallback()),
and every such call is counted in STATS["eager_fallback_calls"].
"""

import ctypes
import hashlib
import os
import subprocess
import tempfile
import threading
import time

import torch
from torch._dynamo import register_backend
from torch._functorch.aot_autograd import aot_module_simplified
from torch._decomp import core_aten_decompositions

aten = torch.ops.aten

# omega-mv main 369dbc96daa1684db2d7c2c7085bbf16b3fd77ee, seed/out/omc as committed (not rebuilt).
OMC_SHA256 = "2c82480596bbdc50cda9626866209ef662d5834f278f839ff4ce0250c495029f"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
KERNEL_DIR = os.environ.get("OMEGA_TORCH_KERNELS", os.path.join(ROOT, "pytorch", "kernels"))
CACHE = os.environ.get("OMEGA_TORCH_CACHE", os.path.join(ROOT, "build", "torch"))

STATS = {"graphs": 0, "graph_cache_hits": 0, "omega_calls": 0, "eager_fallback_calls": 0, "units_built": 0,
         "libraries_built": 0, "per_op": {}}
# Compile-side wall time in ns, summed over the process (perf_counter_ns around each phase): omc on
# kernels, omc on src/native.om, the native binder, cc, dlopen, and _lower as a whole (which contains
# all of the former when a unit is built). Read by pytorch/bench_split.py; never reset by reset_stats().
TIMES = {"omc": 0, "native_omc": 0, "binder": 0, "cc": 0, "dlopen": 0, "lower": 0}
_FALLBACK = set(filter(None, os.environ.get("OMEGA_TORCH_FALLBACK", "").split(",")))
_LOCK = threading.Lock()
_LIBS = {}  # library key -> {unit name: ctypes function}
_GRAPHS = {}  # graph key (_graph_key) -> the lowered graph function
_NATIVE = None

STATUS = {1: "overflow", 2: "divide by zero", 3: "bounds", 4: "loop bound", 5: "conversion",
          6: "resource", 7: "shift", 32: "foreign argument refused", 33: "reentry",
          34: "runtime entry not provided", 35: "no stack"}


class OmegaRefused(RuntimeError):
    """The graph holds work the Omega backend does not implement. Nothing ran."""


class OmegaCallError(RuntimeError):
    """A compiled Omega unit returned a nonzero status (trap or refused argument)."""


def set_fallback(ops):
    """Name the ops (e.g. "aten.tanh.default") that may run in eager PyTorch. Each call is counted."""
    _FALLBACK.clear()
    _FALLBACK.update(ops)


def reset_stats():
    STATS.update(graphs=0, graph_cache_hits=0, omega_calls=0, eager_fallback_calls=0, per_op={})


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _omc():
    path = os.environ.get("OMEGA_OMC")
    if not path:
        raise OmegaRefused("set OMEGA_OMC to omega-mv seed/out/omc (sha256 %s)" % OMC_SHA256)
    got = _sha(path)
    if got != OMC_SHA256:
        raise OmegaRefused("omc sha256 %s is not the pinned %s" % (got, OMC_SHA256))
    return path


def _compile_om(src, out, phase="omc"):
    t0 = time.perf_counter_ns()
    with open(out, "wb") as o, tempfile.TemporaryFile() as err:
        rc = subprocess.run([_omc()], input=src, stdout=o, stderr=err).returncode
        err.seek(0)
        msg = err.read().decode(errors="replace").strip()
    TIMES[phase] += time.perf_counter_ns() - t0
    if rc != 0 or msg:
        os.unlink(out)
        raise OmegaRefused("omc refused the unit (rc=%d): %s" % (rc, msg))


def _native():
    global _NATIVE
    if _NATIVE is None:
        os.makedirs(CACHE, exist_ok=True)
        path = os.path.join(CACHE, "native-%s" % OMC_SHA256[:12])
        with open(os.path.join(ROOT, "src", "native.om"), "rb") as f:
            _compile_om(f.read(), path, "native_omc")
        os.chmod(path, 0o700)
        _NATIVE = path
    return _NATIVE


def unit_source(kernel, consts, name=None):
    """The unit text: one "const NAME ulong V" line per shape constant, then the kernel file. With name,
    the entry function is renamed to it, so that one library can hold several specialisations of a kernel
    (the binding refuses two units with the same name); nothing else in the text changes."""
    head = "".join("const %s ulong %d\n" % (k, v) for k, v in consts)
    with open(os.path.join(KERNEL_DIR, kernel + ".om"), "rb") as f:
        body = b"\n" + f.read()
    if name is not None and name != kernel:
        old, new = b"\nfn %s " % kernel.encode(), b"\nfn %s " % name.encode()
        if body.count(old) != 1:
            raise OmegaRefused("kernel %s: entry 'fn %s' must appear exactly once" % (kernel, kernel))
        body = body.replace(old, new)
    return head.encode() + body[1:]


def load_units(units):
    """Build and load ONE library holding every unit of a graph, and return its ctypes functions in order.

    units: a list of (kernel, consts, nargs). Equal (kernel, consts) pairs share one unit. Each distinct
    unit is compiled by omc; all of them go to src/native.om in a single frame stream, so the binding is
    one C file, compiled by one cc run and opened by one dlopen. The library is cached on disk under
    build/torch/<sha256 of the compiler pin, src/native.om and every unit source in order>.
    Each function is omega_<name>(uint64_t *result, (ptr, len) * nargs), where name is the kernel for its
    first specialisation in the library and kernel_<j> for the j-th further one."""
    if not units:
        return []
    names, srcs, seen = {}, [], {}
    for kernel, consts, nargs in units:
        k = (kernel, tuple(consts))
        if k not in names:
            j = seen.get(kernel, 0)
            seen[kernel] = j + 1
            names[k] = (kernel if j == 0 else "%s_%d" % (kernel, j), nargs)
            srcs.append((names[k][0], unit_source(kernel, consts, names[k][0])))
    h = hashlib.sha256(OMC_SHA256.encode())
    with open(os.path.join(ROOT, "src", "native.om"), "rb") as f:
        h.update(f.read())
    for name, src in srcs:
        h.update(b"%d\0%s\0" % (len(src), name.encode()) + src)
    key = h.hexdigest()[:24]
    with _LOCK:
        lib = _LIBS.get(key)
        if lib is None:
            d = os.path.join(CACHE, key)
            os.makedirs(d, exist_ok=True)
            so = os.path.join(d, "libomega.so")
            if not os.path.exists(so):
                frames = []
                for name, src in srcs:
                    binp = os.path.join(d, name + ".bin")
                    _compile_om(src, binp)
                    with open(binp, "rb") as f:
                        code = f.read()
                    frames.append(src + b"\0" + b"%08d" % len(code) + code)
                cfile = os.path.join(d, "binding.c")
                t0 = time.perf_counter_ns()
                with open(cfile, "wb") as o:
                    rc = subprocess.run([_native()], input=b"".join(frames), stdout=o,
                                        stderr=subprocess.DEVNULL).returncode
                TIMES["binder"] += time.perf_counter_ns() - t0
                if rc != 0:
                    raise OmegaRefused("src/native.om refused units %s (exit %d)" % ([n for n, _ in srcs], rc))
                tmp = so + ".tmp"
                t0 = time.perf_counter_ns()
                subprocess.run(["cc", "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror", "-fPIC", "-shared",
                                "-o", tmp, cfile], check=True)
                TIMES["cc"] += time.perf_counter_ns() - t0
                os.replace(tmp, so)
                STATS["units_built"] += len(srcs)
                STATS["libraries_built"] += 1
            t0 = time.perf_counter_ns()
            dll = ctypes.CDLL(so)
            TIMES["dlopen"] += time.perf_counter_ns() - t0
            lib = {}
            for name, nargs in names.values():
                fn = getattr(dll, "omega_" + name)
                fn.argtypes = [ctypes.POINTER(ctypes.c_uint64)] + [ctypes.c_void_p, ctypes.c_uint64] * nargs
                fn.restype = ctypes.c_uint32
                lib[name] = fn
            _LIBS[key] = lib
    return [lib[names[(kernel, tuple(consts))][0]] for kernel, consts, _ in units]


def load_unit(kernel, consts, nargs):
    """One unit in a library of its own (load_units with a single unit)."""
    return load_units([(kernel, consts, nargs)])[0]


def call_unit(fn, name, tensors):
    """Call a bound unit on f32 CPU tensors. Zero copy: the binding receives each tensor's own storage
    address and element count, and the Omega code reads and writes that storage in place (the tensors are
    borrowed for the call). Raises on any nonzero status."""
    args = []
    for t in tensors:
        args += [t.data_ptr(), t.numel()]
    res = ctypes.c_uint64(0)
    st = fn(ctypes.byref(res), *args)
    if st != 0:
        raise OmegaCallError("omega_%s returned status %d (%s)" % (name, st, STATUS.get(st, "trap")))
    STATS["omega_calls"] += 1
    STATS["per_op"][name] = STATS["per_op"].get(name, 0) + 1


# ---- graph lowering -----------------------------------------------------------------------------

SUPPORTED = ("aten.mm.default", "aten.addmm.default", "aten.permute.default", "aten.add.Tensor",
             "aten.relu.default", "aten._softmax.default")

# Language limits at the pinned omc (OMEGESE 9.4): an array holds 1 .. 16777216 elements, and a
# function's local arrays total at most 4 MiB (softmax keeps one f64 row: 8 bytes per column).
OM_MAX_ARRAY = 16777216
OM_MAX_LOCAL_BYTES = 4 << 20


def _meta(n):
    v = n.meta.get("val") if hasattr(n, "meta") else None
    return v


def _static_shape(v):
    out = []
    for s in v.shape:
        if not isinstance(s, int):
            return None
        out.append(s)
    return out


def _check_tensor(v, why):
    if not isinstance(v, torch.Tensor):
        return why + ": not a tensor"
    if v.dtype != torch.float32:
        return why + ": dtype %s (only float32)" % v.dtype
    if v.device.type != "cpu":
        return why + ": device %s (only cpu)" % v.device
    if _static_shape(v) is None:
        return why + ": symbolic shape %s (compile with dynamic=False)" % (tuple(v.shape),)
    if any(s == 0 for s in v.shape):
        return why + ": empty tensor"
    if v.numel() > OM_MAX_ARRAY:
        return why + ": %d elements, above the Omega array limit %d (OMEGESE 9.4)" % (v.numel(), OM_MAX_ARRAY)
    return None


def _plan_node(n, users):
    """Return (kernel, consts, input nodes) for n, or a refusal string."""
    t = str(n.target)
    ins = [a for a in n.args if isinstance(a, torch.fx.Node)]
    for a in ins + [n]:
        bad = _check_tensor(_meta(a), "%s %s" % (t, a.name))
        if bad:
            return bad
    sh = lambda a: _static_shape(_meta(a))
    if n.kwargs:
        return "%s: keyword arguments %s not supported" % (t, dict(n.kwargs))
    if t == "aten.mm.default":
        a, b = n.args
        (M, K), (K2, N) = sh(a), sh(b)
        return ("mm", [("M", M), ("K", K), ("N", N), ("MK", M * K), ("KN", K * N), ("MN", M * N)], [a, b])
    if t == "aten.addmm.default":
        if len(n.args) != 3:
            return "aten.addmm: beta/alpha other than 1 not supported"
        c, a, b = n.args
        if len(sh(a)) != 2 or len(sh(b)) != 2:
            return "aten.addmm: operands must be 2-D"
        (M, K), (K2, N) = sh(a), sh(b)
        if sh(c) != [N]:
            return "aten.addmm: bias shape %s (only a 1-D bias of length N=%d)" % (sh(c), N)
        cs = [("M", M), ("K", K), ("N", N), ("MK", M * K)]
        p = b
        if p.op == "call_function" and str(p.target) == "aten.permute.default" and list(p.args[1]) == [1, 0] \
                and len(users[p]) == 1:
            # nn.Linear: read the [N,K] weight in place instead of materialising its transpose.
            return ("linear", cs + [("NK", N * K), ("MN", M * N)], [c, a, p.args[0]])
        return ("addmm", cs + [("KN", K * N), ("MN", M * N)], [c, a, b])
    if t == "aten.permute.default":
        x, dims = n.args
        if len(sh(x)) != 2 or list(dims) != [1, 0]:
            return "aten.permute: only 2-D [1, 0] (got dims %s on shape %s)" % (list(dims), sh(x))
        R, C = sh(x)
        return ("tr", [("R", R), ("C", C), ("RC", R * C)], [x])
    if t == "aten.add.Tensor":
        if len(n.args) != 2 or len(ins) != 2:
            return "aten.add.Tensor: only tensor + tensor with alpha 1"
        a, b = n.args
        if sh(a) != sh(b):
            return "aten.add.Tensor: broadcasting %s + %s not supported" % (sh(a), sh(b))
        return ("eadd", [("L", _meta(a).numel())], [a, b])
    if t == "aten.relu.default":
        (x,) = n.args
        return ("relu", [("L", _meta(x).numel())], [x])
    if t == "aten._softmax.default":
        x, dim, half = n.args
        r = len(sh(x))
        if half or (dim % r) != r - 1 or r != 2:
            return "aten._softmax: only 2-D over the last dim, half_to_float False"
        R, C = sh(x)
        if 8 * C > OM_MAX_LOCAL_BYTES:
            return "aten._softmax: row of %d columns exceeds the 4 MiB local-array limit" % C
        return ("softmax", [("R", R), ("C", C), ("RC", R * C)], [x])
    return "%s: no Omega kernel" % t


def _val_sig(v):
    """The part of a node's example value that its lowering depends on: for a tensor its dtype, shape,
    strides, device and layout (a cached plan for float32 must never serve a float64 graph)."""
    if isinstance(v, torch.Tensor):
        return ("tensor", str(v.dtype), tuple(str(s) for s in v.shape), tuple(str(s) for s in v.stride()),
                v.device.type, str(v.layout))
    return ("value", repr(v))


def _graph_key(gm):
    """sha256 over everything a lowered graph depends on: the compiler pin, src/native.om, every kernel
    source in KERNEL_DIR, the fallback set, and each node in order (op, target, arguments with nodes named
    by position, and _val_sig of its example value)."""
    h = hashlib.sha256(OMC_SHA256.encode())
    with open(os.path.join(ROOT, "src", "native.om"), "rb") as f:
        h.update(f.read())
    for name in sorted(os.listdir(KERNEL_DIR)):
        if name.endswith(".om"):
            with open(os.path.join(KERNEL_DIR, name), "rb") as f:
                h.update(b"\0%s\0" % name.encode() + f.read())
    h.update(repr(sorted(_FALLBACK)).encode())
    pos = {}
    for i, n in enumerate(gm.graph.nodes):
        pos[n] = i
        a = torch.fx.node.map_arg((n.args, n.kwargs), lambda x: "%%%d" % pos[x])
        h.update(repr((n.op, str(n.target), a, _val_sig(_meta(n)))).encode() + b"\n")
    return h.hexdigest()


def _lower(gm, example_inputs):
    """Lower an aten graph to one Omega library, or return the cached lowering of an identical graph."""
    gkey = _graph_key(gm)
    with _LOCK:
        run = _GRAPHS.get(gkey)
    if run is not None:
        STATS["graph_cache_hits"] += 1
        return run
    g = gm.graph
    users = {n: list(n.users) for n in g.nodes}
    steps, refused, fused = [], [], set()
    for n in g.nodes:
        if n.op in ("placeholder", "output"):
            continue
        if n.op != "call_function":
            refused.append("%s (%s): only call_function nodes" % (n.name, n.op))
            continue
        t = str(n.target)
        p = _plan_node(n, users) if t in SUPPORTED else "%s: no Omega kernel" % t
        if isinstance(p, tuple):
            if p[0] == "linear":
                fused.add(n.args[2])
            steps.append(("omega", n, p))
        elif t in _FALLBACK:
            steps.append(("eager", n, None))
        else:
            refused.append("%s: %s" % (n.name, p))
    steps = [s for s in steps if s[1] not in fused or len(users[s[1]]) != 1]
    if refused:
        raise OmegaRefused("Omega backend refuses this graph (nothing ran; no eager fallback):\n  "
                           + "\n  ".join(refused))
    units = [(p[0], p[1], len(p[2]) + 1) for kind, n, p in steps if kind == "omega"]
    fns = iter(load_units(units))
    compiled = []
    for kind, n, p in steps:
        if kind == "omega":
            kernel, consts, ins = p
            compiled.append((kind, n, kernel, next(fns), ins, _static_shape(_meta(n))))
        else:
            compiled.append((kind, n, None, None, None, None))
    placeholders = [n for n in g.nodes if n.op == "placeholder"]
    (out_node,) = [n for n in g.nodes if n.op == "output"]
    live_steps = [s for s in compiled if s[1] not in fused]
    STATS["graphs"] += 1

    def run(*args):
        env = {}
        for ph, a in zip(placeholders, args):
            if isinstance(a, torch.Tensor) and not a.is_contiguous():
                raise OmegaRefused("input %s is not contiguous; Omega kernels read row-major storage" % ph.name)
            env[ph] = a
        for kind, n, kernel, fn, ins, shape in live_steps:
            if kind == "omega":
                xs = [env[a] for a in ins]
                o = torch.empty(shape, dtype=torch.float32)
                call_unit(fn, kernel, xs + [o])
                env[n] = o
            else:
                STATS["eager_fallback_calls"] += 1
                a = torch.fx.node.map_arg(n.args, lambda x: env[x])
                k = torch.fx.node.map_arg(n.kwargs, lambda x: env[x])
                env[n] = n.target(*a, **k)
        return tuple(torch.fx.node.map_arg(out_node.args[0], lambda x: env[x]))

    run._omega_steps = [(s[0], s[2] or str(s[1].target)) for s in live_steps]
    with _LOCK:
        _GRAPHS[gkey] = run
    return run


@register_backend
def omega(gm, example_inputs):
    """torch.compile backend "omega": inference only, float32 CPU, static shapes."""
    if torch.is_grad_enabled() and any(getattr(x, "requires_grad", False) for x in example_inputs):
        raise OmegaRefused("autograd is not supported by the Omega backend (milestone 1); "
                           "run the compiled model under torch.no_grad()")
    if torch.cuda.is_available():
        raise OmegaRefused("a CUDA device is visible; milestone 1 is CPU-only (set CUDA_VISIBLE_DEVICES=)")

    def fw(g, inputs):
        t0 = time.perf_counter_ns()
        try:
            return _lower(g, inputs)
        finally:
            TIMES["lower"] += time.perf_counter_ns() - t0

    return aot_module_simplified(gm, example_inputs, fw_compiler=fw,
                                 decompositions=core_aten_decompositions())
