# MAX CPU custom op "omega_matmul": glue only. The matmul is the Omega unit max-cpu/omatmul.om,
# compiled by tools/native into libomega_native.so (export omega2_omatmul, native ABI v2,
# docs/NATIVE-ABI.md).
#
#   c     output float32 [M, N]          written by Omega as f32 bit patterns
#   ab    input  bfloat16 [M*K + K*N]    A row-major, then B row-major (one view: six-slot limit)
#   shape input  int64 [3]               [M, K, N]
#
# Symbol resolution: the caller loads libomega_native.so with RTLD_GLOBAL before the graph runs
# (max-cpu/omega_max.py). MAX 26.7's kernel JIT does not search the process image, so a plain
# external_call["omega2_omatmul", ...] fails at model load with "Symbols not found"
# (max-cpu/run.sh keeps that as a control). The call therefore resolves the same C symbol through
# dlopen(NULL)/dlsym (OwnedDLHandle() with no path), and a missing symbol raises.
#
# Omega refuses a bad shape with a nonzero result and leaves C untouched; the bridge refuses a bad
# pointer or length with a nonzero status. Either is raised here, so MAX fails the execution
# instead of returning C.

import extensibility
from extensibility import InputTensor, OutputTensor
from std.ffi import OwnedDLHandle, external_call


@extensibility.register("omega_matmul", type="cpu")
struct OmegaMatmul:
    @staticmethod
    def execute[
        target: StaticString,
    ](
        c: OutputTensor[dtype=DType.float32, rank=2, ...],
        ab: InputTensor[dtype=DType.bfloat16, rank=1, ...],
        shape: InputTensor[dtype=DType.int64, rank=1, ...],
    ) raises:
        comptime assert target == "cpu", "omega_matmul is a CPU op"
        var result: UInt64 = 0
        var process = OwnedDLHandle()
        var status = process.get_function[UInt32]("omega2_omatmul")(
            Pointer(to=result),
            ab.unsafe_ptr[DType.uint16](),
            UInt64(ab.size()),
            c.unsafe_ptr[DType.uint32](),
            UInt64(c.size()),
            shape.unsafe_ptr[DType.uint64](),
            UInt64(shape.size()),
        )
        if status != 0 or result != 0:
            raise Error(
                "omega_matmul refused: status "
                + String(status)
                + " result "
                + String(result)
            )
