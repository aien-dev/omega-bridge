#!/usr/bin/env python3
"""Exercise the real runner's terminal verdict, without an Omega compiler.

Only the final shell decision is executed. These are host control-flow tests,
not native caller execution or ABI-v2 qualification.
"""

import pathlib
import subprocess
import unittest


class VerdictTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runner = pathlib.Path(__file__).with_name("run.sh").read_text()
        marker = "for l in $notrun;"
        if runner.count(marker) != 1:
            raise AssertionError("cannot identify the runner's terminal verdict uniquely")
        cls.verdict = marker + runner.split(marker, 1)[1]

    def run_verdict(self, fails, notrun):
        return subprocess.run(
            ["sh", "-eu", "-c", 'fails=$1; notrun=$2\n' + self.verdict,
             "native-v2-verdict", str(fails), notrun],
            text=True, capture_output=True, check=False,
        )

    def test_complete_success(self):
        result = self.run_verdict(0, "")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "NATIVE-V2 PASS (not run: none)\n")
        self.assertEqual(result.stderr, "")

    def test_each_missing_toolchain_is_not_run(self):
        for language in ("c++", "python", "rust", "zig", "go"):
            with self.subTest(language=language):
                result = self.run_verdict(0, " " + language)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("NOT_RUN " + language + " caller: toolchain not installed\n",
                              result.stdout)
                self.assertIn("NATIVE-V2 NOT_RUN (not run: " + language + ")\n",
                              result.stdout)
                self.assertNotIn("NATIVE-V2 PASS", result.stdout)
                self.assertEqual(result.stderr, "")

    def test_multiple_missing_toolchains_are_not_run(self):
        result = self.run_verdict(0, " zig go")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("NOT_RUN zig caller: toolchain not installed\n", result.stdout)
        self.assertIn("NOT_RUN go caller: toolchain not installed\n", result.stdout)
        self.assertIn("NATIVE-V2 NOT_RUN (not run: zig go)\n", result.stdout)
        self.assertNotIn("NATIVE-V2 PASS", result.stdout)

    def test_failure_remains_failure(self):
        result = self.run_verdict(1, "")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "NATIVE-V2 FAIL 1\n")

    def test_failure_takes_precedence_over_not_run(self):
        result = self.run_verdict(1, " zig")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("NOT_RUN zig caller: toolchain not installed\n", result.stdout)
        self.assertIn("NATIVE-V2 FAIL 1\n", result.stdout)
        self.assertNotIn("NATIVE-V2 PASS", result.stdout)
        self.assertNotIn("NATIVE-V2 NOT_RUN", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
