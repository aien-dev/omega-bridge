"""Additive e5b32567 frontend: native/C/Python differential and pin mutants.
Run after the baseline tools/test.sh; this does not replace baseline coverage.
No GPU, CUDA runtime, driver or hardware access.
"""
import os
import pathlib
import shutil
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parents[1]
os.chdir(root)
b = root / "build/seeded"
b.mkdir(parents=True, exist_ok=True)
seed = os.environ.get("OMEGA_SEEDED_OMC")
if not seed:
    sys.exit("NOT_RUN: set OMEGA_SEEDED_OMC to the pinned e5b32567 compiler")

def run(args, data=None, env=None):
    return subprocess.run([str(a) for a in args], input=data, capture_output=True,
                          timeout=60, env=env)

def checked(args, data=None):
    p = run(args, data)
    assert p.returncode == 0, (args, p.returncode, p.stderr.decode())
    return p.stdout

def result(p):
    return p.returncode, p.stdout, p.stderr

source = "const N ulong 16777216\n"
source += "fn sum6 a ulong b ulong c ulong d ulong e ulong f ulong to ulong\nret add add add a b add c d add e f\nend\n"
source += "fn big a view uchar N to ulong\nret len a\nend\n"
for i in range(40):
    body = "add x 1" if i == 0 else f"chain{i-1} add x 1"
    source += f"fn chain{i} x ulong to ulong\nret {body}\nend\n"
source += """fn first a view ulong 4 to ulong
ret get a 0
end
fn main to int
n = sum6 1 2 3 4 5 6
for i ulong 64
if gt i 7
break
end
n = add n i
end
a = new ulong 4 0
put a 0 chain39 n
ret int first view a
end
"""
fixture = b / "expanded.om"
fixture.write_text(source)
# A wrong compiler refuses before semantic checking or producing target output.
wrong = dict(os.environ, OMEGA_SEEDED_OMC=os.environ.get("OMEGA_SEED", "build/bootstrap/omc"))
p = run(["sh", "tools/bridge-seeded", "c", fixture], env=wrong)
assert p.returncode == 65 and not p.stdout and b"fingerprint mismatch" in p.stderr
# Baseline mode remains unable to adopt new capabilities implicitly.
p = run(["sh", "tools/bridge", "c", fixture])
assert p.returncode != 0 and not p.stdout
native = b / "native"
native.write_bytes(checked([seed], source.encode()))
native.chmod(0o755)
expected = result(run([native]))
assert expected[0] not in range(101, 115), expected
outputs = {}
for target, ext in [("c", "c"), ("python", "py")]:
    text = checked(["sh", "tools/bridge-seeded", target, fixture])
    path = b / ("expanded." + ext)
    path.write_bytes(text)
    if target == "c":
        exe = b / "portable"
        checked(["gcc", "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror", path, "-o", exe])
        got = run([exe])
    else:
        got = run([sys.executable, path])
    assert result(got) == expected, (target, expected, result(got))
    outputs[target] = text
# Control: the same differential rejects an actual arithmetic emission defect.
assert b"(a+b)&mask" in outputs["c"]
mutant = b / "mutant.c"
mutant.write_bytes(outputs["c"].replace(b"(a+b)&mask", b"(a-b)&mask"))
checked(["gcc", "-std=gnu11", "-O2", mutant, "-o", b / "mutant"])
assert result(run([b / "mutant"])) != expected
# Explicit native x86 instruction-set execution, not AArch64 emulation.
if not shutil.which("x86_64-linux-gnu-gcc") or not shutil.which("qemu-x86_64"):
    sys.exit("NOT_RUN: install x86_64-linux-gnu-gcc and qemu-x86_64 for x86 differential")
checked(["x86_64-linux-gnu-gcc", "-static", "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
         b / "expanded.c", "-o", b / "portable-x86"])
assert result(run(["qemu-x86_64", b / "portable-x86"])) == expected
unit = b / "unit.om"
unit.write_text("""const L ulong 4
fn seedunit a view ulong L o edit ulong L to ulong
put o 0 get a 0
ret get o 0
end
""")
(b / "unit.c").write_bytes(checked(["sh", "tools/bridge-seeded", "c", unit]))
header = checked(["sh", "tools/bridge-seeded", "h", unit])
assert b"omega_seedunit" in header and b"{" not in header
(b / "unit.h").write_bytes(b"#include <stdint.h>\n" + header)
(b / "caller.c").write_text('''#include "unit.h"
int main(void) {
    uint64_t a[4] = {42}, out[4] = {0}, result = 0;
    if (omega_seedunit(0,a,4,out,4) != 32) return 1;
    if (omega_seedunit(&result,a,3,out,4) != 32) return 2;
    if (omega_seedunit(&result,a,4,a,4) != 32) return 3;
    if (omega_seedunit(&result,a,4,out,4) != 0 || result != 42 || out[0] != 42) return 4;
    return 0;
}
''')
checked(["gcc", "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror", b / "caller.c", b / "unit.c", "-o", b / "caller"])
assert result(run([b / "caller"])) == (0, b"", b"")
print("SEEDED CONVERTER differential C/Python/native/x86 and pin/arithmetic/ABI controls PASS; device NOT_RUN")
