#!/usr/bin/env python3
"""Host-only evidence-path regression for run.sh, no Omega or MAX execution.

Run: python3 max-cpu/test_run_evidence.py
RUN_SCRIPT may select an unchanged baseline or private source mutant.
The exact shell script runs in a private fixture. git, sha256sum and
tools/native are explicit test doubles; this does not test compiler admission.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(os.environ.get("RUN_SCRIPT", Path(__file__).with_name("run.sh")))


class EvidenceDestinationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="bridge-max-evidence-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for directory in ("max-cpu", "tools", "bin", "tmp", "evidence/MAX-CPU/raw"):
            (self.root / directory).mkdir(parents=True)
        shutil.copyfile(SCRIPT, self.root / "max-cpu/run.sh")
        self.record = self.root / "evidence/MAX-CPU/raw/build-lib.log"
        self.record.write_text("IMMUTABLE_ORIGINAL\n")
        for name, text in {
            "bin/git": "#!/bin/sh\nprintf 'compiler-placeholder\\n'\n",
            "bin/sha256sum": "#!/bin/sh\ncat >/dev/null\nexit 0\n",
            "tools/native": "#!/bin/sh\nprintf 'TEST_BUILD_FAILURE\\n'\nexit 73\n",
        }.items():
            path = self.root / name
            path.write_text(text)
            path.chmod(0o755)
        self.build = self.root / "build"
        self.env = dict(os.environ, PATH=str(self.root / "bin") + ":" + os.environ["PATH"],
                        BUILD=str(self.build), TMPDIR=str(self.root / "tmp"),
                        OMEGA_REPO=str(self.root / "unused-repo"))
        self.env.pop("EV", None)

    def run_script(self, ev=None):
        env = self.env.copy()
        if ev is not None:
            env["EV"] = str(ev)
        return subprocess.run(["sh", "max-cpu/run.sh"], cwd=self.root, env=env,
                              text=True, capture_output=True, timeout=10)

    def test_default_does_not_overwrite_original_even_when_build_fails(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 73, result.stderr)
        self.assertEqual(self.record.read_text(), "IMMUTABLE_ORIGINAL\n")
        paths = [line.removeprefix("evidence=") for line in result.stdout.splitlines()
                 if line.startswith("evidence=")]
        self.assertEqual(len(paths), 1, result.stdout)
        self.assertEqual((Path(paths[0]) / "build-lib.log").read_text(), "TEST_BUILD_FAILURE\n")

    def test_existing_explicit_evidence_refuses_before_build_reset(self):
        self.build.mkdir()
        marker = self.build / "keep"
        marker.write_text("existing build\n")
        result = self.run_script(self.record.parent)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("EV must name a new directory", result.stderr)
        self.assertEqual(self.record.read_text(), "IMMUTABLE_ORIGINAL\n")
        self.assertEqual(marker.read_text(), "existing build\n")

    def test_new_explicit_evidence_directory_is_used(self):
        ev = self.root / "new-evidence"
        result = self.run_script(ev)
        self.assertEqual(result.returncode, 73, result.stderr)
        self.assertEqual((ev / "build-lib.log").read_text(), "TEST_BUILD_FAILURE\n")
        self.assertEqual(self.record.read_text(), "IMMUTABLE_ORIGINAL\n")

    def test_new_explicit_evidence_under_build_refuses_before_reset(self):
        self.build.mkdir()
        marker = self.build / "keep"
        marker.write_text("existing build\n")
        ev = self.build / "evidence"
        result = self.run_script(ev)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("EV must not overlap BUILD", result.stderr)
        self.assertEqual(marker.read_text(), "existing build\n")
        self.assertEqual(self.record.read_text(), "IMMUTABLE_ORIGINAL\n")

    def test_explicit_outward_alias_uses_resolved_destination_after_reset(self):
        self.build.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        alias = self.build / "link"
        alias.symlink_to(outside, target_is_directory=True)
        result = self.run_script(alias / "new-evidence")
        self.assertEqual(result.returncode, 73, result.stderr)
        self.assertFalse(alias.exists())
        self.assertEqual((outside / "new-evidence/build-lib.log").read_text(),
                         "TEST_BUILD_FAILURE\n")
        self.assertIn(f"evidence={outside / 'new-evidence'}\n", result.stdout)
        self.assertEqual(self.record.read_text(), "IMMUTABLE_ORIGINAL\n")

    def test_dangling_explicit_evidence_link_refuses_before_reset(self):
        for index, suffix in enumerate(("", "/", "///", "/.")):
            with self.subTest(suffix=suffix):
                self.build.mkdir(exist_ok=True)
                marker = self.build / "keep"
                marker.write_text("existing build\n")
                target = self.root / f"missing-target-{index}"
                alias = self.root / f"dangling-{index}"
                alias.symlink_to(target, target_is_directory=True)
                result = self.run_script(str(alias) + suffix)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("EV must name a new directory", result.stderr)
                self.assertTrue(alias.is_symlink())
                self.assertFalse(target.exists())
                self.assertEqual(marker.read_text(), "existing build\n")

    def test_missing_explicit_parent_refuses_before_build_reset(self):
        self.build.mkdir()
        marker = self.build / "keep"
        marker.write_text("existing build\n")
        result = self.run_script(self.root / "missing-parent/evidence")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("EV must name a new directory", result.stderr)
        self.assertEqual(marker.read_text(), "existing build\n")

    def test_explicit_overlap_aliases_refuse_before_reset(self):
        self.build.mkdir()
        marker = self.build / "keep"
        marker.write_text("existing build\n")
        alias = self.root / "alias"
        alias.symlink_to(self.build, target_is_directory=True)
        for ev in (alias / "evidence", self.build / ".." / "build" / "evidence", self.build):
            with self.subTest(ev=ev):
                result = self.run_script(ev)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("EV must not overlap BUILD", result.stderr)
                self.assertEqual(marker.read_text(), "existing build\n")

    def test_default_tmpdir_inside_build_refuses_including_alias(self):
        temp = self.build / "tmp"
        temp.mkdir(parents=True)
        marker = temp / "previous-evidence"
        marker.write_text("previous evidence\n")
        alias = self.root / "tmp-alias"
        alias.symlink_to(temp, target_is_directory=True)
        for parent in (temp, alias, self.build / ".." / "build" / "tmp"):
            with self.subTest(parent=parent):
                self.env["TMPDIR"] = str(parent)
                result = self.run_script()
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("TMPDIR must be a directory outside BUILD", result.stderr)
                self.assertEqual(marker.read_text(), "previous evidence\n")

    def test_explicit_evidence_ancestor_of_build_refuses_without_creating_it(self):
        ev = self.root / "new-evidence"
        self.env["BUILD"] = str(ev / "build")
        result = self.run_script(ev)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("EV must not overlap BUILD", result.stderr)
        self.assertFalse(ev.exists())

    def test_default_rerun_keeps_previous_evidence(self):
        first = self.run_script()
        self.assertEqual(first.returncode, 73, first.stderr)
        paths = list((self.root / "tmp").glob("omega-max-cpu-evidence.*"))
        self.assertEqual(len(paths), 1)
        marker = paths[0] / "keep"
        marker.write_text("previous evidence\n")
        second = self.run_script()
        self.assertEqual(second.returncode, 73, second.stderr)
        self.assertEqual(marker.read_text(), "previous evidence\n")
        self.assertEqual(len(list((self.root / "tmp").glob("omega-max-cpu-evidence.*"))), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
