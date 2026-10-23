# L720 measured results, 2026-10-23

Status: **OPEN, incomplete, no READY or deployment**.
Functional source commit4534a7bd9abb3ac4df6a08d946a198cad4bd0005.
Replay sources were exported from that commit, not read from the worktree.
Private replay root: `/home/drakestapleton/handoffs/renda8b-L720/replay-4534a7b`.

| Gate | Actual result |
|---|---|
| Qualified compiler identity | PASS,191b776e...098e9, original and private copy equal |
| Original behavioral RED | Numeric284 failing checks; checkpoint5 failing checks |
| FP8/BF16 codec replay | PASS289/289, exit0 |
| Descriptor unit replay | PASS21/21, exit0 |
| Geometry/greedy replay | PASS188/188, exit0 |
| Kernel encoding replay | PASS1022/1022 byte/field checks, exit0; not GPU semantics |
| Native real checkpoint header inspection | PASS651 descriptors, exit0 |
| External checkpoint SHA checks | PASS12/12 files, including both weight shards |
| Swapped real shard order | REFUSED65 |
| Unsupported kernel selector | REFUSED69, zero output bytes |
| Six compiled mutants | All compile0, all test exit1 |
| Independent disassembly | Both capsules decode; FADD/FMUL, correct bounds EXIT and store |
| Immutable replay capsules | Byte-identical to the disassembled artifacts |
| ELF inspection | Seven principal executables static AArch64 EXEC, no INTERP/NEEDED |
| Inspector runtime maps | Executable, anonymous data, vvar/vdso/stack only; exact replay binary match |
| Source whitespace | Native source diff --check PASS; raw readelf evidence retains7 trailing-space lines |
| GPU execution / full forward / model-quality goldens | NOT_RUN; not implemented/qualified |
| HTTP, real answer, tools, streaming, Hermes/caller cutover | NOT_RUN; no server launched |
| Shared35B health and candidate18128 availability | UNKNOWN in sandbox, no service changed |
| GitHub push | FAIL128, DNS unavailable |
| Shared ledger update | FAIL1, ledger lock read-only |

Mutant selector0 changes FP8 tie parity (2 failures);1 biases BF16 rounding
(2);2 disables shape validation (3);3 scrambles grouped-query head mapping (28);
4 changes greedy tie selection (1);5 substitutes multiply for addition (2
encoding failures). The first five are host behavioral failures; the last is
an offline instruction-contract failure, not a GPU behavioral negative control.
No failed compiler output counts as a successful mutant test.

The full staged whitespace check reported the7 raw `readelf` Magic lines with
trailing spaces. Raw command output is retained. This formatting finding does
not affect native source or executable checks and is not reported as a full
repository lint pass.

Logs retain initial compile failures: checkpoint register pressure/error12,
inspector fd/value type mismatches/error7, mutation harness unsupported break/
error9. Fixes reduced expression pressure, used int fd/long read-write results,
and explicit loop state. Those are implementation corrections, not gate waivers.
Initial numeric RED had one erroneous midpoint input and an exit-count wrap;
NUMERIC.md documents the correction. Its original combined source is preserved
in the private build directory and fingerprinted in red-source.sha256.

Compile/test recipes are in native/renda8b/README.md. Exact source and artifact
SHA256 manifests are source.sha256 and artifacts.sha256. Each replay suite has
raw compile and check logs plus ELF inspection; both disassemblies are retained.
No timing or throughput measurements were taken. There is no unmeasured speed
claim, no full-model correctness result, and no independent review claim.

Profile readback remains35B on18091 for renda1/renda2/work-control. The provider
context setting is131072 and compression setting65536 in these files; neither
is a validated8B context setting. Actual 8B config maximum is40960. Any eventual
scoped cutover must choose the qualified context cap and verify it through real
calls, not carry the35B compression limit blindly. The separate publication
harness hardcodes18091. It was inspected but neither changed nor restarted.

Source implementation is locally committed through a private Git metadata
directory for the existing assigned worktree. Normal worktree Git metadata is
read-only and still reports the original base. The private commit is real;
remote publication is not done. See the handoff for the exact final bundle.
