# Native command integration contract, L514

Both installed aliases point to one POSIX shell entry point under
`PREFIX/lib/omega-native`. They share executables and source pins. There is no
mutable application configuration, enrollment, background process or watcher.
Invocation works from an unrelated working directory. Shell is disclosed host
glue pending L408 FR13/14; no compiler features or syscall dialects were added.

`om math 'REQUEST'` sends one newline-terminated request to the unmodified native
math CLI. Embedded newlines are usage errors. Native stdout is preserved. Native
transport errors retain their status; otherwise any REFUSED response returns 65.
`om math` directly executes the native CLI on stdin, preserving its live streaming
behavior, native statuses and documented limits. No shell math/parser/eval is used.

`om convert --to c|python [--] input.om [-o output]` snapshots a readable regular
file, invokes native omc on that snapshot, then sends the same bytes with the
existing C/P mode prefix to the native bridge. The checker output is never
executed. Both stages must succeed and emit nonempty output. No generated C is
used to build any Omega executable. Compiler/converter refusals retain their
native stderr, followed by a fixed contextual error, and normalize to exit 65.
Only after both stages succeed is stdout published or a destination-directory
temporary file atomically renamed. Existing destination symlinks/directories are
refused. Failed conversion never truncates existing output or creates a partial
destination. Successful replacement uses mode 600; existing mode/ownership are
not carried over. Atomic visibility does not claim fsync/power-loss durability.

General statuses: usage 64, native refusal/integrity 65, input unavailable 66,
unsupported 69, destination/collision 73, I/O 74. Native math transport statuses
are 1 for line transport bound, 2 for I/O, 3 for session bound. Signals follow the
shell/native process behavior. One-shot input and output are buffered in a private
temporary directory; streams are not buffered by the dispatcher.

Installation checks both aliases, including dangling symlinks, and the package
path before writes. An occupied package path causes refusal, even after a previous
partial manual removal. There is no automatic upgrade or overwrite. A per-prefix
mkdir lock serializes cooperating lifecycle operations. Synchronous publication
or smoke-test failure reverses installed aliases/package and newly created empty
directories; preexisting directories and files remain. The installer requires the
prefix parent to exist and rejects a newline in its path. Tests use isolated HOME
and prefix only. No actual account has been enrolled by qualification.

Uninstall preflights alias targets, owned hashes, regular-file types and recorded
fixed permissions, then removes only a fixed owned file list. Unknown files inside
the package are retained. Empty directories are removed only when this installation
created them. User modifications cause refusal before removal. No recursive
uninstall deletion is used. Concurrent hostile mutations and interrupted/power-loss
transactions are outside this qualification. The two aliases cannot become visible
in one filesystem operation; rollback covers synchronous failure between them.

Installed files include local SHA-256 checks. These detect accidental modifications;
they are not signatures or a defence against the account owner modifying both
files and manifests. The repository lock pins imported source bytes and the
qualified seed compiler. See NATIVE-PROVENANCE.md for the trust boundary.

`attach`, `discover`, `status` return UNSUPPORTED with exit 69. They do not scan
languages or claim Python/C/Rust replacement. The attachment branch's C launcher
was read as an installation oracle and never imported. The native TRN1 verifier
is not exposed by this task. All unrelated production retirement counters stay 0.
