# Omega one-line installer candidate

The public command is `omega`; `om` and `omg` remain identical compatibility
aliases. This supersedes earlier primary-command wording in inherited receipts.
Existing installations are not silently upgraded or overwritten. Use their
owned uninstall command first when moving from an older installation.

## Intended public entry (NOT LIVE yet)

After the exact release payload and website script are published:

```sh
curl -fsSL https://www.aienos.com/omega/install.sh | sh
omega help
omega check hello.om
omega build hello.om -o hello
omega run hello.om
```

The installer uses `$HOME/.local` by default and leaves PATH/startup files
unchanged. If its bin directory is not already on PATH, use the printed full
path or add `$HOME/.local/bin` to PATH. It requires no sudo, cloud account,
model download or API key. Supported target remains experimental Linux ARM64.
This is a shell download/host boundary around the seed-native Omega tools,
not a claim that the current host dispatcher and installer are written in Omega.

`curl | sh` trusts the website's TLS-delivered bootstrap. The script downloads
one immutable source artifact and checks an embedded SHA256 before extraction
or installation. This is an integrity pin, not a signed-release claim. No `latest`
URL, checksum supplied by the mirror or compiler/interpreter fallback is used.
Optional `OMEGA_DOWNLOAD_URL` can select an HTTPS mirror or loopback HTTP test
server, but cannot change the expected digest. Both URLs and paths are quoted.
Download failure, hash mismatch, unsupported host and command collisions fail
without replacing unrelated files. Source installation and all three alias
smokes must succeed before the script reports success.

## Immutable payload

Payload source commit: `70459b34b8c4840c48c2b15f2edc4b2a7c39ea75`
Payload archive SHA256: `eaf37ff32d17166de403372069b52aeb98b9523ce154b8f065ae9e4c161c8480`
Archive name: `omega-developer-linux-arm64-source.tar.gz`
Recipe: `git archive --format=tar --prefix=omega/ 70459b34b8c4840c48c2b15f2edc4b2a7c39ea75 | gzip -n`

The bootstrap is intentionally committed AFTER the payload freeze, avoiding a
self-referential archive checksum. Do not rearchive the later bootstrap commit
and upload it under this digest. A runtime fix requires a new payload commit,
archive and embedded pin, then fresh affected qualification.

## Actual tests

The new alias behavior was RED for missing `omega`, then 7/7 checks passed.
The complete native suite passed after fixing its manual installation fixtures
to create all three aliases. The safety matrix expanded from57 to61 cases;
no check was removed or weakened. The first failing suite and original red
logs remain recorded. Some initial alias-red rows cascade after the old
uninstaller removes the fixture; only the discriminating missing-command and
wrong uninstall behavior constitute useful baseline evidence.

Real HTTP `curl | sh` download tests passed5/5 on BOTH the Spark and physical
Raspberry Pi5. Cases: install and run a real native program, reject tampered
payload, handle missing payload, preserve an unrelated `omega` command, reject
invalid arguments. Tests run real curl, a loopback server and real source builds,
not a fake backend. Test infrastructure uses Python only as an external host
oracle/server, never as an installed command or compiler/runtime dependency.
Both test installations were removed. No services or shell profiles changed.

## Publication order

The sole authorized desk/release owner must first publish the exact source
artifact on the public Omega product repository as an experimental prerelease,
then publish this exact script at `/omega/install.sh` and connect `/omega/`.
If version `v0.1.0-dev.1` is taken, deliberately change the pinned URL and rerun
HTTP configuration tests. Do not make a public one-line success claim until
both the actual public source asset and bootstrap URL have been read back and
the literal public command has been tested from a fresh supported host.
Current private staging branch and local HTTP tests do NOT meet that final gate.
