# Python caller for the omega-bridge native call ABI v1 test library (ctypes, standard library only).
import ctypes, os, sys
lib = ctypes.CDLL(os.path.join(os.path.dirname(os.path.abspath(__file__)), "libomega_native.so"))
u64, u32, P = ctypes.c_uint64, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint64)
for name in ("omega_madd", "omega_smadd"):
    getattr(lib, name).argtypes, getattr(lib, name).restype = [P, u64, u64, u64], u32
lib.omega_fill.argtypes, lib.omega_fill.restype = [P, ctypes.c_void_p, u64, u64], u32
SENTINEL = 6148914691236517205
fails = 0
def check(name, ok):
    global fails
    print(("PASS " if ok else "FAIL ") + name)
    fails += not ok
def bits(v):  # signed Python int -> canonical 64-bit two's-complement bits
    return v & (2**64 - 1)
def signed(b):
    return b - 2**64 if b >= 2**63 else b
r = u64(0)
check("madd 3*5+7 = 22", lib.omega_madd(ctypes.byref(r), 3, 5, 7) == 0 and r.value == 22)
check("madd wraps = 3", lib.omega_madd(ctypes.byref(r), 2**64 - 1, 2, 5) == 0 and r.value == 3)
check("madd large", lib.omega_madd(ctypes.byref(r), 1311768467463790320, 18364758544493064720, 1085102592571150095) == 0
      and r.value == 3637949782307626511)
check("madd signed bits = -13", lib.omega_madd(ctypes.byref(r), bits(-3), 5, 2) == 0 and signed(r.value) == -13)
r = u64(SENTINEL)
check("smadd overflow traps 1, result unchanged", lib.omega_smadd(ctypes.byref(r), 2**62, 4, 0) == 1 and r.value == SENTINEL)
buf = (u64 * 4)()
check("fill k=1 traps 3, result unchanged", lib.omega_fill(ctypes.byref(r), buf, 4, 1) == 3 and r.value == SENTINEL)
check("writes before the trap stay visible", list(buf) == [11, 22, 0, 0])
check("fill k=0 = 3", lib.omega_fill(ctypes.byref(r), buf, 4, 0) == 0 and r.value == 3 and list(buf) == [11, 22, 33, 0])
check("null result refused 32", lib.omega_madd(None, 3, 5, 7) == 32)
print(("FAIL " if fails else "PASS ") + "%d failure(s)" % fails)
sys.exit(fails != 0)
