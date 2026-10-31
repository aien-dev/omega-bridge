# Python caller for the f32 and ushort array kinds through the binding tools' `python` word generates
# (ctypes, standard library only). argv: the folder holding omega_native.py and libomega_native.so.
# Every expected value is computed here in Python (struct), independently of the Omega code.
import ctypes, struct, sys
sys.path.insert(0, sys.argv[1])
import omega_native as om
fails = 0
def check(name, ok):
    global fails
    print(("PASS " if ok else "FAIL ") + name)
    fails += not ok
def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]
def f32bits(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]
def f16bits(x):
    return struct.unpack("<H", struct.pack("<e", x))[0]
def refused(f):
    try:
        f()
    except ctypes.ArgumentError:
        return True
    return False
F, H, SENT = ctypes.c_float, ctypes.c_uint16, 6148914691236517205
av = [1.5, 2.25, -3.0, 0.125]; hv = [1.0, 0.5, 2.0, -0.25]
a = (F * 4)(*av); h = (H * 4)(*[f16bits(x) for x in hv]); o = (F * 4)()
want = [f32(x + y) for x, y in zip(av, hv)]
r = ctypes.c_uint64(SENT)
check("fsum f32 view + ushort view -> f32 edit == Python",
      om.omega_fsum(ctypes.byref(r), a, 4, h, 4, o, 4) == 0 and list(o) == want)
check("fsum result bits == Python", r.value == f32bits(f32(want[0] + want[3])))
g = (H * 3)(*[f16bits(x) for x in (3.0, -0.75, 1024.0)])
check("halve ushort edit written in place == Python",
      om.omega_halve(ctypes.byref(r), g, 3) == 0 and list(g) == [f16bits(x) for x in (1.5, -0.375, 512.0)])
# Negative controls: what the ABI cannot carry is refused before the Omega code runs.
r = ctypes.c_uint64(SENT); o2 = (F * 4)()
check("fsum wrong length 3 refused (status 32), output and result untouched",
      om.omega_fsum(ctypes.byref(r), a, 3, h, 4, o2, 4) == 32 and list(o2) == [0.0] * 4 and r.value == SENT)
check("halve wrong length 4 refused (status 32), array untouched",
      om.omega_halve(ctypes.byref(r), g, 4) == 32 and list(g) == [f16bits(x) for x in (1.5, -0.375, 512.0)])
check("f64 array for an f32 view refused", refused(lambda: om.omega_fsum(ctypes.byref(r), (ctypes.c_double * 4)(), 4, h, 4, o, 4)))
check("int32 array for an f32 view refused", refused(lambda: om.omega_fsum(ctypes.byref(r), (ctypes.c_int32 * 4)(), 4, h, 4, o, 4)))
check("bytes for an edit ushort array refused", refused(lambda: om.omega_halve(ctypes.byref(r), bytes(6), 3)))
check("length 2**64 refused", refused(lambda: om.omega_halve(ctypes.byref(r), g, 2**64)))
print(("FAIL " if fails else "PASS ") + "%d failure(s)" % fails)
sys.exit(fails != 0)
