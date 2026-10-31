#!/usr/bin/env python3
"""ABI v2 cross-qualification, reusing tests/native/v2's unmodified oracles.

Required: OMEGA_NATIVE_OMC (baseline generator compiler), OMEGA_NATIVE_X86_OMC
(pinned x86 compiler), CC=x86_64-linux-gnu-gcc, CXX=x86_64-linux-gnu-g++,
rustc with x86_64-unknown-linux-gnu std, Zig 0.13, Go with cgo, qemu-x86_64,
and OMEGA_NATIVE_X86_PYTHON (an x86 Linux interpreter, NOT host python).
OMEGA_NATIVE_X86_SYSROOT defaults to /usr/x86_64-linux-gnu; an extracted Python
runtime may supply OMEGA_NATIVE_X86_LIBPATH. Missing tools refuse aggregate PASS.
No CPU timing or native hardware qualification is inferred from emulation.
"""
import hashlib
import os
from pathlib import Path
import re
import shlex
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
T = ROOT / "tests/native/v2"
N = ROOT / "tests/native"
OUTPUTS = {"c": "c", "h": "h", "python": "py", "rust": "rs", "zig": "zig", "go": "go",
           "api": "api.h", "apih": "api_decl.h", "apic": "api_defs.c"}
REQUIRED = {"c", "cpp", "python", "rust", "zig", "go"}
# The AArch64 parity baseline is the generator of the last intentional AArch64 output change:
# f637021 (#26, f32 and ushort array kinds). Moving it requires a reviewed AArch64 output change.
BASELINE = "f637021"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def command(key, default):
    return shlex.split(os.environ.get(key, default))


