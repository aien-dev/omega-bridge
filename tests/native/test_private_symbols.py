#!/usr/bin/env python3
"""Host-only linkage regression; no device or application is opened."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
OMC = os.environ["OMEGA_NATIVE_OMC"]
CC = os.environ.get("CC", "cc")
PIN = "734f0a39319fbfa930bcc62cb30dbf06d47d78e126372b74f5baf478e6126b61"


def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, **kwargs)


def build(generator, out):
    out.mkdir()
    objects = []
    for name in ("madd", "smadd"):
        source = (ROOT / "tests/native" / (name + ".om")).read_bytes()
        code = run([OMC], input=source).stdout
        frame = source + b"\0" + f"{len(code):08d}".encode() + code
        cfile = out / (name + ".c")
        cfile.write_bytes(run([str(generator), "c"], input=frame).stdout)
        obj = out / (name + ".o")
        run([CC, "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror", "-c", str(cfile), "-o", str(obj)])
        objects.append(obj)
    result = subprocess.run([CC, "-pthread", str(ROOT / "tests/native/private_symbols.c"),
                             *map(str, objects), "-o", str(out / "caller")], capture_output=True)
    (out / "link.log").write_bytes(result.stdout + result.stderr)
    return result, objects


def generator(source, out):
    out.write_bytes(run([OMC], input=source).stdout)
    out.chmod(0o755)
    return out


def main():
    import hashlib
    assert hashlib.sha256(Path(OMC).read_bytes()).hexdigest() == PIN, "compiler pin mismatch"
    # Optional source override also permits replaying the pre-fix generator.
    source = Path(os.environ.get("OMEGA_NATIVE_SOURCE", ROOT / "src/native.om")).read_bytes()
    with tempfile.TemporaryDirectory(prefix="omega-private-symbols-") as tmp:
        tmp = Path(tmp)
        gen = generator(source, tmp / "native")
        linked, objects = build(gen, tmp / "normal")
        if linked.returncode:
            print(linked.stderr.decode(), end="")
            raise AssertionError("separately generated bindings must link")
        for name, obj in zip(("madd", "smadd"), objects):
            symbols = run(["nm", "--defined-only", str(obj)], text=True).stdout.splitlines()
            public = {line.split()[-1] for line in symbols if line.split()[-2].isupper()}
            assert public == {"omega_" + name}, (obj, public)
            private = {line.split()[-1]: line.split()[-2] for line in symbols
                       if line.split()[-1].startswith("ombr_")}
            for helper in ("ombr_enter", "ombr_trap", "ombr_no_entry", "ombr_code_" + name,
                           "ombr_entry_" + name, "ombr_active", "ombr_stk", "ombr_rt_table"):
                assert helper in private and private[helper].islower(), (helper, private)
        print(run([str(tmp / "normal/caller")], text=True).stdout, end="")
        # Restore just the original defect, not arbitrary code or public wrappers.
        mutant = source.replace(b".local ombr_enter", b".globl ombr_enter")
        assert mutant != source, "missing local helper directive"
        linked, _ = build(generator(mutant, tmp / "mutant"), tmp / "global")
        assert linked.returncode != 0 and b"multiple definition" in linked.stderr and b"ombr_enter" in linked.stderr, linked.stderr
        print("PRIVATE-SYMBOLS PASS: nm public ABI unchanged, private locals; .globl mutant rejected")


if __name__ == "__main__":
    main()
