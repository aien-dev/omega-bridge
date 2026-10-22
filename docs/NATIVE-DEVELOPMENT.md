# Native checking, building and execution

`om` is the primary command. `omg` is its alias to the exact same implementation.
These commands use the installed, source-rebuilt seeded Omega compiler. They do
not translate through C, use a Python interpreter or add new language features.
Qualified platform remains Linux AArch64.

```sh
om check program.om
om build program.om -o program
om run program.om
# Exactly equivalent:
omg run program.om
```

`check` compiles to a private temporary artifact, requires a nonempty static
AArch64 EXEC ELF and discards it. Success is silent. `build` uses the same checks
and atomically publishes an executable with private mode700. Neither executes
the source. The compiler's native subset is broader than the optional converter's
C/Python subset; a native-valid program can still be refused by conversion.

`run` validates and compiles first, then executes that native artifact with the
caller's stdin/stdout/stderr. Compilation reads a source snapshot, not the
program's input stream. Normal program exit statuses are returned unchanged.
This is explicit code execution, **not a sandbox**. Signal behavior follows the
host shell/native processes; this does not qualify new process-control features.

Source must name a readable regular file. Symlinked source is snapshotted.
Use `--` before a leading-dash input name. A literal filename `-` means that file,
not stdin. Program arguments are not supported yet; extra arguments return64.
No source-from-stdin mode or implicit download is added.

Build requires `-o`. Successful replacement of a regular output file is explicit
and atomic, like existing conversion output; existing mode/ownership are not
retained. Output symlinks and nonregular files are refused. Output must not refer
to the source's own inode, preventing source destruction through equal paths or
aliases. On compilation, ELF qualification or publication failure, old output
remains intact. Private request/staging files are removed after normal completion.
Atomic visibility is not a power-loss durability guarantee.

The installed `verify-elf.sh` is owned, mode700, included in file integrity checks
and the fixed uninstall list. It uses host GNU readelf to inspect metadata; it
performs no Omega program computation. POSIX shell and Linux utilities remain
disclosed host glue, not a first-party C/Rust compiler or runtime fallback.

Statuses:64usage/unsupported program arguments,65compile/ELF/integrity refusal,
66input unavailable,73output conflict/publication failure,74I/O. Once a valid
program is launched, its own status takes precedence and is not remapped to65.
Existing math/conversion behavior, both aliases, immutable source pins, native
binary identities, installer rollback and filesystem-link protections remain.

Tests are in `tests/native/developer-commands.mjs`; they execute real installed
commands in isolated HOME/prefixes. They cover native stdout and nonzero status,
binary stdin, silent non-executing check/build, executable output, path quoting,
source/output collision, failed-output preservation, wrong-native-compiler ELF
refusal, helper integrity, cleanup, aliases and uninstall. The runtime exec trace
checks that no foreign compiler or interpreter fallback runs. The original
full suite remains part of `tools/test-native.sh`.

No actual account enrollment, background watcher, runtime attachment, service
replacement, broader legacy retirement or speedup is claimed by this addition.
