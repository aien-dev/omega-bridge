# Native ABI v2 oracle, Python (tests/native/v2/run.sh): the generated omega_native.py only. Importing it
# checks every unit's identity against the library.
import ctypes, sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
import omega_native as om

fails = 0
def check(name, ok):
    global fails
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        fails += 1

R0 = 0x5a5a5a5a5a5a5a5a
def res():
    return ctypes.c_uint64(R0)

check("ident vec", om.omega2_ident_vec() == om.OMEGA2_IDENT_vec)
r = res(); check("bsum abc = 294", om.omega2_bsum(ctypes.byref(r), b"abc", 3) == 0 and r.value == 294)
r = res(); check("bsum (None, 0) = 0", om.omega2_bsum(ctypes.byref(r), None, 0) == 0 and r.value == 0)
r = res(); check("bsum (None, 1) refused", om.omega2_bsum(ctypes.byref(r), None, 1) == 32 and r.value == R0)
raw = (ctypes.c_uint8 * 16)()
mis = ctypes.cast(ctypes.addressof(raw) + 1, ctypes.POINTER(ctypes.c_uint32))
r = res(); check("wsum misaligned refused", om.omega2_wsum(ctypes.byref(r), mis, 1) == 32 and r.value == R0)
w4 = (ctypes.c_uint32 * 4)(1, 2, 3, 0xffffffff)
r = res(); check("wsum = 4294967301", om.omega2_wsum(ctypes.byref(r), w4, 4) == 0 and r.value == 4294967301)
r = res(); check("bsum len 2^64-1 refused", om.omega2_bsum(ctypes.byref(r), b"abc", 2**64 - 1) == 32)
try:
    om.omega2_bsum(ctypes.byref(r), b"abc", 2**64)
    check("len 2^64 raises", False)
except ctypes.ArgumentError:
    check("len 2^64 raises ctypes.ArgumentError", True)
h = (ctypes.c_uint16 * 8)(1, 2, 3, 4)
r = res(); check("vcopy edit == view refused", om.omega2_vcopy(ctypes.byref(r), h, 4, h, 4) == 32)
h4 = ctypes.cast(ctypes.addressof(h) + 8, ctypes.POINTER(ctypes.c_uint16))
r = res(); check("vcopy adjacent accepted", om.omega2_vcopy(ctypes.byref(r), h, 4, h4, 4) == 0 and r.value == 4 and h[7] == 4)
r = res(); check("#748 golden: vpart o 2^64-2 k 4 traps 3", om.omega2_vpart(ctypes.byref(r), bytes(16), 16, 2**64 - 2, 4) == 3 and r.value == R0)
s8 = (ctypes.c_uint8 * 8)(1, 2, 3, 4, 5, 6, 7, 8)
r = res(); st = om.omega2_swap8(ctypes.byref(r), ctypes.cast(s8, ctypes.c_char_p), 8, s8)
check("swap8 out == view reversed", st == 0 and list(s8) == [8, 7, 6, 5, 4, 3, 2, 1])
ho = (ctypes.c_uint64 * 2)(11, 22)
r = res(); check("halt traps 9, out untouched", om.omega2_halt(ctypes.byref(r), ho) == 9 and list(ho) == [11, 22] and r.value == R0)
c = (ctypes.c_uint8 * 24)()
r = res(); check("absorb", om.omega2_absorb(ctypes.byref(r), c, b"abc", 3) == 0 and c[0] == 294 % 256 and c[1] == 1 and c[8] == 3)
o16 = (ctypes.c_uint8 * 16)()
r = res(); check("digest", om.omega2_digest(ctypes.byref(r), bytes(c), o16) == 0 and r.value == 3 and o16[8] == 294 % 256)
f3 = (ctypes.c_uint64 * 3)()
r = res(); check("fillv", om.omega2_fillv(ctypes.byref(r), f3, 3, 9) == 0 and list(f3) == [9, 9, 9])
l3 = (ctypes.c_int64 * 3)(-5, 7, -9)
r = res(); check("lsum = -7 (two's complement bits)", om.omega2_lsum(ctypes.byref(r), l3, 3) == 0 and r.value == 2**64 - 7)
ok = True
for k in range(100):
    r = res(); ok = ok and om.omega_madd(ctypes.byref(r), k, 3, 1) == 0 and r.value == 3 * k + 1
    r = res(); ok = ok and om.omega2_bsum(ctypes.byref(r), b"abc", 3) == 0 and r.value == 294
check("interleaved madd (v1) and bsum (v2)", ok)
print(("PY-V2 FAIL " if fails else "PY-V2 PASS ") + str(fails))
sys.exit(1 if fails else 0)
