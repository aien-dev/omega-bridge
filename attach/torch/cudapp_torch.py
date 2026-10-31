"""cudapp_torch: PyTorch custom operators that run on the NVIDIA GB10 through CUDA++ (aien-dev/CUDApp).

    torch.ops.cudapp.mm(a, b)          a (m, k) @ b (k, n) -> (m, n) float32, omega_gpu_gemm_ex
    torch.ops.cudapp.swiglu(gate, up)  silu(gate) * up, float32, omega_gpu_swiglu_f32

Registered with torch.library.custom_op on CPU tensors: the operands are host memory, CUDA++ stages them to the
chip, runs kernels from Omega's own code generator (no CUDA toolkit, no NVIDIA user-space library) and copies the
result back. Arithmetic (CUDApp src/omega_gpu_gemm_ex.h, src/omega_gpu_elementwise_api.h):
    mm      bf16 x bf16 and f16 x f16 native HMMA with fp32 accumulation; anything with f32 the bf16x3 route
            (not exact fp32); the k parts summed on the host in double.
    swiglu  MUFU.EX2 / MUFU.RCP (each about 2^-22 relative).
The library is CUDA++'s libomega_gpu.a linked into one shared object (build.sh, CUDAPP_TORCH_LIB).

MIGRATION-PENDING host glue (Python): torch.library registration is a Python/C++ ABI, which seeded Omega cannot
emit yet. MIGRATION_PENDING below marks it; the named successor is the omega_native.py binding that
omega-bridge tools/native writes (the python word of src/native.om) for an Omega unit that calls the CUDA++ entries, once Omega
code can call host functions.
"""
import ctypes
import os

import torch

MIGRATION_PENDING = True

OP_N, OP_T = 0, 1
DT = {torch.float32: 0, torch.bfloat16: 1, torch.float16: 2}


class _Info(ctypes.Structure):
    _fields_ = [("route", ctypes.c_uint32), ("core_type", ctypes.c_uint32),
                ("core_calls", ctypes.c_uint64), ("host_fixed", ctypes.c_uint64)]


class _GemmEx(ctypes.Structure):  # OmegaGemmExArgs, src/omega_gpu_gemm_ex.h
    _fields_ = [("op_a", ctypes.c_int), ("op_b", ctypes.c_int),
                ("m", ctypes.c_uint64), ("n", ctypes.c_uint64), ("k", ctypes.c_uint64), ("batch", ctypes.c_uint64),
                ("a_type", ctypes.c_int), ("b_type", ctypes.c_int), ("c_type", ctypes.c_int),
                ("a", ctypes.c_void_p), ("lda", ctypes.c_uint64), ("stride_a", ctypes.c_uint64),
                ("b", ctypes.c_void_p), ("ldb", ctypes.c_uint64), ("stride_b", ctypes.c_uint64),
                ("c", ctypes.c_void_p), ("ldc", ctypes.c_uint64), ("stride_c", ctypes.c_uint64),
                ("alpha", ctypes.c_float), ("beta", ctypes.c_float),
                ("compute", ctypes.c_int), ("scale", ctypes.c_int),
                ("scale_a", ctypes.c_void_p), ("scale_b", ctypes.c_void_p),
                ("scale_stride_a", ctypes.c_uint64), ("scale_stride_b", ctypes.c_uint64),
                ("block_m", ctypes.c_uint32), ("block_n", ctypes.c_uint32), ("block_k", ctypes.c_uint32),
                ("info", ctypes.POINTER(_Info))]


_lib = ctypes.CDLL(os.environ.get("CUDAPP_TORCH_LIB", os.path.join(os.path.dirname(__file__), "libcudapp_attach.so")))
_lib.omega_gpu_gemm_ex.argtypes = [ctypes.POINTER(_GemmEx)]
_lib.omega_gpu_gemm_ex.restype = ctypes.c_int
_lib.omega_gpu_gemm_rc_name.argtypes = [ctypes.c_int]
_lib.omega_gpu_gemm_rc_name.restype = ctypes.c_char_p
_lib.omega_gpu_swiglu_f32.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
_lib.omega_gpu_swiglu_f32.restype = ctypes.c_int
_lib.omega_gpu_elementwise_rc_name.argtypes = [ctypes.c_int]
_lib.omega_gpu_elementwise_rc_name.restype = ctypes.c_char_p
_lib.omega_gpu_gemm_ex_test_set_mutant.argtypes = [ctypes.c_int]
_lib.omega_gpu_gemm_ex_test_set_mutant.restype = None

last_route = None  # OmegaGemmRoute of the last cudapp::mm (3 = BF16X3, 1 = NATIVE)


def set_gemm_mutant(m):
    """Negative control: 1 drops the last k element of every product (CUDApp's own red check)."""
    _lib.omega_gpu_gemm_ex_test_set_mutant(m)


@torch.library.custom_op("cudapp::mm", mutates_args=())
def mm(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    global last_route
    if a.dim() != 2 or b.dim() != 2 or a.shape[1] != b.shape[0]:
        raise ValueError(f"cudapp::mm needs (m, k) @ (k, n), got {tuple(a.shape)} @ {tuple(b.shape)}")
    if a.dtype not in DT or b.dtype not in DT or a.device.type != "cpu" or b.device.type != "cpu":
        raise TypeError("cudapp::mm takes CPU float32, bfloat16 or float16 tensors")
    a, b = a.contiguous(), b.contiguous()
    m, k = a.shape
    n = b.shape[1]
    c = torch.empty((m, n), dtype=torch.float32)
    if m == 0 or n == 0:
        return c
    if k == 0:
        return c.zero_()
    info = _Info()
    args = _GemmEx(op_a=OP_N, op_b=OP_N, m=m, n=n, k=k, batch=1, a_type=DT[a.dtype], b_type=DT[b.dtype], c_type=0,
                   a=a.data_ptr(), lda=k, b=b.data_ptr(), ldb=n, c=c.data_ptr(), ldc=n, alpha=1.0, beta=0.0,
                   info=ctypes.pointer(info))
    rc = _lib.omega_gpu_gemm_ex(ctypes.byref(args))
    if rc != 0:
        raise RuntimeError(f"omega_gpu_gemm_ex: {_lib.omega_gpu_gemm_rc_name(rc).decode()} ({rc})")
    last_route = info.route
    return c


@mm.register_fake
def _(a, b):
    return a.new_empty((a.shape[0], b.shape[1]), dtype=torch.float32)


@torch.library.custom_op("cudapp::swiglu", mutates_args=())
def swiglu(gate: torch.Tensor, up: torch.Tensor) -> torch.Tensor:
    if gate.shape != up.shape or gate.dtype != torch.float32 or up.dtype != torch.float32:
        raise TypeError("cudapp::swiglu takes two float32 CPU tensors of one shape")
    if gate.device.type != "cpu" or up.device.type != "cpu" or gate.numel() >= 2 ** 32:
        raise TypeError("cudapp::swiglu takes CPU tensors of fewer than 2^32 elements")
    gate, up = gate.contiguous(), up.contiguous()
    out = torch.empty_like(gate)
    if gate.numel() == 0:
        return out
    rc = _lib.omega_gpu_swiglu_f32(gate.numel(), gate.data_ptr(), up.data_ptr(), out.data_ptr(), None)
    if rc != 0:
        raise RuntimeError(f"omega_gpu_swiglu_f32: {_lib.omega_gpu_elementwise_rc_name(rc).decode()} ({rc})")
    return out


@swiglu.register_fake
def _(gate, up):
    return torch.empty_like(gate)
