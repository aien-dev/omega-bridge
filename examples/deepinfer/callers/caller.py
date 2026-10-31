"""Python caller for examples/deepinfer/flops_pairs.om: python3 -I caller.py BUILD_DIR. Every Omega
declaration comes from the generated omega_native.py; nothing is typed by hand here. Expected values:
evidence/deepinfer-flops-pairs/wolfram.md."""
import ctypes
import sys

sys.path.insert(0, sys.argv[1])
import omega_native as om  # noqa: E402

FAILS = 0


def check(name, ok):
    global FAILS
    print("PASS" if ok else "FAIL", name)
    FAILS += 0 if ok else 1


VS = [
    ("floor_prefix", (9, 2), 0, 20),
    ("capped_prefix", (9, 2, 3), 0, 18),
    ("pairs", (3, 9, 2, 3), 0, 16),
    ("pairs", (3, 9, 2, 0), 0, 18),
    ("pairs", (0, 4096, 1, 512), 0, 1966336),
    ("floor_prefix", (3037000499, 1), 0, 4611686016981624750),
    ("capped_prefix", (4611686018427387904, 1, 2), 0, 9223372036854775807),
    ("floor_prefix", (3037000500, 1), 1, 0),
    ("capped_prefix", (4611686018427387905, 1, 2), 1, 0),
    ("capped_prefix", (0, 4294967296, 2147483648), 1, 0),
    ("floor_prefix", (-1, 1), 9, 0),
    ("floor_prefix", (5, 0), 9, 0),
    ("pairs", (5, 3, 1, 0), 9, 0),
    ("pairs", (0, 3, 1, -1), 9, 0),
]
SENTINEL = 0x5A5A5A5A5A5A5A5A

check("ident: library == binding", om.omega2_ident_flops_pairs() == om.OMEGA2_IDENT_flops_pairs)
for fn, args, status, want in VS:
    r = ctypes.c_uint64(SENTINEL)
    st = getattr(om, "omega2_" + fn)(ctypes.byref(r), *(a & 0xFFFFFFFFFFFFFFFF for a in args))
    got = r.value - (1 << 64) if r.value >> 63 else r.value
    check("%s %s -> status %d" % (fn, " ".join(map(str, args)), st),
          st == status and (got == want if st == om.OMEGA_OK else r.value == SENTINEL))
check("null result refused 32", om.omega2_pairs(None, 0, 3, 1, 0) == om.OMEGA_BAD_ARG)
try:
    om.omega2_pairs(ctypes.byref(ctypes.c_uint64()), -1, 3, 1, 0)
    check("negative int refused by the binding", False)
except ctypes.ArgumentError:
    check("negative int refused by the binding (a long is passed as its two's-complement bits)", True)
sys.exit(1 if FAILS else 0)
