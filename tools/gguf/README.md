# tools/gguf: our own GGUF writer and comparer

Part of the llama.cpp -> Omega adoption bridge ([Bridge #10](https://github.com/aien-dev/omega-bridge/issues/10)).
Format translation is Bridge's job; no model computation happens here.

| Tool | What it does |
|---|---|
| `st2gguf <checkpoint dir> <out.gguf>` | Writes a GGUF (version 3, 32-byte alignment) from a dense Qwen3 checkpoint stored in bf16 safetensors. 2-D weights are copied byte for byte as GGML BF16; 1-D norm vectors are widened exactly to f32. Tied embeddings: no `output.weight`. Tokenizer (BPE vocab, merges, added tokens, chat template) and all model parameters come from the checkpoint's own files. Refuses anything outside the profile (other architectures, attention bias, rope scaling, non-bf16 tensors, shape mismatches against `config.json`). |
| `ggufcmp <a.gguf> <b.gguf>` | Compares two GGUF files: every metadata key (type and value, arrays element for element) and every tensor (type, extents, identical bytes). Producer-only keys such as `general.name` are reported but do not fail. Exit 0 identical, 1 differences, 2 unreadable. |

Build: `tools/gguf/build.sh` (a C compiler is the only dependency). Both tools carry their own GGUF
reader/writer and a small JSON reader written from the published format facts; nothing is copied from
an outside converter.

Why C and not Omega yet: the converter needs to open and read named files; the seed's host file words
are on omega-mv PR #678 and not on main. When they land, this tool moves to `.om` like the rest of the
first-party code (omega-mv #599).

Evidence for the first frozen model (Qwen3-4B-Instruct-2507, bf16) lives in `evidence/gguf/`.
