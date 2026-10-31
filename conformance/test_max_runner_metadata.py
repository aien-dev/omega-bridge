#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
"""Host-only MAX runner metadata regression tests. No MAX installation or device.

Run: python3 conformance/test_max_runner_metadata.py
MAX_RUNNER_METADATA_SOURCE may select a private source mutant for this test.
Import-only doubles exercise the real helper without constructing a graph,
session, buffer or device. This does not establish MAX runtime compatibility.
"""
import contextlib
import os
from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest.mock import patch


RUNNER = Path(os.environ.get(
    "MAX_RUNNER_METADATA_SOURCE", Path(__file__).with_name("max_runner.py")))


class UnexpectedConstruction:
    def __init__(self, *args, **kwargs):
        raise AssertionError("metadata test constructed a MAX runtime object")


@contextlib.contextmanager
def runner(module):
    modules = {"max": module, "numpy": types.ModuleType("numpy")}
    for name, attrs in {
        "max.driver": ("Accelerator", "CPU", "Buffer"),
        "max.dtype": ("DType",),
        "max.engine": ("InferenceSession",),
        "max.graph": ("DeviceRef", "Graph", "TensorType", "ops"),
    }.items():
        stub = types.ModuleType(name)
        for attr in attrs:
            setattr(stub, attr, UnexpectedConstruction)
        modules[name] = stub
    with patch.dict(sys.modules, modules), patch.object(sys, "path", sys.path.copy()):
        yield runpy.run_path(str(RUNNER))


class MaxVersionMetadataTests(unittest.TestCase):
    def test_observed_version_is_preserved(self):
        for version in ("26.7.0", "26.8.0", "26.8.0.dev1+local"):
            with self.subTest(version=version):
                module = types.ModuleType("max")
                module.__version__ = version
                with runner(module) as namespace:
                    self.assertEqual(namespace["_max_version"](), version)

    def test_missing_version_is_unknown(self):
        with runner(types.ModuleType("max")) as namespace:
            self.assertEqual(namespace["_max_version"](), "unknown")

    def test_invalid_version_is_unknown(self):
        for version in (None, "", "   ", 267, True, (26, 7, 0)):
            with self.subTest(version=version):
                module = types.ModuleType("max")
                module.__version__ = version
                with runner(module) as namespace:
                    self.assertEqual(namespace["_max_version"](), "unknown")

    def test_unavailable_module_is_unknown(self):
        with runner(types.ModuleType("max")) as namespace:
            with patch.dict(sys.modules, {"max": None}):
                self.assertEqual(namespace["_max_version"](), "unknown")

    def test_unreadable_version_is_unknown(self):
        module = types.ModuleType("max")

        def unavailable(name):
            if name == "__version__":
                raise RuntimeError("version metadata unavailable")
            raise AttributeError(name)

        module.__getattr__ = unavailable
        with runner(module) as namespace:
            self.assertEqual(namespace["_max_version"](), "unknown")


if __name__ == "__main__":
    unittest.main(verbosity=2)
