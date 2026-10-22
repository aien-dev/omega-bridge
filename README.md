# Omega native commands

I provide `om` as the primary command and `omg` as its alias. My source-only
build starts with the audited hex seed, reproduces the pinned Omega compiler,
and uses that compiler to build the converter and exact math executable.
All source checking, conversion and calculation run in native Omega. I use a
small POSIX shell dispatcher for arguments, files and processes because the
current seed does not expose those capabilities. There is no first-party C or
Rust launcher, compiler or calculator in this default command path.

I currently qualify Linux AArch64 only, without a GPU. I keep this staging
repository private pending separate audit and release. I do not claim a speedup,
Wolfram parity, automatic runtime replacement or completed system retirement.

## Install from this source checkout

```sh
quiet-build tools/install.sh --offline --prefix "$HOME/.local"
```

The prefix's parent must exist. On hosts without `quiet-build`, run the script
directly. Both command names are checked for collisions before writes. Installation
builds the seed chain once and shares the qualified compiler between components.
All pinned source is committed, so installation needs no network, sibling checkout,
prebuilt executable or source override. `--offline` makes this intent explicit;
installation is always offline. I leave PATH and shell startup files unchanged.
Before writing build outputs, the default builders refuse any symbolic link,
hardlinked file or special file anywhere in `build/`, including the build root.
Ordinary regular-file rebuilds remain supported. Preserve an unsafe output tree
and build from a fresh checkout rather than deleting files you do not own.
Use the absolute command path if the prefix's `bin` directory is not already on PATH.

```sh
"$HOME/.local/bin/om" math 'diff (x+1)^5'
printf 'eval 1/3+1/6\nexpand (x+1)^3\n' | "$HOME/.local/bin/omg" math
"$HOME/.local/bin/om" convert --to c tests/fixtures/fib.om -o /tmp/fib.c
"$HOME/.local/bin/omg" help
"$HOME/.local/bin/om" version
"$HOME/.local/bin/om" check tests/fixtures/fib.om
"$HOME/.local/bin/om" build tests/fixtures/fib.om -o /tmp/omega-fib
"$HOME/.local/bin/omg" run tests/fixtures/fib.om
```

Native [check/build/run](docs/NATIVE-DEVELOPMENT.md) use the seeded compiler
directly. Check and build never execute the source; run explicitly executes the
qualified native program with the caller's input/output and program exit status.
It is not a sandbox. Program arguments are not implemented yet. Build publishes
a private executable atomically and refuses to overwrite its own source.

Top-level text declarations now convert to C and Python with exact byte lengths,
including embedded zero and UTF-8 bytes. Text remains read-only. The seeded
four-escape grammar and capacity limits are recorded in the
[text conversion design](docs/TEXT-CONVERSION.md). Inline quoted expressions
retain their native refusal.

For a real input available in this checkout, `tests/fixtures/fib.om` can be used
with either conversion target. C output targets GNU C11/POSIX; Python output targets
Python 3. Target compilers/interpreters are needed only when you choose to run that
output. Conversion itself does not execute the source or emitted program.
Existing applications can call generated library functions under the [caller
contract](docs/ABI.md). Python/C source input conversion is not supported.

I preserve native `OK`/`REFUSED` text. A one-shot math refusal exits 65. Streaming
math preserves the native session contract: ordinary refusals allow subsequent
requests, and EOF returns zero. Transport failures retain native nonzero statuses.
Math supports bounded exact rationals, degree-16 polynomials, differentiation,
polynomial antiderivatives, substitution, GCD and linear solving. Magnitudes,
including intermediates, are limited to 128 decimal digits. My [command
contract](docs/NATIVE-COMMANDS.md), [math contract](seed/math/CONTRACT.md) and
[converter capabilities](docs/CAPABILITIES.md) define the remaining limits.

I snapshot conversion input before checking it. Conversion failures publish no
output and leave an existing destination unchanged. Successful `-o` publication
uses an atomic rename in the destination directory, with private permissions.
Symlink destinations are refused. Filenames may contain spaces or start with a
dash; `--` may precede an option-like input name. Requests never pass through eval.

## Remove and verify

```sh
"$HOME/.local/bin/omg" uninstall
quiet-build tools/test-native.sh
```

Removal checks both aliases, file contents, types and modes before deleting owned
files. It also refuses symbolic links in the named prefix and its parent folders,
including `bin` and `lib`, before and after taking the installation lock.
Changed installation files cause refusal; unrelated files and user data
remain. Installation rolls back synchronous failures. Crash/power-loss recovery,
concurrent hostile filesystem changes and multi-file atomic visibility are not
qualified. I install no watchers, runtime hooks, services, PATH rewrites or global
state. `attach`, `discover` and `status` report unsupported and exit 69.

The [qualification record](evidence/native-commands/README.md) records actual
counts and commands. The source import and exact-byte lock are documented in
[provenance](docs/NATIVE-PROVENANCE.md). My build dependencies are POSIX sh and
standard Linux text/file/hash utilities plus `readelf`, also used for native
check/build/run metadata qualification. Node, Python, GCC and
`strace` are test tools only. The [upstream AGPL-3.0 licence](provenance/OMEGA-LICENSE)
is preserved with the copied source. Retirement of existing Rust/C services and
native argument/process support remain separate work.
