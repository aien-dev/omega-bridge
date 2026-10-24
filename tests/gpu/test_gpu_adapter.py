#!/usr/bin/env python3
"""Tests for the native Omega GPU adapter protocol (omega-bridge#3).

The adapter is a pure boundary: it reads one request from stdin and prints a
verdict. These tests exercise acceptance, every named refusal, determinism and
the no-silent-fallback rule. No device is opened. Hardware execution remains
NOT_RUN and is reported as such by the harness and the support matrix.

Usage: test_gpu_adapter.py [--adapter build/gpu-adapter] [--artifact DIR]
"""
import argparse
import hashlib
import os
import subprocess
import sys

HDR = "omega-bridge-gpu-adapter/1"
CONTRACT = "a" * 64
ARTIFACT = "b" * 64


def negotiate(**over):
    fields = {
        "mode": "negotiate",
        "adapter": "gb10-native-cubin",
        "consumer": "max",
        "backend": "nvidia",
        "isa": "sm_121",
        "driver": "580.173.02",
        "abi": "omega-gpu-platform/1.2",
        "dtypes": "bf16,f32",
        "capabilities": "cubin-load,launch-template,memory-handoff",
        "rights": "read,execute",
        "sync": "explicit",
        "telemetry": "off",
        "contract_id": CONTRACT,
    }
    fields.update(over)
    order = ["mode", "adapter", "consumer", "backend", "isa", "driver", "abi",
             "dtypes", "capabilities", "rights", "sync", "telemetry", "contract_id"]
    return "\n".join([HDR] + [f"{k}={fields[k]}" for k in order]) + "\n"


def admit(**over):
    fields = {
        "mode": "admit",
        "adapter": "gb10-native-cubin",
        "consumer": "max",
        "backend": "nvidia",
        "isa": "sm_121",
        "driver": "580.173.02",
        "abi": "omega-gpu-platform/1.2",
        "dtypes": "bf16,f32",
        "capabilities": "cubin-load,launch-template,memory-handoff",
        "rights": "read,execute",
        "sync": "explicit",
        "telemetry": "off",
        "contract_id": CONTRACT,
        "artifact_id": ARTIFACT,
        "kernel_format": "nvidia-cubin-elf64",
        "qmd_template": "zero-va-v1",
        "receipt": "valid",
        "ownership": "producer",
        "alias": "none",
    }
    fields.update(over)
    order = ["mode", "adapter", "consumer", "backend", "isa", "driver", "abi",
             "dtypes", "capabilities", "rights", "sync", "telemetry", "contract_id",
             "artifact_id", "kernel_format", "qmd_template", "receipt", "ownership", "alias"]
    return "\n".join([HDR] + [f"{k}={fields[k]}" for k in order]) + "\n"


