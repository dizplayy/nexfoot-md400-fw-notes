# 5. Ghidra workflow for the q32s core

The firmware is loaded as a raw binary at base `0x1E00000`. With the
[`kagaimiq/ghidra-jieli`](https://github.com/kagaimiq/ghidra-jieli) processor
module (language `q32s`), Ghidra 11 decompiles and disassembles the application
correctly.

## Setup

```
analyzeHeadless <project> <name> -import app.bin \
    -processor q32s:LE:32:default \
    -loader BinaryLoader -loader-baseAddr 0x1E00120
```

`app.bin` is the **decrypted payload** of the `app.bin` entry, starting at
`0x1E00120`. Importing the whole flash image also works; use `0x1E00000` as the
base in that case.

Notes:

- The module's function detection is incomplete. Several large functions are only
  reached by `call`, so `CreateFunctionCmd` is often needed before decompiling.
- Decompilation of a few functions aborts with `pcode error ... Unable to
  resolve constructor`; the surrounding code can still be read from the
  disassembly.
- String references are 32-bit immediates (`mov rX, #imm32`), so
  address -> function mapping works with a simple scalar scan.

## Useful scripts

| Script | Purpose |
|---|---|
| `tools/ghidra/gh_decomp.py` | decompile a list of addresses (creates functions if missing) |
| `tools/ghidra/gh_ranges.py` | linear disassembly of address ranges |
| `tools/ghidra/gh_scalars.py` | find instructions containing scalars in a range |
| `tools/ghidra/gh_callers.py` | callers of a function with preceding context |
| `tools/ghidra/gh_disrange.py` | disassemble a range in an existing program |
| `tools/ghidra/gh_asm.py` | assemble a line and print the bytes |

## q32s encodings (verified)

| Instruction | Bytes | Notes |
|---|---|---|
| `mov rN, #imm32` | `C0\|N`, `FF`, `lo16 LE`, `hi16 LE` | 6 bytes, N = 0..15 |
| `add rX, rY, #imm16` | `(Y<<4)\|X`, `FC`, `lo16 LE` | 4 bytes |
| `call <abs>` | `BF F3`, `rel16 LE` | `rel16 = (target - va)/2 - 2` |
| `call rN` | `80\|N`, `00` | indirect call |
| `push {rets, 0x4}` | `74 01` | mask bit for r4 |
| `pop {pc, 0x4}` | `54 01` | matches the push |
| `add sp, #imm16` (short) | `(imm16>>1) & 0xFF`, `0B` | e.g. `56 0B` = `add sp, #-0x154` |
| `add sp, #imm16` (long) | `C0 FB`, `imm16 LE` | emitted by the assembler |
| `nop` | `00 00` | 2 bytes |

The Ghidra assembler can emit most instructions but **not** the 6-byte `mov
rN, #imm32`; hand-encode it. It also refuses `goto` with an absolute target, so
prefer `mov` + `call rN` for far jumps.

## In-place patching rules

1. **Never add executable code after the last image entry.**
   The region after `p11_code` (`0x3ECB2..0x3F000` in this build) is **not
   executable**: a jump there makes the device fall back to ROM UBOOT.
2. Patch by replacing instructions with **same-length** ones, or by replacing a
   sequence with an equal-length sequence.
3. After patching, recompute the entry CRCs and re-encrypt
   (`docs/01-image-format.md`).
4. Verify the disassembly of the patched bytes before flashing.

## Example: same-length operand patch

```python
# mov r1, #0x13  ->  mov r1, #0x12
app[0x1E13FC6 - 0x1E00120:0x1E13FC6 - 0x1E00120 + 2] = bytes.fromhex("2171")
```

Both encodings are 2 bytes (`31 71` and `21 71`), so no code moves.
