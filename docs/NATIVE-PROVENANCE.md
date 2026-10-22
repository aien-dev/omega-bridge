# Exact source imports and build lineage

`provenance/pins` fixes the Omega seed at
29b12760f4c962606411d6bf25032aedef063301, math at
78477217b6803ad5d2b14caee40b65c7509aa40c, and the unchanged converter source at
77376b1941a020dba441a14fce8eaadea692a5b7. `seed.files` and `math.files` name every
consumed upstream file. The Omega licence is copied byte-for-byte from the math
commit into OMEGA-LICENSE. Each file, plus src/toc.om, has an exact SHA-256 in
sources.sha256. No first-party math/compiler source is translated or hand-ported.
The supplied copies are build inputs; upstream working trees are never modified.

`tools/verify-sources.sh` checks the lock's fixed digest, its component hashes,
source hashes, extra seed files and symlinks before a build. The embedded digest
anchors the checked-in lock; it is not a public-key signature. Changing a pin or
manifest requires a reviewed verifier change. A dirty, malformed or added source
include fails closed. No source import/macro expansion is added to Omega: the
unmodified math core and CLI are concatenated and checked as one unit.

To reproduce source imports from an explicitly supplied clean Git cache:

```sh
tools/import-sources.sh --offline /absolute/path/to/clean/omega-git-cache
tools/verify-sources.sh
```

The importer reads exact Git blobs, never working-tree source. A supplied dirty
cache is refused. Missing offline pins are refused. Without a supplied cache,
`tools/import-sources.sh` can fetch missing exact commits from the real private
upstream https://github.com/aien-spark/omega.git into build/source-cache, requiring
upstream access. It downloads source objects only. Installation itself uses the
committed copies, has no fetch path and does not require that cache or Git.
Existing OMEGA_SOURCE/OMEGA_SEED environment variables do not override the default
installation source chain.

The source chain is load0.sh -> seed0 -> hex1 -> asm2 -> om4 -> omc stage1 -> omc
stage2. The seed self-image and the two omc stages must match byte-for-byte. The
qualified compiler hash must be
191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9.
The same rebuilt omc builds both src/toc.om and core.om+cli.om. Every executed
build artifact must be a nonempty AArch64 ELF. The compiler, converter and math
executables must have no INTERP or NEEDED entries. This is a Linux syscall boundary,
not a claim that host shell/utilities themselves are Omega-written.

Default build/install/runtime host dependencies: POSIX sh, uname, dirname,
realpath, cat, printf, mkdir, mktemp, cp, mv, ln, chmod, readlink, rm, rmdir, find,
sort, grep, cut, tr, cmp, stat, od, sed, sha256sum, and GNU readelf/file. The seed
loader also uses awk and wc. GNU/Linux utility semantics such as mv -T, find
-delete and sha256sum --status are required. quiet-build is optional off Spark
and used for all qualification builds here. Tests additionally use Node, Python 3,
GCC (only for emitted C target tests), strace, Git and tar. No network or GPU is
needed for installation or the normal test suite. The source import verification
against an upstream Git cache is a separate explicit test.

No executable is committed. build/ is ignored. Executable hashes and tool versions
are recorded in evidence/native-commands. Existing tools/bridge and tools/test.sh
retain their original converter regression interface. The primary installed
interface is specified in NATIVE-COMMANDS.md. Generated C is an output target,
never a seed parent. All unrelated system retirement counters remain 0.
