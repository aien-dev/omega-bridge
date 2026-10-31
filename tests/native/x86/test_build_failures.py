#!/usr/bin/env python3
"""Issue #34 controls: no missing/failed language can produce aggregate PASS.
Runs the complete x86 boundary suite for each control and the positive case.
Requires the same real toolchains/interpreter as run.sh; never emulates a build.

Optional EMPTY_OUTPUT retains every case's stdout, command/status and numbered
build/run logs. By default a fresh timestamped directory is created under
build/native-x86-controls. Evidence is never automatically deleted.
"""
import os
from datetime import datetime, timezone
from pathlib import Path
import shutil
import shlex
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    if len(sys.argv) > 2:
        print("usage: test_build_failures.py [EMPTY_OUTPUT]")
        return 2
    default = HERE.parents[2] / "build/native-x86-controls" / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + str(os.getpid()))
    out = (Path(sys.argv[1]) if len(sys.argv) == 2 else default).resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        print("FAIL output directory must be empty: " + str(out))
        return 1
    out.mkdir(parents=True, exist_ok=True)
    print("INFO control evidence: " + str(out), flush=True)
    env = dict(os.environ)
    # The positive run must resolve actual compilers, not control scripts.
    for key, default_tool in (("ZIG", "zig"), ("GO", "go")):
        value = env.get(key, default_tool)
        if not shutil.which(value):
            print("NATIVE-X86 CONTROLS NOT_RUN: real " + key + " required")
            return 1
        env[key] = shutil.which(value)

    def run_case(name, case_env):
        args = [sys.executable, str(HERE / "suite.py"), str(out / name)]
        run = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=case_env)
        (out / (name + ".log")).write_bytes(run.stdout)
        (out / (name + ".command")).write_text(
            shlex.join(args) + "\nexit=" + str(run.returncode) + "\n")
        return run

    for key, status in (("ZIG", 42), ("GO", 43)):
        fake = out / (key.lower() + "-fail")
        fake.write_text(f"#!/bin/sh\nprintf 'CONTROL: {key} build refused\\n' >&2\nexit {status}\n")
        fake.chmod(0o755)
        run = run_case(key, dict(env, **{key: str(fake)}))
        # The failing compiler's signal is in a numbered command log, and
        # the aggregate must be FAIL, not a silent skip or green run.
        signals = b"".join(p.read_bytes() for p in (out / key).glob("*.log"))
        if run.returncode == 0 or b"NATIVE-X86 FAIL" not in run.stdout or b"EMULATED PASS" in run.stdout or f"CONTROL: {key} build refused".encode() not in signals:
            sys.stdout.buffer.write(run.stdout)
            print("FAIL control " + key + ": failed build was not refused; logs: " + str(out))
            return 1
        print("PASS failed-toolchain control " + key, flush=True)
    missing = dict(env, ZIG=str(out / "absent-zig"), GO=str(out / "absent-go"))
    run = run_case("missing", missing)
    if run.returncode == 0 or b"NATIVE-X86 NOT_RUN" not in run.stdout or b"NOT_RUN zig" not in run.stdout or b"NOT_RUN go" not in run.stdout or b"EMULATED PASS" in run.stdout:
        sys.stdout.buffer.write(run.stdout)
        print("FAIL missing-toolchain control; logs: " + str(out))
        return 1
    print("PASS missing Zig and Go refuse aggregate PASS (#34)", flush=True)
    run = run_case("positive", env)
    sys.stdout.buffer.write(run.stdout)
    if run.returncode != 0 or b"NATIVE-X86 EMULATED PASS (six languages built and run; native x86 NOT_RUN)" not in run.stdout:
        print("FAIL real-toolchain positive control; logs: " + str(out))
        return 1
    for language in ("c", "cpp", "python", "rust", "zig", "go"):
        if ("PASS " + language + " caller EMULATED").encode() not in run.stdout:
            print("FAIL positive caller missing: " + language)
            return 1
    print("NATIVE-X86 CONTROLS PASS (EMULATED; native x86 NOT_RUN)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