class Suite:
    def __init__(self, out):
        self.out = out.resolve()
        self.out.mkdir(parents=True, exist_ok=True)
        self.cc = command("CC", "x86_64-linux-gnu-gcc")
        self.cxx = command("CXX", "x86_64-linux-gnu-g++")
        self.zig = command("ZIG", "zig")
        self.go = command("GO", "go")
        self.rust = command("RUSTC", "rustc")
        self.qemu = command("QEMU_X86_64", "qemu-x86_64")
        self.sysroot = os.environ.get("OMEGA_NATIVE_X86_SYSROOT", "/usr/x86_64-linux-gnu")
        self.python = os.environ.get("OMEGA_NATIVE_X86_PYTHON", "")
        self.nm = command("NM", "x86_64-linux-gnu-nm")
        self.objdump = command("OBJDUMP", "x86_64-linux-gnu-objdump")
        self.env = dict(os.environ, CC=shlex.join(self.cc), CGO_ENABLED="1", GOOS="linux", GOARCH="amd64")
        self.failed = []
        self.missing = []
        self.ran = set()
        self.omc = os.environ.get("OMEGA_NATIVE_OMC", "")
        self.xomc = os.environ.get("OMEGA_NATIVE_X86_OMC", "")
        self.lib = self.out / "library"
        self.gen = self.lib / "work/native-gen"
        self.counter = 0

    def check(self, name, ok):
        print(("PASS " if ok else "FAIL ") + name, flush=True)
        if not ok:
            self.failed.append(name)
        return ok

    def call(self, args, *, data=None, cwd=None, env=None):
        args = list(map(str, args))
        self.counter += 1
        result = subprocess.run(args, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                cwd=cwd, env=self.env if env is None else env)
        log = self.out / f"{self.counter:04d}.log"
        log.write_bytes(("$ " + shlex.join(args) + "\n").encode() + result.stdout + result.stderr
                        + f"\nexit={result.returncode}\n".encode())
        if result.returncode:
            print(f"INFO exit={result.returncode} log={log}", flush=True)
        return result

    def must(self, args, **kwargs):
        result = self.call(args, **kwargs)
        if result.returncode:
            raise RuntimeError(f"command failed: {shlex.join(list(map(str, args)))}")
        return result.stdout

    def guest(self, exe, *args):
        # Every target execution goes through QEMU, even on a native x86 host.
        cmd = self.qemu + ["-L", self.sysroot]
        if os.environ.get("OMEGA_NATIVE_X86_LIBPATH"):
            cmd += ["-E", "LD_LIBRARY_PATH=" + os.environ["OMEGA_NATIVE_X86_LIBPATH"]]
        return cmd + [str(exe), *map(str, args)]

    def preflight(self):
        tools = {"c": self.cc, "cpp": self.cxx, "rust": self.rust, "zig": self.zig, "go": self.go,
                 "qemu": self.qemu, "nm": self.nm, "objdump": self.objdump}
        for language, cmd in tools.items():
            if not cmd or not shutil.which(cmd[0]):
                self.missing.append(language)
                print(f"NOT_RUN {language} caller/tool: {shlex.join(cmd)} unavailable", flush=True)
        if not self.python or not Path(self.python).is_file():
            self.missing.append("python")
            print("NOT_RUN python caller: set OMEGA_NATIVE_X86_PYTHON to an x86 interpreter", flush=True)
        else:
            elf = Path(self.python).resolve().read_bytes()[:20]
            self.check("Python is ELF64 x86-64, not the host interpreter",
                       elf[:6] == b"\x7fELF\x02\x01" and elf[18:20] == b"\x3e\x00")
        for name, path, key in (("generator", self.omc, "PIN"), ("x86", self.xomc, "X86_PIN")):
            match = re.search(r"^" + key + r"=([0-9a-f]{64})$", (ROOT / "tools/native").read_text(), re.M)
            self.check(name + " compiler pin", bool(match and path and Path(path).is_file()
                       and digest(Path(path).read_bytes()) == match.group(1)))
        if self.missing or self.failed:
            return False
        rustlib = self.must(self.rust + ["--print", "target-libdir", "--target", "x86_64-unknown-linux-gnu"]).decode().strip()
        if not list(Path(rustlib).glob("libstd-*.rlib")):
            self.missing.append("rust-std-x86_64")
            print("NOT_RUN rust caller: x86_64-unknown-linux-gnu standard library absent", flush=True)
        print("INFO x86 compiler sha256=" + digest(Path(self.xomc).read_bytes()), flush=True)
        print("INFO generator compiler sha256=" + digest(Path(self.omc).read_bytes()), flush=True)
        # Prove the extracted runtime can load ctypes before importing generated bindings.
        p = self.call(self.guest(self.python, "-I", "-c", "import ctypes, platform; assert platform.machine() == 'x86_64'; print('X86-PYTHON READY')"))
        self.check("x86 Python interpreter and ctypes runtime", p.returncode == 0 and b"X86-PYTHON READY" in p.stdout)
        return not self.failed and not self.missing

    def generate(self, word, frame, gen=None, target=True):
        return self.call([gen or self.gen, word] + (["x86linux"] if target else []), data=frame)

    def frame(self, source, code, name=None):
        result = source + b"\0" + f"{len(code):08d}".encode() + code
        if name is not None:
            result += f"omega-unit {name} {digest(Path(self.xomc).read_bytes())}\n".encode()
        return result

    def compile_unit(self, source):
        return self.must([self.xomc], data=b"target x86linux\n" + source)

    def build_c(self, folder, source=None, output="caller_c", shared=False, extra=()):
        source = source or T / "caller.c"
        flags = ["-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror"]
        if shared:
            flags += ["-fPIC", "-shared", "-Wl,-soname,libomega_native.so", "-include", str(folder / "omega_native.h")]
        else:
            flags += ["-pthread", "-I", str(folder)]
        cmd = self.cc + flags + [str(source)]
        if not shared:
            cmd += ["-L" + str(folder), "-lomega_native", "-Wl,-rpath," + str(folder), "-ldl"]
        return self.call(cmd + list(extra) + ["-o", str(folder / output)])

    def initial_library(self):
        units = [N / "madd.om"] + [T / (name + ".om") for name in ("vec", "lay", "one")]
        self.must([ROOT / "tools/native", "--target", "x86linux", self.lib, *units])
        self.frame_set = (self.lib / "work/units.in").read_bytes()
        for caller in T.glob("caller.*"):
            shutil.copy2(caller, self.lib / caller.name)
        self.check("tools/native built mixed OM-1/OM-2 x86 library and all bindings", True)

    def identity_and_code(self):
        ctext = (self.lib / "omega_native.c").read_text()
        self.check("x86 floor uses actual usable stack base, independent of out carve",
                   "mov %r9,%r15" in ctext and
                   bool(re.search(r"ombr_xenter.*ombr_stk\s*-\s*OMBR_STACK", ctext)))
        htext = (self.lib / "omega_native.h").read_text()
        identities = (self.lib / "work/ident.txt").read_text()
        elf = (self.lib / "libomega_native.so").read_bytes()
        self.check("library ELF machine is x86-64", elf[:6] == b"\x7fELF\x02\x01" and elf[18:20] == b"\x3e\x00")
        for name in ("madd", "vec", "lay", "one"):
            path = (N if name == "madd" else T) / (name + ".om")
            source = path.read_bytes()
            abi = 1 if name == "madd" else 2
            identity = f"omega-ident 1 unit={name} abi={abi} profile=OM-{abi} src={digest(source)} omc={digest(Path(self.xomc).read_bytes())}"
            self.check("original source/compiler identity " + name, identity + " path=" + str(path) in identities
                       and (abi == 1 or ('"' + identity + '"' in ctext and '"' + identity + '"' in htext)))
            self.check("source snapshot excludes target directive " + name,
                       (self.lib / f"work/{name}.om").read_bytes() == source)
            code = (self.lib / f"work/{name}.bin").read_bytes()
            self.check("compiler bytes reproduce " + name, code == self.compile_unit(source))
            entries = len(re.findall(rb"^export fn ", source, re.M))
            if entries:
                valid = len(code) >= entries * 6
                for index in range(entries):
                    start = index * 6
                    slot = code[start:start + 6]
                    valid = valid and len(slot) == 6 and slot[0] == 0xe9 and slot[5] == 0x90
                    if len(slot) == 6:
                        destination = start + 5 + struct.unpack("<i", slot[1:5])[0]
                        valid = valid and entries * 6 <= destination < len(code)
                self.check("six-byte JMP/NOP entry slots " + name, valid)
                listing = self.must(self.objdump + ["-D", "-b", "binary", "-m", "i386:x86-64",
                                                   str(self.lib / f"work/{name}.bin")])
                self.check("independent x86 instruction oracle " + name,
                           len(re.findall(rb"\bjmp\b", listing)) >= entries and b"(bad)" not in listing)
            symbol = ("ombr_code_" if abi == 1 else "ombr2_code_") + name
            symbols = self.must(self.objdump + ["-t", str(self.lib / "libomega_native.so")]).decode()
            address = next(int(line.split()[0], 16) for line in symbols.splitlines() if line.split() and line.split()[-1] == symbol)
            sections = self.must(self.objdump + ["-h", str(self.lib / "libomega_native.so")]).decode()
            offsets = [line.split() for line in sections.splitlines() if re.match(r"\s*\d+\s+\.", line)]
            offset = next(address - int(s[3], 16) + int(s[5], 16) for s in offsets
                          if int(s[3], 16) <= address < int(s[3], 16) + int(s[2], 16))
            self.check("embedded bytes unchanged " + name, elf[offset:offset + len(code)] == code)
        exports = set(line.split()[-1] for line in self.must(self.nm + ["-D", "--defined-only", str(self.lib / "libomega_native.so")]).decode().splitlines())
        expected = {"omega2_" + name for name in "absorb bsum digest fillv halt ident_lay ident_one ident_vec lsum swap8 two vcopy vlen vpart wsum".split()} | {"omega_madd"}
        self.check("exact public ABI symbol set", exports == expected)
        private = [line.split() for line in self.must(self.nm + ["--defined-only", str(self.lib / "libomega_native.so")]).decode().splitlines()
                   if line.split()[-1].startswith("ombr")]
        self.check("all runtime/code/entry symbols private", bool(private) and all(s[-2].islower() for s in private))
        self.check("no caller hand-declares Omega ABI", not any(re.search(r'uint32_t omega|fn omega|argtypes|CDLL|import "C"', p.read_text()) for p in T.glob("caller.*")))
        # Declarations do not depend on instruction bytes. Pad only the payload
        # to satisfy the default generator's four-byte AArch64 word boundary.
        declaration_frame = b""
        for name in ("madd", "vec", "lay", "one"):
            source = (self.lib / f"work/{name}.om").read_bytes()
            code = (self.lib / f"work/{name}.bin").read_bytes()
            code += b"\x90" * (-len(code) % 4)
            declaration_frame += self.frame(source, code, None if name == "madd" else name)
        for word in ("h", "python", "rust", "zig", "go", "api", "apih", "apic"):
            a = self.generate(word, declaration_frame)
            b = self.generate(word, declaration_frame, target=False)
            self.check("target-independent declarations " + word, a.returncode == b.returncode == 0 and a.stdout == b.stdout)

    def build_language(self, language, folder, stem="caller", edition="2021"):
        source = folder / stem
        if language == "c":
            return self.build_c(folder, source.with_suffix(".c"), stem + "_c")
        if language == "cpp":
            return self.call(self.cxx + ["-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(folder), str(source.with_suffix(".cpp")), "-L" + str(folder), "-lomega_native", "-Wl,-rpath," + str(folder), "-o", str(folder / (stem + "_cpp"))])
        if language == "rust":
            return self.call(self.rust + ["--target", "x86_64-unknown-linux-gnu", "-C", "linker=" + self.cc[0], "-O", "--edition", edition, "-D", "warnings", str(source.with_suffix(".rs")), "-L", str(folder), "-C", "link-arg=-Wl,-rpath," + str(folder), "-o", str(folder / (stem + "_rust"))])
        if language == "zig":
            return self.call(self.zig + ["build-exe", str(source.with_suffix(".zig")), "-target", "x86_64-linux-gnu", "-L" + str(folder), "-lomega_native", "-lc", "-rpath", str(folder), "-femit-bin=" + str(folder / (stem + "_zig"))], cwd=folder)
        if language == "go":
            pkg = folder / (stem + "-go")
            (pkg / "omeganative").mkdir(parents=True)
            for name in ("omega_native.go", "omega_native.h", "libomega_native.so"):
                shutil.copy2(folder / name, pkg / "omeganative" / name)
            shutil.copy2(source.with_suffix(".go"), pkg / "main.go")
            (pkg / "go.mod").write_text("module omegacaller\n\ngo 1.20\n")
            env = dict(self.env, CGO_LDFLAGS="-Wl,-rpath," + str(pkg / "omeganative"))
            return self.call(self.go + ["build", "-o", str(folder / (stem + "_go")), "."], cwd=pkg, env=env)
        raise ValueError(language)

    def callers(self):
        for language in sorted(REQUIRED):
            if language == "python":
                result = self.call(self.guest(self.python, "-I", self.lib / "caller.py", self.lib))
            else:
                build = self.build_language(language, self.lib)
                if not self.check(language + " caller built", build.returncode == 0):
                    continue
                result = self.call(self.guest(self.lib / ("caller_" + language)))
            transcript = result.stdout + result.stderr
            if self.check(language + " caller EMULATED", result.returncode == 0 and b"PASS" in transcript and b"FAIL" not in transcript):
                self.ran.add(language)
            if language == "rust":
                build = self.build_language(language, self.lib, edition="2024")
                self.check("rust-2024 caller EMULATED", build.returncode == 0 and self.call(self.guest(self.lib / "caller_rust")).returncode == 0)
        built = self.build_c(self.lib, Path(__file__).with_name("sysv.c"), "sysv",
                             extra=[str(Path(__file__).with_name("sysv.S"))])
        self.check("SysV AMD64 saved-register oracle EMULATED",
                   built.returncode == 0 and self.call(self.guest(self.lib / "sysv")).returncode == 0)

    def stale_and_v1(self):
        stale = self.out / "stale"
        stale.mkdir()
        shutil.copy2(self.lib / "libomega_native.so", stale)
        original = (T / "vec.om").read_bytes()
        changed = original.replace(b"an OM-2 unit", b"An OM-2 unit", 1)
        self.check("stale source mutation changes bytes", changed != original)
        frame = self.frame(changed, (self.lib / "work/vec.bin").read_bytes(), "vec")
        for word, ext in (("h", "h"), ("python", "py")):
            result = self.generate(word, frame)
            self.check("stale " + word + " generated", result.returncode == 0)
            (stale / ("omega_native." + ext)).write_bytes(result.stdout)
        self.must(self.cc + ["-std=gnu11", "-I", str(stale), str(T / "stale.c"), "-L" + str(stale), "-lomega_native", "-Wl,-rpath," + str(stale), "-o", str(stale / "stale_c")])
        result = self.call(self.guest(stale / "stale_c"))
        self.check("stale C identity refused", result.returncode == 3 and ("src=" + digest(changed)).encode() in result.stdout)
        self.must(self.cc + ["-std=gnu11", "-I", str(self.lib), str(T / "stale.c"), "-L" + str(self.lib), "-lomega_native", "-Wl,-rpath," + str(self.lib), "-o", str(stale / "fresh_c")])
        self.check("fresh C identity control", self.call(self.guest(stale / "fresh_c")).returncode == 0)
        result = self.call(self.guest(self.python, "-I", "-c", f"import sys; sys.path.insert(0, {str(stale)!r}); import omega_native"))
        self.check("stale Python import refused for identity", result.returncode != 0 and b"ImportError: libomega_native.so is not the library" in result.stderr)
        old = self.out / "v1use"
        old.mkdir()
        shutil.copy2(self.lib / "libomega_native.so", old)
        source = (T / "v1use/bsum.om").read_bytes()
        frame = self.frame(source, self.compile_unit(source))
        for word in ("h", "python", "rust", "zig", "go"):
            result = self.generate(word, frame)
            self.check("v1 refusal binding generated " + word, result.returncode == 0)
            (old / ("omega_native." + OUTPUTS[word])).write_bytes(result.stdout)
        for source in (T / "v1use").glob("use.*"):
            shutil.copy2(source, old / source.name)
        for language in sorted(REQUIRED):
            result = self.call(self.guest(self.python, "-I", old / "use.py", old)) if language == "python" else self.build_language(language, old, "use")
            self.check(language + " refuses old v1 symbol", result.returncode != 0 and b"omega_bsum" in result.stdout + result.stderr
                       and bool(re.search(rb"undefined reference|undefined symbol", result.stdout + result.stderr)))

    def refusals(self):
        code = (self.lib / "work/vec.bin").read_bytes()
        b = b"om2\nexport fn e1 d view uchar * to ulong\nret 0\nend\n"
        trailer = b"omega-unit u " + b"0" * 64 + b"\n"
        def frame(source=b, binary=code, tail=trailer):
            return source + b"\0" + f"{len(binary):08d}".encode() + binary + tail
        result = self.generate("c", frame())
        self.check("generator accepts refusal control", result.returncode == 0 and b"omega2_e1(uint64_t *result, const uint8_t *o_d, uint64_t o_d_len)" in result.stdout)
        cases = [("missing identity", frame(tail=b"")), ("short digest", frame(tail=b"omega-unit u 0123\n")),
                 ("nonhex digest", frame(tail=b"omega-unit u " + b"0" * 63 + b"G\n")),
                 ("invalid unit name", frame(tail=trailer.replace(b" u ", b" a-b "))),
                 ("repeated unit", frame() + frame(source=b.replace(b"e1", b"e2"))),
                 ("repeated export", frame() + frame(tail=trailer.replace(b" u ", b" v "))),
                 ("diag", frame(source=b.replace(b"om2\n", b"om2 diag\n"))),
                 ("eight slots", frame(source=b"om2\nexport fn e1 a view uchar * b view uchar * c view uchar * d view uchar * to ulong\nret 0\nend\n")),
                 ("unknown layout", frame(source=b"om2\nexport fn e1 c edit nolay to void\nend\n")),
                 ("oversized out", frame(source=b"om2\nexport fn e1 o out ulong 8193 to void\nend\n")),
                 ("uint scalar", frame(source=b"om2\nexport fn e1 x uint to ulong\nret 0\nend\n")),
                 ("uint result", frame(source=b.replace(b"to ulong", b"to uint"))),
                 ("reserved len name", frame(source=b.replace(b"e1 d ", b"e1 d_len "))),
                 ("short six-byte entry table", frame(source=b"om2\nexport fn e1 to void\nend\nexport fn e2 to void\nend\n", binary=b"x" * 11)),
                 ("unknown c-type layout", frame(source=b"note bridge c-type nolay x\nom2\nexport fn e1 to void\nend\n"))]
        for name, data in cases:
            result = self.generate("c", data)
            self.check("generator refuses " + name, result.returncode == 110 and not result.stdout)
        for args in ([], ["java", "x86linux"], ["c", "unknown"], ["c", "x86linux", "extra"]):
            result = self.call([self.gen, *args], data=self.frame_set)
            self.check("generator refuses argument vector " + repr(args), result.returncode == 110 and not result.stdout)
        wrong_pin = dict(self.env, OMEGA_NATIVE_X86_OMC=self.omc)
        absent = self.out / "wrong-compiler-pin"
        result = self.call([ROOT / "tools/native", "--target", "x86linux", absent, N / "madd.om"], env=wrong_pin)
        self.check("mismatched x86 compiler refuses before creating outputs",
                   result.returncode == 1 and not result.stdout and b"x86 omc sha256" in result.stderr
                   and b", pinned " in result.stderr and not absent.exists())
        keep = self.out / "keep"
        self.must([ROOT / "tools/native", "--target", "x86linux", keep, N / "madd.om"])
        before = {str(p.relative_to(keep)): p.read_bytes() for p in keep.rglob("*") if p.is_file()}
        result = self.call([ROOT / "tools/native", "--target", "x86linux", keep, N / "madd.om"], env=wrong_pin)
        after = {str(p.relative_to(keep)): p.read_bytes() for p in keep.rglob("*") if p.is_file()}
        self.check("mismatched x86 compiler preserves previous outputs",
                   result.returncode == 1 and not result.stdout and b"x86 omc sha256" in result.stderr
                   and before == after)
        bad = self.out / "bad.om"
        bad.write_bytes(b"fn m a ulong to uchar\nret uchar a\nend\n")
        result = self.call([ROOT / "tools/native", "--target", "x86linux", keep, N / "madd.om", bad])
        after = {str(p.relative_to(keep)): p.read_bytes() for p in keep.rglob("*") if p.is_file()}
        self.check("tools/native refusal preserves previous outputs and removes scratch", result.returncode == 110 and str(bad).encode() in result.stderr and before == after)

    def mutant_generator(self, name, old, new, count=1):
        folder = self.out / ("mut-" + name)
        folder.mkdir()
        source = (ROOT / "src/native.om").read_bytes()
        assert source.count(old) == count, (name, source.count(old), count)
        changed = source.replace(old, new)
        binary = self.must([self.omc], data=changed)
        gen = folder / "gen"
        gen.write_bytes(binary)
        gen.chmod(0o755)
        return folder, gen

    def runtime_mutants(self):
        for name, old, new, expected in (
            ("wrap", b" || n * es > UINTPTR_MAX - lo)", b")", b"#748 golden: vpart len 2^64-1"),
            ("overlap", b"if ((sp[i].w == 1 || sp[j].w == 1 ||", b"if ((", b"vcopy edit == view"),
            ("outcopy", b"memmove(o[i].dst, buf[i], o[i].n);", b"(void)buf[i];", b"digest: tag")):
            folder, gen = self.mutant_generator(name, old, new)
            for word, ext in (("c", "c"), ("h", "h")):
                result = self.generate(word, self.frame_set, gen)
                self.check(name + " mutant generated " + word, result.returncode == 0)
                (folder / ("omega_native." + ext)).write_bytes(result.stdout)
            self.check(name + " mutant differs", (folder / "omega_native.c").read_bytes() != (self.lib / "omega_native.c").read_bytes())
            shutil.copy2(self.lib / "omega_api.h", folder)
            self.must_build(self.build_c(folder, folder / "omega_native.c", "libomega_native.so", shared=True))
            self.must_build(self.build_c(folder))
            result = self.call(self.guest(folder / "caller_c"))
            self.check(name + " mutant caught by existing boundary oracle", result.returncode != 0 and b"FAIL " + expected in result.stdout)

    @staticmethod
    def must_build(result):
        if result.returncode:
            raise RuntimeError("control could not build; not a mutant detection")

    def private_symbols(self):
        source = (ROOT / "src/native.om").read_bytes()
        for mutated in (False, True):
            folder = self.out / ("private-mutant" if mutated else "private")
            folder.mkdir()
            gen = self.gen
            if mutated:
                changed = source.replace(b".local ombr_enter", b".globl ombr_enter")
                assert changed != source
                gen = folder / "gen"
                gen.write_bytes(self.must([self.omc], data=changed))
                gen.chmod(0o755)
            objects = []
            for name in ("madd", "smadd"):
                text = (N / (name + ".om")).read_bytes()
                result = self.generate("c", self.frame(text, self.compile_unit(text)), gen)
                self.check("private fixture generated " + name, result.returncode == 0)
                cfile = folder / (name + ".c")
                cfile.write_bytes(result.stdout)
                obj = folder / (name + ".o")
                self.must(self.cc + ["-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror", "-c", str(cfile), "-o", str(obj)])
                objects.append(obj)
                if not mutated:
                    symbols = [line.split() for line in self.must(self.nm + ["--defined-only", str(obj)]).decode().splitlines()]
                    public = {line[-1] for line in symbols if line[-2].isupper()}
                    private = {line[-1]: line[-2] for line in symbols if line[-1].startswith("ombr_")}
                    helpers = ("ombr_enter", "ombr_trap", "ombr_no_entry", "ombr_code_" + name, "ombr_entry_" + name,
                               "ombr_active", "ombr_stk", "ombr_rt_table")
                    self.check("separate object private locals " + name, public == {"omega_" + name} and all(h in private and private[h].islower() for h in helpers))
            result = self.call(self.cc + ["-pthread", str(N / "private_symbols.c"), *map(str, objects), "-o", str(folder / "caller")])
            if mutated:
                self.check("global helper mutant rejected at link", result.returncode != 0 and b"multiple definition" in result.stderr and b"ombr_enter" in result.stderr)
            else:
                self.must_build(result)
                self.check("separate bindings and TLS isolation EMULATED", self.call(self.guest(folder / "caller")).returncode == 0)

    def freestanding_api(self):
        folder = self.out / "api"
        folder.mkdir()
        flags = ["-std=gnu11", "-ffreestanding", "-fno-builtin", "-O2", "-Wall", "-Wextra", "-Werror"]
        def imports(obj):
            return {line.split()[-1] for line in self.must(self.nm + ["-u", str(obj)]).decode().splitlines()}
        self.must(self.cc + flags + ["-I", str(self.lib), "-c", str(T / "fsuse.c"), "-o", str(folder / "use.o")])
        self.check("prototype-only API has no libc imports", imports(folder / "use.o") == {"absorb", "bsum", "digest", "swap8"})
        self.must(self.cc + ["-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror", "-Wmissing-prototypes", "-I", str(self.lib), "-c", str(self.lib / "omega_api_defs.c"), "-o", str(folder / "defs.o")])
        symbols = self.must(self.nm + [str(folder / "defs.o")])
        self.check("out-of-line API owns abort and definitions", "abort" in imports(folder / "defs.o") and b" T swap8" in symbols)
        inline = folder / "inline.c"
        inline.write_bytes((T / "fsuse.c").read_bytes().replace(b'"omega_api_decl.h"', b'"omega_api.h"'))
        self.must(self.cc + flags + ["-I", str(self.lib), "-c", str(inline), "-o", str(folder / "inline.o")])
        self.check("inline API import negative control", "abort" in imports(folder / "inline.o"))
        exe = folder / "fsmain"
        self.must(self.cc + ["-std=gnu11", "-O2", "-I", str(self.lib), str(T / "fsmain.c"), str(folder / "use.o"), str(folder / "defs.o"), "-L" + str(self.lib), "-lomega_native", "-Wl,-rpath," + str(self.lib), "-o", str(exe)])
        result = self.call(self.guest(exe))
        self.check("out-of-line API EMULATED", result.returncode == 0 and b"PASS fs_check 0" in result.stdout)
        result = self.call(self.guest(exe, "refuse"))
        self.check("out-of-line API trap aborts", result.returncode in (-6, 134))
        for name, old, new in (("apih", b"if eq get st 5 8\n", b"if eq get st 5 98\n"),
                               ("api", b"if eq get st 5 7\n", b"if eq get st 5 97\n")):
            mutant, gen = self.mutant_generator(name, old, new)
            result = self.generate(name, self.frame_set, gen)
            self.check(name + " API mutant generated", result.returncode == 0)
            if name == "apih":
                shutil.copy2(self.lib / "omega_native.h", mutant)
                (mutant / "omega_api_decl.h").write_bytes(result.stdout)
                # Supply abort's declaration so this control detects the import
                # leak, not an unrelated implicit-declaration compilation error.
                build = self.call(self.cc + flags + ["-include", "stdlib.h", "-I", str(mutant), "-c", str(T / "fsuse.c"), "-o", str(mutant / "use.o")])
                self.check("prototype-only API mutant caught", (build.returncode == 0 and "abort" in imports(mutant / "use.o")))
            else:
                self.check("inline API mutant caught", result.stdout != (self.lib / "omega_api.h").read_bytes() and b"static inline" not in result.stdout)

    def aarch64_parity(self):
        baseline = self.out / "baseline-native-gen"
        source = self.must(["git", "-C", str(ROOT), "show", BASELINE + ":src/native.om"])
        baseline.write_bytes(self.must([self.omc], data=source))
        baseline.chmod(0o755)
        frames = {}
        for path in sorted(N.rglob("*.om")):
            if Path(__file__).parent in path.parents:
                continue
            text = path.read_bytes()
            significant = [line for line in text.splitlines() if not line.startswith(b"note ") and line.strip()]
            om2 = bool(significant and significant[0] == b"om2")
            compiler = self.xomc if om2 else self.omc
            result = self.call([compiler], data=text)
            if result.returncode:
                self.check("AArch64 parity fixture compiles " + str(path.relative_to(N)), False)
                continue
            trailer = ("omega-unit " + path.stem + " " + digest(Path(compiler).read_bytes()) + "\n").encode() if om2 else b""
            frame = text + b"\0" + f"{len(result.stdout):08d}".encode() + result.stdout + trailer
            frames[path] = frame
        sets = {"v1-set": b"".join(frame for path, frame in frames.items() if path.parent == N),
                "v2-set": frames.get(N / "madd.om", b"") + b"".join(frames.get(T / (name + ".om"), b"") for name in ("vec", "lay", "one"))}
        comparisons = [(str(path.relative_to(N)), frame) for path, frame in frames.items()] + list(sets.items())
        for name, frame in comparisons:
            for word in (*OUTPUTS, "freest"):
                old = self.generate(word, frame, baseline, target=False)
                new = self.generate(word, frame, target=False)
                self.check("AArch64 byte parity " + BASELINE + " " + name + " " + word,
                           old.returncode == new.returncode and old.stdout == new.stdout and old.stderr == new.stderr)

    def trap_controls(self):
        here = Path(__file__).parent
        source = (here / "trapcall.om").read_bytes()
        code = self.compile_unit(source)
        follow_source = (here / "follow.om").read_bytes()
        follow_frame = self.frame(follow_source, self.compile_unit(follow_source))
        out_source = (here / "outtrap.om").read_bytes()
        out_frame = self.frame(out_source, self.compile_unit(out_source), "outtrap")
        pattern = b"\xbe\x05\x00\x00\x00\x41\xff\x66\x10"
        self.check("nested explicit trap uses ESI and runtime table slot 2", code.count(pattern) == 1)
        if code.count(pattern) != 1:
            return
        basicwrite = self.call([self.xomc], data=b"target x86linux\nfn hostbad d edit uchar 1 to ulong\nr = write 1 d 0 1\nret ulong r\nend\n")
        self.check("legacy basic write remains permitted in bare code", basicwrite.returncode == 0 and bool(basicwrite.stdout))
        hostword = self.call([self.xomc], data=b"target x86linux\nfn hostbad to long\nr = fclose -1\nret r\nend\n")
        self.check("advanced bare host helper remains compiler refusal 9", hostword.returncode == 9 and b"error 9" in hostword.stderr)
        for name, changed, expected in (
                ("trap", code, 5),
                ("zero-code", code.replace(pattern, b"\xbe\x00\x00\x00\x00\x41\xff\x66\x10"), 34),
                ("wrong-slot", code.replace(pattern, b"\xbe\x05\x00\x00\x00\x41\xff\x66\x00"), 34),
                ("xsave-stack", code, 6)):
            folder = self.out / name
            folder.mkdir()
            frame = self.frame(source, changed) + follow_frame + out_frame
            for word, ext in (("c", "c"), ("h", "h")):
                result = self.generate(word, frame)
                self.check(name + " control generated " + word, result.returncode == 0)
                output = result.stdout
                if name == "xsave-stack" and word == "c":
                    before = b"mov %r9,%r15"
                    self.check("xsave control bounds only owned runtime stack", output.count(before) == 1)
                    output = output.replace(before, b"lea -1024(%r8),%r15")
                (folder / ("omega_native." + ext)).write_bytes(output)
            self.must_build(self.build_c(folder, folder / "omega_native.c", "libomega_native.so", shared=True))
            build = self.build_c(folder, here / "trapcheck.c", "trapcheck",
                                 extra=["-DEXPECT_TRAP=" + str(expected), str(here / "sysv.S")])
            self.must_build(build)
            result = self.call(self.guest(folder / "trapcheck"))
            self.check(name + ": status " + str(expected) + ", sentinel, saved regs and subsequent call EMULATED",
                       result.returncode == 0 and b"PASS trap status" in result.stdout)

    def freestanding_x86(self):
        # tests/native/test_freestanding.py's caller (four threads, nested trap, signed trap)
        # against `tools/native --target x86linux --freestanding`, i.e. the xfasm adapter.
        sys.path.insert(0, str(N))
        import test_freestanding
        good = (ROOT / "src/native.om").read_bytes()
        old, new = b"mov %rax,(%rcx)", b"mov %rbx,(%rcx)"
        xfasm = [line for line in good.split(b"\n") if line.startswith(b"text xfasm ")]
        # The mutant must hit the freestanding adapter's result store exactly once.
        if not self.check("freestanding result-store mutant applies once to xfasm",
                          len(xfasm) == 1 and xfasm[0].count(old) == 1):
            return
        bad = good.replace(xfasm[0], xfasm[0].replace(old, new))
        for name, source in (("freestanding-x86", good), ("freestanding-x86-mutant", bad)):
            tree = self.out / name
            (tree / "tools").mkdir(parents=True)
            (tree / "src").mkdir()
            shutil.copy2(ROOT / "tools/native", tree / "tools/native")
            (tree / "src/native.om").write_bytes(source)
            epoch = tree / "epoch.om"
            epoch.write_text(test_freestanding.EPOCH)
            lib = tree / "lib"
            self.must([tree / "tools/native", "--target", "x86linux", "--freestanding", lib, epoch, N / "smadd.om"])
            obj = lib / "omega_native.o"
            elf = obj.read_bytes()
            imports = {line.split()[-1] for line in self.must(self.nm + ["-u", str(obj)]).decode().splitlines() if line.split()}
            self.check(name + " object is x86-64 with only GPU_FS_LINK imports",
                       elf[:6] == b"\x7fELF\x02\x01" and elf[18:20] == b"\x3e\x00"
                       and not imports - test_freestanding.ALLOWED)
            caller = tree / "caller.c"
            caller.write_text(test_freestanding.CALLER)
            self.must_build(self.call(self.cc + ["-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror", "-pthread",
                                                 "-I", str(lib), str(caller), str(obj), "-o", str(tree / "caller")]))
            result = self.call(self.guest(tree / "caller"))
            if source is good:
                self.check("freestanding x86 epoch/MAX trap, nested and signed trap, four threads EMULATED",
                           result.returncode == 0)
            else:
                self.check("freestanding x86 result-store mutant caught by caller EMULATED",
                           result.returncode == 1)

    def floor_controls(self):
        # This is a byte-level foreign ABI oracle, not compiler behavior:
        # mov %r15,%rax; ret; nop; nop occupies one six-byte export slot.
        source = b"om2\nexport fn floor o out uchar 64 to ulong\nput o 0 1\nret 0\nend\n"
        frame = self.frame(source, b"\x4c\x89\xf8\xc3\x90\x90", "floor")
        generated = {}
        for word in ("c", "h"):
            result = self.generate(word, frame)
            self.check("direct floor oracle generated " + word, result.returncode == 0)
            generated[word] = result.stdout
        correct = b"ombr_stk - OMBR_STACK"
        self.check("direct floor oracle finds one true-floor argument", generated["c"].count(correct) == 1)
        for name, mutated in (("floor", False), ("floor-mutant", True)):
            folder = self.out / name
            folder.mkdir()
            for ext, payload in generated.items():
                if mutated and ext == "c":
                    payload = payload.replace(correct, b"(unsigned char *)(top) - OMBR_STACK")
                (folder / ("omega_native." + ext)).write_bytes(payload)
            self.must(self.cc + ["-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                                 "-I", str(folder), str(Path(__file__).with_name("floorcheck.c")),
                                 "-pthread", "-o", str(folder / "floorcheck")])
            result = self.call(self.guest(folder / "floorcheck"))
            if mutated:
                self.check("carved-top floor mutant rejected without crash EMULATED",
                           result.returncode == 1 and b"FAIL stack floor" in result.stdout)
            else:
                self.check("actual R15 mapping floor with ABI-v2 out buffer EMULATED",
                           result.returncode == 0 and b"PASS R15 equals actual" in result.stdout)

    def finish(self):
        print("NATIVE-X86 NATIVE NOT_RUN (physical x86 execution not requested)", flush=True)
        if self.failed:
            print("NATIVE-X86 FAIL " + "; ".join(self.failed), flush=True)
            return 1
        missing = set(self.missing) | (REQUIRED - self.ran)
        if missing:
            print("NATIVE-X86 NOT_RUN (not run: " + " ".join(sorted(missing)) + ")", flush=True)
            return 1
        print("NATIVE-X86 EMULATED PASS (six languages built and run; native x86 NOT_RUN)", flush=True)
        return 0


def main():
    if len(sys.argv) > 2:
        print("usage: suite.py [EMPTY_OUTPUT]", flush=True)
        return 2
    out = Path(sys.argv[1]) if len(sys.argv) == 2 else ROOT / "build/native-x86"
    # Refuse overwriting any previous evidence. Give each integration run a fresh directory.
    if out.exists() and any(out.iterdir()):
        print("FAIL output directory must be empty: " + str(out), flush=True)
        return 1
    suite = Suite(out)
    try:
        if suite.preflight():
            for step in (suite.initial_library, suite.identity_and_code, suite.aarch64_parity,
                         suite.callers, suite.stale_and_v1, suite.refusals, suite.runtime_mutants,
                         suite.private_symbols, suite.freestanding_api, suite.trap_controls,
                         suite.freestanding_x86, suite.floor_controls):
                try:
                    step()
                except (RuntimeError, AssertionError, OSError, StopIteration) as error:
                    suite.check(step.__name__ + ": " + str(error), False)
                    if step == suite.initial_library:
                        break
    except (RuntimeError, OSError) as error:
        suite.check("preflight: " + str(error), False)
    return suite.finish()


if __name__ == "__main__":
    sys.exit(main())