def run(binary, text):
    p = subprocess.run([binary], input=text.encode(), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
    return p.returncode, p.stdout.decode(errors="replace"), p.stderr.decode(errors="replace")


def parse(out):
    d = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            d[k] = v
    return d


class T:
    def __init__(self):
        self.n = 0
        self.fail = 0

    def check(self, cond, msg):
        self.n += 1
        if not cond:
            self.fail += 1
            print("FAIL:", msg)

    def verdict(self, binary, text, want):
        rc, out, err = run(binary, text)
        d = parse(out)
        if want == "ACCEPT":
            self.check(rc == 0 and d.get("verdict") == "ACCEPT", f"want ACCEPT, got rc={rc} {d} {err}")
            if d.get("verdict") == "ACCEPT":
                self.check(len(d.get("request_sha256", "")) == 64, "accept hash missing")
        else:
            self.check(rc == 3 and d.get("verdict") == "REFUSE" and d.get("code") == want,
                       f"want {want}, got rc={rc} {d} {err}")
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default=os.path.join(os.path.dirname(__file__), "../../build/gpu-adapter"))
    ap.add_argument("--artifact", default=None, help="prefix of a CUDApp exported artifact")
    args = ap.parse_args()
    t = T()
    b = args.adapter

    # Acceptance.
    t.verdict(b, negotiate(), "ACCEPT")
    t.verdict(b, admit(), "ACCEPT")
    t.verdict(b, negotiate(consumer="omega", adapter="fake-gpu", backend="fake",
                            isa="fake-1", driver="0.0.0"), "ACCEPT")
    t.verdict(b, negotiate(driver="581.2.0"), "ACCEPT")  # newer driver is compatible

    # Determinism and request binding.
    o1 = t.verdict(b, admit(), "ACCEPT")
    o2 = t.verdict(b, admit(), "ACCEPT")
    t.check(o1 == o2, "same request did not produce identical output")
    o3 = t.verdict(b, admit(artifact_id="c" * 64), "ACCEPT")
    t.check(parse(o1)["request_sha256"] != parse(o3)["request_sha256"],
            "different request produced the same hash")

    # Named refusals. Each mutation is one field.
    t.verdict(b, HDR + "\n" + negotiate(), "E_ORDER")  # duplicate header
    t.verdict(b, negotiate().replace(HDR, "omega-bridge-gpu-adapter/2"), "E_ORDER")
    t.verdict(b, negotiate(mode="probe"), "E_MODE")
    t.verdict(b, negotiate(adapter="amd-native"), "E_ADAPTER")
    t.verdict(b, negotiate(backend="rocm"), "E_BACKEND")
    t.verdict(b, negotiate(isa="sm_120"), "E_ISA")
    t.verdict(b, negotiate(driver="579.9.9"), "E_DRIVER")
    t.verdict(b, negotiate(driver="580.173"), "E_DRIVER")
    t.verdict(b, negotiate(driver="580.x.2"), "E_DRIVER")
    t.verdict(b, negotiate(abi="omega-gpu-platform/1.1"), "E_ABI")
    t.verdict(b, negotiate(dtypes="f16,f32"), "E_DTYPES")
    t.verdict(b, negotiate(capabilities="cubin-load"), "E_CAPABILITY")
    t.verdict(b, negotiate(rights="read"), "E_RIGHTS")
    t.verdict(b, negotiate(sync="implicit"), "E_SYNC")
    t.verdict(b, negotiate(telemetry="on"), "E_TELEMETRY")
    t.verdict(b, negotiate(contract_id="A" * 64), "E_CONTRACT")
    t.verdict(b, negotiate(contract_id="a" * 63), "E_CONTRACT")
    t.verdict(b, negotiate(consumer="cuda"), "E_CAPABILITY")
    # No silent fallback: asking the non-executing adapter to admit a native artifact.
    t.verdict(b, admit(adapter="fake-gpu", backend="fake", isa="fake-1", driver="0.0.0"), "E_ADAPTER")
    # Artifact refusals.
    t.verdict(b, admit(artifact_id="z" * 64), "E_ARTIFACT")
    t.verdict(b, admit(kernel_format="ptx"), "E_FORMAT")
    t.verdict(b, admit(qmd_template="live-va-v1"), "E_RELOC")
    t.verdict(b, admit(receipt="stale"), "E_RECEIPT")
    t.verdict(b, admit(receipt="missing"), "E_RECEIPT")
    t.verdict(b, admit(ownership="consumer"), "E_OWNERSHIP")
    t.verdict(b, admit(alias="alias"), "E_ALIAS")
    # Structural refusals.
    t.verdict(b, "", "E_ORDER")
    t.verdict(b, HDR + "\n", "E_ORDER")
    t.verdict(b, negotiate() + "alias=none\n", "E_ORDER")           # extra line
    t.verdict(b, negotiate().replace("isa=sm_121\n", ""), "E_ORDER")  # missing line
    t.verdict(b, negotiate().replace("mode=negotiate", "modx=negotiate"), "E_ORDER")

    # Real artifact from CUDApp, if supplied.
    if args.artifact:
        man = open(args.artifact + ".manifest").read()
        f = dict(l.split("=", 1) for l in man.splitlines() if "=" in l)
        t.verdict(b, admit(contract_id=f["contract_id"], artifact_id=f["artifact_id"]), "ACCEPT")

    print(f'SUMMARY {{"checks": {t.n}, "fail": {t.fail}}}')
    return 1 if t.fail else 0


if __name__ == "__main__":
    sys.exit(main())
