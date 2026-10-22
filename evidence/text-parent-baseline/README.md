# Parent-frozen text baseline

This is a native reference and pre-change converter baseline, **not** proof that
the new C/Python text implementation works. Base0fc7d86, native compiler SHA256
191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9.
The parent executed both scripts on LinuxAArch64; no GPU/model/service access.

`baseline.json`: nine actual cases. Six source units accepted by the pinned native
compiler were executed and matched independent expected byte strings; all six
are refused by each old target with no output. Unknown escape, unterminated text
and inline string expression are refused by the seed. Inline quoted expressions
are therefore not a language feature promised by the follow-on.

`extended-native-oracle.json`: eight additional unique source units, encoded as
hex so arbitrary control/high bytes are preserved without committing binary
source fixtures. Actual native output covers all256 byte values in order/reverse,
a repeated alphabet and read-only view calls; attempts to put/read/edit text are
native refusals. Empty text indexed through a runtime variable compiles then
traps, with its actual status recorded. Each accepted artifact was required to be
a nonempty static AArch64 ELF before execution; compiler failures were never run.

`summary.json` aggregates both files by source SHA256:17 unique source units,
11native accepts and6native refusals. The old emitter was exercised in12 target
refusal pairs for the initial six accepted native cases; the additional eight are
frozen native references, not claimed old-emitter execution tests.

Reproduce with the supplied scripts from the tested base's own build output.
The helpers use the already qualified seed binary, verify its identity and record
actual stdout bytes/status. They do not reconstruct the same compiler separately
for every case. Generated `.elf` artifacts remain in owned handoff scratch and
are deliberately not committed.

The first probe incorrectly assumed every old text refusal was24. Raw NUL instead
reaches the old non-string-aware lexer and returns16 (src/toc.om tok rejects
control bytes). The parent inspected that code and corrected the *baseline's*
expected refusal class to16/24 while preserving actual status in each row. No
production code or acceptance gate was weakened. Native quoted text accepts raw
NUL; the new target implementation must preserve it, not continue the old refusal.

The current worker is L551, isolated branchfeat/native-text-conversion; its
immutable final source will be independently compared against these references
only after its own gates pass. Parent acceptance/core review is L555. Whole-system
retirement and automatic runtime attachment remain unqualified.
