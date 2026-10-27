# Caller for the Python module native.om generates in py mode (standard library only).
# argv: the generated module, the library built from the C file the same units generate.
# Every expected value is computed here in Python, independently of the Omega code.
import array, ctypes, importlib.util, struct, sys
spec = importlib.util.spec_from_file_location("omega_native_py", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
lib = ctypes.CDLL(sys.argv[2])
fails = 0
def check(name, ok):
    global fails
    print(("PASS " if ok else "FAIL ") + name)
    fails += not ok
def raises(exc, f, *a):
    try:
        f(*a)
    except exc as e:
        return e
    return None
def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]
def f32bits(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]
def f16bits(x):
    return struct.unpack("<H", struct.pack("<e", x))[0]
check("madd 3*5+7 = 22", m.omega_madd(lib, 3, 5, 7) == 22)
check("madd wraps mod 2^64", m.omega_madd(lib, 2**64 - 1, 2, 5) == 3)
check("smadd long result is signed: -3*5+2 = -13", m.omega_smadd(lib, -3, 5, 2) == -13)
e = raises(m.OmegaError, m.omega_smadd, lib, 2**62, 4, 0)
check("smadd overflow raises OmegaError status 1", e is not None and e.status == 1 and e.unit == "smadd")
buf = array.array("Q", [0] * 4)
e = raises(m.OmegaError, m.omega_fill, lib, buf, 1)
check("fill k=1 raises status 3; writes before the trap stay", e is not None and e.status == 3 and list(buf) == [11, 22, 0, 0])
check("fill k=0 = 3, edit array written in place", m.omega_fill(lib, buf, 0) == 3 and list(buf) == [11, 22, 33, 0])
check("spin 1000 = 499500", m.omega_spin(lib, 1000) == 499500)
check("big 7 = 15", m.omega_big(lib, 7) == 15)
d = bytearray(2)
check("mix void result is None", m.omega_mix(lib, 5, 1, b"\x07\x08\x09", d, array.array("Q", [0, 100]), 3) is None)
check("mix wrote d = [9, 108]", list(d) == [9, 108])
check("hsum 1+4+9+16+10 = 40 (private helpers)", m.omega_hsum(lib, bytes([1, 2, 3, 4]), 10) == 40)
a = array.array("f", [1.5, 2.25, -3.0, 0.125])
hv = [1.0, 0.5, 2.0, -0.25]
h = array.array("H", [f16bits(x) for x in hv])
o = array.array("f", [0.0] * 4)
want = [f32(x + y) for x, y in zip(a, hv)]
r = m.omega_fsum(lib, a, h, o)
check("fsum f32 lanes == Python", list(o) == want)
check("fsum result bits == Python", r == f32bits(f32(want[0] + want[3])))
g = array.array("H", [f16bits(x) for x in (3.0, -0.75, 1024.0)])
m.omega_halve(lib, g)
check("halve ushort edit == Python", list(g) == [f16bits(x) for x in (1.5, -0.375, 512.0)])
# Refusals before the call: kind, length, writability and scalar range.
check("wrong length refused (ValueError)", raises(ValueError, m.omega_fsum, lib, array.array("f", [0.0] * 3), h, o) is not None)
check("f64 buffer for an f32 view refused", raises(TypeError, m.omega_fsum, lib, array.array("d", [0.0] * 4), h, o) is not None)
check("int32 buffer for an f32 view refused", raises(TypeError, m.omega_fsum, lib, array.array("i", [0] * 4), h, o) is not None)
check("read-only buffer for an edit array refused", raises(TypeError, m.omega_halve, lib, bytes(6)) is not None)
check("view array takes a read-only buffer", m.omega_hsum(lib, b"\x00\x00\x00\x02", 0) == 4)
check("negative ulong refused", raises(TypeError, m.omega_madd, lib, -1, 0, 0) is not None)
check("2^64 ulong refused", raises(TypeError, m.omega_madd, lib, 2**64, 0, 0) is not None)
check("bool for ulong refused", raises(TypeError, m.omega_madd, lib, True, 0, 0) is not None)
check("2^63 long refused", raises(TypeError, m.omega_smadd, lib, 2**63, 0, 0) is not None)
check("float for ulong refused", raises(TypeError, m.omega_madd, lib, 1.0, 0, 0) is not None)
print(("FAIL " if fails else "PASS ") + "%d failure(s)" % fails)
sys.exit(fails != 0)
