# Omega Bridge GPU adapter protocol v1

Status: implemented and host-qualified (`src/gpu_adapter.om`, 47 checks). No
device is opened by the adapter. Hardware load/execution is **NOT_RUN** until a
coordinated Spark window; see [GPU-SUPPORT-MATRIX.md](GPU-SUPPORT-MATRIX.md).

## 1. What this is, and what it is not

Bridge is the attachment and translation/interop owner. This adapter decides
whether a named consumer may attach to a named GPU adapter under declared
capabilities. It is a pure boundary:

- it does not encode instructions, load a cubin, allocate device memory, submit
  work or synchronize a device;
- it never returns a device pointer, virtual address, DMA handle or capability;
- it never falls back to CPU, to another backend, or to a less capable adapter;
- it has no network, telemetry or install path.

Native ownership stays with the existing projects: Omega/CUDApp own the sm_121
encoder, code generator, QMD template, driver client, artifact exporter and
verifier. MAX/Mojo extensions, if any, remain isolated third-party artifacts.

## 2. Activation

The adapter is **disabled by default** because nothing invokes it unless a
caller runs the binary. There is no daemon, no environment hook, no automatic
attachment and no write outside the caller's own files. A caller must read the
verdict and may only proceed on `ACCEPT`. `REFUSE` is final for that request.

Build (source-only, pinned seed):

```sh
sh tools/build-gpu-adapter.sh          # uses build/omc or $OMEGA_SEED
python3 tests/gpu/test_gpu_adapter.py  # 47 checks, no device
```

## 3. Wire format

One request on stdin, one response on stdout. UTF-8/ASCII, one `key=value` per
line, LF line endings. The first line is the protocol identifier. Key order is
part of the contract: unknown, duplicate or out-of-order keys are refused.

### 3.1 Negotiation (14 lines)

```
omega-bridge-gpu-adapter/1
mode=negotiate
adapter=gb10-native-cubin|fake-gpu
consumer=omega|max
backend=nvidia|fake
isa=sm_121|fake-1
driver=MAJOR.MINOR.PATCH
abi=omega-gpu-platform/1.2
dtypes=bf16,f32
capabilities=cubin-load,launch-template,memory-handoff
rights=read,execute
sync=explicit
telemetry=off
contract_id=<64 lowercase hex>
```

`gb10-native-cubin` requires `backend=nvidia`, `isa=sm_121` and a driver at
least `580.173.02`. `fake-gpu` requires `backend=fake` and `isa=fake-1`; it is
nonexecuting and exists for deterministic round-trip fixtures. The capability,
dtype, rights, sync and telemetry strings are exact sets: a request for a subset
or a superset is refused, never silently downgraded. `telemetry=off` means the
adapter itself initiates nothing; a consumer's own telemetry remains the
consumer's declared policy.

### 3.2 Artifact admission (20 lines)

Same 14 lines, then:

```
artifact_id=<64 lowercase hex>
kernel_format=nvidia-cubin-elf64
qmd_template=zero-va-v1
receipt=valid
ownership=producer
alias=none
```

`adapter=fake-gpu` cannot admit a native artifact (`E_ADAPTER`). `receipt` must
be `valid`; `stale` and `missing` are refused. `ownership=producer` means the
artifact producer (Omega/CUDApp) owns the realization and the consumer receives
only the declared rights. `alias=none` declares no overlapping inputs/outputs.
The QMD template must carry zero device addresses; a live-address QMD is
refused. Text, cubin, QMD and cbank digests are bound by the artifact manifest
and checked by the admitting loader (CUDApp `omega_native_artifact_admit`), not
re-derived here.

### 3.3 Response

`ACCEPT` (exit 0):

```
omega-bridge-gpu-adapter/1
verdict=ACCEPT
adapter=<value>
consumer=<value>
isa=<value>
contract_id=<64 hex>
request_sha256=<64 hex>
```

`REFUSE` (exit 3):

```
omega-bridge-gpu-adapter/1
verdict=REFUSE
code=E_<NAME>
request_sha256=<64 hex>
```

`request_sha256` is SHA-256 over the exact request bytes. It binds the verdict
to the request and makes replay/round-trip tests deterministic.

## 4. Named refusals

| code | meaning |
|---|---|
| `E_VERSION` | reserved |
| `E_ORDER` | wrong line count/order, duplicate or unknown key, bad header |
| `E_MODE` | unknown mode |
| `E_ADAPTER` | unknown adapter, or a nonexecuting adapter asked to admit |
| `E_BACKEND` | backend does not match the adapter |
| `E_ISA` | ISA/profile does not match the adapter |
| `E_DRIVER` | driver malformed or older than the adapter's minimum |
| `E_ABI` | platform ABI mismatch |
| `E_DTYPES` | tensor dtype set mismatch |
| `E_CAPABILITY` | requested capability set not supported (includes unknown consumer) |
| `E_RIGHTS` | rights set mismatch |
| `E_SYNC` | implicit ordering requested |
| `E_TELEMETRY` | telemetry policy not `off` |
| `E_CONTRACT` | contract id malformed |
| `E_ARTIFACT` | artifact id malformed |
| `E_FORMAT` | kernel format other than the cubin container |
| `E_RELOC` | QMD template declares a live device address |
| `E_RECEIPT` | receipt stale, missing or not `valid` |
| `E_OWNERSHIP` | ownership declaration not `producer` |
| `E_ALIAS` | alias declaration not `none` |
| `E_LIMIT` | input too large / hash failure |
| `E_IO` | stdin read failure |

A refusal carries no partial acceptance and no fallback target.

## 5. Memory, streams and lifetime (contract, not implementation)

- **Address spaces are not shared.** Omega's device VAs and a consumer's
  context VAs are distinct. Nothing in this protocol licenses reuse of a raw
  pointer, DMA handle or allocation across contexts.
- **Ownership is explicit.** The producer owns the realization and its
  resources; the consumer holds only `read,execute` for the admitted artifact.
  Transfer of a buffer requires a separate, explicit handoff with its own
  identity and lifetime; this protocol carries no buffers.
- **Synchronization is explicit.** `sync=explicit` means the consumer must
  complete the producer's declared ordering before reading results. The adapter
  does not create events or fences.
- **Failure is terminal for the request.** The adapter never retries, never
  substitutes a backend and never reports success for an unqualified device.

## 6. Reproducibility and evidence

`tools/build-gpu-adapter.sh` enforces the seed fingerprint
`191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9` and records the
source and binary hashes. `tests/gpu/test_gpu_adapter.py` covers acceptance,
determinism, request binding, every named refusal, structural corruption and the
no-fallback rule. Raw logs live in `evidence/MAX-INTEROP/3/`.

No universal compatibility, no cross-vendor execution and no performance claim
is made. Host tests are not hardware evidence.
