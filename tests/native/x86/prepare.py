#!/usr/bin/env python3
"""Extract an amd64 Ubuntu Python oracle without installing host packages.

Usage: python3 tests/native/x86/prepare.py EMPTY_OUTPUT
Reads Ubuntu noble amd64 package indices, verifies each archive against its
index SHA256 and records exact versions/digests in runtime-packages.json.
The extracted runtime is test infrastructure only, never a bridge dependency.
No interpreter or candidate binary is executed by this preparation command.
"""
import gzip
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import urllib.request

PACKAGES = ("python3.12-minimal", "libpython3.12-minimal", "libpython3.12-stdlib",
            "libexpat1", "libffi8", "zlib1g", "libbz2-1.0", "liblzma5", "libssl3t64",
            "libuuid1", "libreadline8t64", "libtinfo6", "libncursesw6", "libsqlite3-0",
            "libmpdec3", "libcrypt1", "libdb5.3t64", "libgdbm6t64", "libgdbm-compat4t64")
# These dependencies are supplied by the cross-toolchain sysroot. Record the
# sysroot separately in the integration receipt; do not copy its files here.
SYSTEM = {"libc6", "libm6", "libgcc-s1"}


def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def records(data):
    for block in data.decode().split("\n\n"):
        fields = {}
        for line in block.splitlines():
            if line and not line[0].isspace() and ": " in line:
                key, value = line.split(": ", 1)
                fields[key] = value
        if "Package" in fields:
            yield fields


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: prepare.py EMPTY_OUTPUT")
    out = Path(sys.argv[1]).resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit("refusing nonempty runtime output: " + str(out))
    out.mkdir(parents=True, exist_ok=True)
    root = out / "root"
    root.mkdir()
    available = {}
    indices = []
    # The later indices override the earlier base package versions.
    for suite in ("noble", "noble-updates", "noble-security"):
        url = f"https://archive.ubuntu.com/ubuntu/dists/{suite}/main/binary-amd64/Packages.gz"
        compressed = fetch(url)
        indices.append({"url": url, "sha256": hashlib.sha256(compressed).hexdigest()})
        for package in records(gzip.decompress(compressed)):
            if package["Package"] in PACKAGES:
                previous = available.get(package["Package"])
                if previous is None or subprocess.run(["dpkg", "--compare-versions", package["Version"], "gt", previous["Version"]]).returncode == 0:
                    available[package["Package"]] = package
    manifest = {"architecture": "amd64", "indices": indices, "packages": [],
                "sysroot_dependencies": sorted(SYSTEM), "execution": "NOT_RUN"}
    for name in PACKAGES:
        # libmpdec is not used by every distro build of CPython; it is optional
        # only if the archive does not publish it. ctypes dependencies are required.
        if name not in available:
            if name == "libmpdec3":
                continue
            raise SystemExit("package absent from indices: " + name)
        package = available[name]
        url = "https://archive.ubuntu.com/ubuntu/" + package["Filename"]
        data = fetch(url)
        actual = hashlib.sha256(data).hexdigest()
        if actual != package["SHA256"]:
            raise SystemExit("archive SHA256 mismatch: " + name)
        archive = out / Path(package["Filename"]).name
        archive.write_bytes(data)
        subprocess.run(["dpkg-deb", "--extract", str(archive), str(root)], check=True)
        manifest["packages"].append({"name": name, "version": package["Version"], "url": url, "sha256": actual})
        print(name + " " + package["Version"] + " sha256=" + actual, flush=True)
    (out / "runtime-packages.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("export OMEGA_NATIVE_X86_PYTHON=" + shlex.quote(str(root / "usr/bin/python3.12")))
    print("export OMEGA_NATIVE_X86_LIBPATH=" + shlex.quote(str(root / "usr/lib/x86_64-linux-gnu") + ":" + str(root / "lib/x86_64-linux-gnu") + ":/usr/x86_64-linux-gnu/lib"))


if __name__ == "__main__":
    main()
