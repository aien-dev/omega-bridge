#!/usr/bin/env python3
"""Finite frame/output pools: compiler-built positive and hostile boundary controls."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
OMC = os.environ["OMEGA_NATIVE_OMC"]
PIN = "734f0a39319fbfa930bcc62cb30dbf06d47d78e126372b74f5baf478e6126b61"


def checked(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, **kwargs)


def build(source, out):
    out.write_bytes(checked([OMC], input=source).stdout)
    out.chmod(0o755)
    return str(out)


def refused(generator, frame):
    result = subprocess.run([generator, "c"], input=frame, capture_output=True)
    assert result.returncode == 106 and result.stdout == b"", (result.returncode, result.stderr)


def main():
    assert hashlib.sha256(Path(OMC).read_bytes()).hexdigest() == PIN, "compiler pin mismatch"
    source = (ROOT / "src/native.om").read_bytes()
    with tempfile.TemporaryDirectory(prefix="omega-capacity-") as tmp:
        tmp = Path(tmp)
        generator = build(source, tmp / "native")
        # Every positive image is independently compiled from its matching source.
        # The straight-line body gives substantial real compiler output, not padded code.
        frames = []
        for i in range(64):
            unit = f"fn cap{i:02d} a ulong to ulong\n".encode() + b"a = xor a 1\n" * 8192 + b"ret ulong 7\nend\n"
            code = checked([OMC], input=unit).stdout
            frames.append(unit + b"\0" + f"{len(code):08d}".encode() + code)
        frame = b"".join(frames)
        assert 4194304 < len(frame) < 16777216
        result = checked([generator, "c"], input=frame)
        assert 16777216 < len(result.stdout) < 33554432
        cfile = tmp / "capacity.c"
        cfile.write_bytes(result.stdout)
        caller = tmp / "caller.c"
        # cap63's code is emitted past the first 16777216-byte output pool, i.e. from `outc`;
        # calling it executes bytes stored in the second pool.
        assert result.stdout.find(b"ombr_code_cap63:") >= 16777216, "cap63 not in second output pool"
        caller.write_text("#include <stdint.h>\nuint32_t omega_cap00(uint64_t *, uint64_t);\nuint32_t omega_cap15(uint64_t *, uint64_t);\nuint32_t omega_cap63(uint64_t *, uint64_t);\nint main(void) { uint64_t r=0; if(omega_cap00(&r,0)!=0 || r!=7) return 1; r=0; if(omega_cap15(&r,0)!=0 || r!=7) return 1; r=0; return omega_cap63(&r,0)!=0 || r!=7; }\n")
        checked([os.environ.get("CC", "cc"), "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror", "-pthread", str(cfile), str(caller), "-o", str(tmp / "caller")])
        checked([str(tmp / "caller")])
        for pool, old in ((b"inb uchar 16777216", b"inb uchar 4194304"),
                          (b"outc uchar 16777216", b"outc uchar 1")):
            mutant = source.replace(b"global " + pool, b"global " + old)
            assert mutant != source
            refused(build(mutant, tmp / ("old-" + pool.split()[0].decode())), frame)
        # Hostile protocol inputs exercise each real upper boundary separately.
        refused(generator, b"\0" * 16777216)
        print("CAPACITY PASS: current input pool exhaustion exits 106 with no output")
        # The output probe deliberately has unmatched source/code custody: it is
        # never executed and is solely an emitter-resource refusal control.
        oversized = []
        for i in range(8):
            unit = f"fn flood{i} to ulong\nret ulong 7\nend\n".encode()
            code = checked([OMC], input=unit).stdout
            oversized_code = code + b"\xff" * (875000 - len(code))
            oversized.append(unit + b"\0" + f"{len(oversized_code):08d}".encode() + oversized_code)
        oversized_frame = b"".join(oversized)
        assert len(oversized_frame) < 16777216
        refused(generator, oversized_frame)
        print("CAPACITY PASS: current output pool exhaustion exits 106 with no output")
        print(f"CAPACITY PASS: compiler-built frame {len(frame)} bytes, C {len(result.stdout)} bytes, both endpoint calls")
        print("CAPACITY PASS: old input/output bound mutants and new input/output overflow controls refuse with no output")


if __name__ == "__main__":
    main()
