# tools/static-re/

Small scripts for static analysis of the official keymap-tool binaries (native Swift/AppKit, unstripped). They
turned the Studio and Professional keymap tools into the command tables in `analysis/keymap-tools/` — without
running the tools.

## Expected inputs

Each script works on a disassembled binary plus two sidecar files next to it:

- `<bin>.nm`  — `nm <bin>` output as `addr<TAB>mangled`
- `<bin>.map` — the same addresses as `addr<TAB>demangled` (pipe the mangled names through `swift-demangle`)

Only the arm64 slice was analysed (`lipo -thin arm64 …`).

## Scripts

| Script | Purpose |
|---|---|
| `dis.sh <bin> <demangled-regex>` | Disassemble one function (from its symbol to the next), annotating `bl` targets with their symbol names. |
| `ann.py <bin> <start> <end>` | Disassemble an address range and annotate it with imported-stub names and inline Swift string literals (reconstructed from `movk` sequences). |
| `lits.py <bin>` | Dump the constant `UInt8` array literals embedded in driver methods (e.g. the `AA AA …` request prefixes and `55 55 …` reply prefixes). |
| `glob.py <bin> "name=globalinit_func …"` | Read the contents of static `Constants` arrays (product IDs, usage IDs, type numbers) from their one-time initializers. |

These are analysis aids, not polished tools; paths and symbol names are passed as arguments. See
`analysis/keymap-tools/README.md` for the results they produced and how the pieces fit together.
