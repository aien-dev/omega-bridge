# Get Omega and build your first project

This source distribution extends the reviewed native developer candidate
`0fc7d8662cb799e7c206b17c18ea4c3ec2b8fea9` from `aien-dev/omega-bridge`
with the `omega` public command; `om` and `omg` remain compatibility aliases.
It builds its compiler from the machine-code seed, offline. It does not need
another Omega checkout, GPU, GCC, Rust, Python, Node, model weights or an API key.

**Supported here: Linux ARM64 (`uname -sm` prints `Linux aarch64`).**
The same package has been exercised on the DGX Spark and Raspberry Pi hub.
macOS, Windows, Linux x86-64 and GPU development are not qualified by this
package. This is an experimental developer candidate, not a stable release or
a claim that every AIEN component has already migrated to Omega.

The public home is intended to be https://www.aienos.com/omega/ with downloads
on the Omega repository, https://github.com/aien-dev/omega-mv/releases .
At packaging time that public release did not exist; a local source download
and successful tests are not public publication. Do not use private staging
repository access as the public installation method.

## 1. Extract and install

Verify the downloaded archive against the separately supplied `SHA256SUMS`,
then extract it. Do not execute an unverified download piped into a shell.

```sh
sha256sum -c SHA256SUMS
tar -xzf omega-developer-linux-arm64-source.tar.gz
cd omega
./tools/install.sh --offline --prefix "$HOME/.local"
```

The prefix's parent must already exist. Existing `om`, `omg` or Omega payload
files cause a refusal rather than being overwritten. The installer leaves PATH,
shell startup files and services unchanged. Use the full command path below;
adding `$HOME/.local/bin` to PATH is optional.

The installer requires POSIX sh, standard GNU/Linux file/text/hash utilities
and GNU `readelf` (normally the `binutils` package). Shell and those utilities
handle installation, arguments and processes. Compilation and program execution
use seed-built native Omega; there is no foreign compiler/interpreter fallback.
Do not describe this package as eliminating all host utilities.

## 2. Start a project anywhere

Leave the downloaded source directory. Omega works on your own project files:

```sh
mkdir -p "$HOME/omega-hello"
cd "$HOME/omega-hello"
printf 'text msg "Hello from Omega\\n"\nfn main to int\nw = write 1 msg 0 len msg\nret 0\nend\n' > hello.om
"$HOME/.local/bin/omega" check hello.om
"$HOME/.local/bin/omega" build hello.om -o hello
./hello
"$HOME/.local/bin/omega" run hello.om
```

Both execution commands print:

```text
Hello from Omega
```

Successful `check` and `build` are silent and do not execute your program.
`build` emits a native AArch64 executable. `run` checks, compiles and executes
with your stdin/stdout/stderr and preserves the program's exit status.
Execution is **not a sandbox**. Program command-line arguments are not supported
yet; use the documented fixed-buffer stdin/stdout facilities where appropriate.

`omg` is an alias to exactly the same implementation and state, not another tool:

```sh
"$HOME/.local/bin/omg" run hello.om
"$HOME/.local/bin/omega" version
"$HOME/.local/bin/omega" help
```

## 3. Explore the supported tools

```sh
"$HOME/.local/bin/omega" math 'eval 1/3+1/6'
"$HOME/.local/bin/omega" math 'diff x^2'
```

These print `OK 1/2` and `OK 2*x`. Exact math is bounded, not a universal CAS.
Read `docs/NATIVE-DEVELOPMENT.md`, `docs/NATIVE-COMMANDS.md`,
`docs/CAPABILITIES.md`, `docs/ABI.md` and `seed/math/CONTRACT.md` before using
features beyond the first project. Examples and refusal cases are included in
`tests/fixtures/`. Optional C/Python conversion is outward interoperability,
not the compiler's implementation or a way to import arbitrary existing projects.
Automatic runtime attachment is not implemented in this candidate.

## 4. Remove the installed commands

```sh
"$HOME/.local/bin/omega" uninstall
```

Removal checks the owned installed files and preserves unrelated files.
Your `omega-hello` project is yours and remains untouched. No background watcher
or service is installed. See README.md for filesystem and recovery limitations.

## Verification and provenance

The distributor reran source installation into isolated prefixes on both the
Spark and a non-Spark Linux ARM64 Raspberry Pi. Each compiled and ran a project
outside the checkout, checked both command names, tested a nonzero program exit,
refused invalid source and removed the installation. Native compiler, converter,
math executable and hello output hashes matched across hosts. This qualifies the
listed host path, not GPU functionality, all platforms or a stable release.
Full raw logs, source archive hashes and replay script accompany the publication
handoff. Existing deeper qualification and independent review remain under
`evidence/native-developer-commands/` and the inherited evidence directories.
