# L551 bounded text conversion design

Frozen before production edits, based on seed/omc/omc.om tok_text, s_text,
arrarg and existing src/toc.om token, array, view and target writers.

1. Token kind 4 carries a quoted source span. Quotes end on the same source
   line, including escaped quotes; a closing quote requires a blank or EOF.
   Decode only newline, tab, backslash and quote escapes. Raw LF is refused;
   raw zero, CR and all high bytes inside quotes remain bytes. Inline quoted
   expressions remain refused by the unchanged seeded whole-unit checker.
2. Store decoded bytes in a fixed 32,768-byte pool. Text and mutable globals
   share the existing eight-entry name table, with kind, pool offset, uchar
   element type and exact decoded length. Empty text has length zero. Input,
   output, name, register, numeric, recursion and other array limits stay fixed.
   Exhaustion refuses with 14 and publishes nothing. Reuse existing get/len,
   write and read-only view calls; text cannot be put/read/edit destinations.
3. Emit C static const uint8_t arrays using decimal byte initializers. Empty
   text uses a one-byte storage placeholder with logical length zero, never
   an implicit terminator. Carry const through read-only C access and view
   signatures. Keep writable read/edit access distinct. Python text uses bytes
   from numeric tuples. No source byte is pasted into target syntax.
4. Preserve the nine-case parent baseline verbatim. Add tests first and record
   real failure before changing production. Move exactly the two newly supported
   refusal sources to positive parity, keeping source bytes and assertions.
   Replace the command-suite unsupported probe with an existing unsupported
   capability; preserve its destination checks and add text conversion coverage.
5. Execute native/C/Python with stdout/stderr/status checks and independent byte
   expectations, including all 256 values, zero, escaping, view forwarding,
   bounds, malformed sources, names, combined capacities and library callers.
   Execute valid compiled mutants changing bytes, length and immutability.
   Run both complete suites, provenance negative controls and clean committed
   source-only replay under quiet-build with isolated HOME/prefix.
6. Keep seed29/math508 imports exact. Rename the historical converter pin to
   converter-parent and bind owned src/toc.om with converter-source-sha256,
   sources.sha256 and the anchored lock. Source imports remain seed/math only.
   Push verified source and evidence. Independent core review remains pending.

Only src/toc.om implements conversion. Node/Python harnesses construct fixtures,
execute independent target oracles, mutate outputs and summarize evidence; shell
reconstructs the seed and manages files/processes. No parser/runtime fallback,
new language, FFI expansion, GPU, performance or retirement claim. System
retirement remains zero. No sibling tree edits or agents.
