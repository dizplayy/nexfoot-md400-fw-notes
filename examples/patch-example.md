# Example: same-length patch end to end

Goal: change one immediate operand, rebuild the image and verify it.

## 1. Dump the flash

Use `tools/jflash.py --read-only` to obtain a 256 KB dump.

## 2. Decrypt

```
python tools/roundtrip.py decrypt dump.bin -o image_plain.bin
```

Extract the application payload (`0x2120..0x2120+0x3B8A0`) as `app.bin`:

```
python -c "b=open('image_plain.bin','rb').read(); open('app.bin','wb').write(b[0x2120:0x2120+0x3B8A0])"
```

## 3. Find and verify the target

Disassemble with Ghidra at base `0x1E00120` and confirm the instruction.
Example target: `0x1E13FC6` holding `mov r1,#0x13` (`31 71`).

## 4. Write the patch file

`patches.txt`:

```
0x1E13FC6 3171 2171   # mov r1,#0x13 -> mov r1,#0x12
```

## 5. Rebuild

```
python tools/build_patch.py --template image_plain.bin --app app.bin \
                            --patch patches.txt --out image_patched.bin
```

The script refuses the patch if the old bytes do not match, recomputes both entry
CRCs, re-encrypts, and asserts a decrypt round-trip.

## 6. Verify offline

```
python tools/roundtrip.py check image_patched.bin
```

and compare the disassembly of the patched range with the expected result.

## 7. Flash

```
python tools/jflash.py --loader bd19loader.bin --write image_patched.bin
```

The device must be in UBOOT mode. After a failed write, replug and re-run with
`--allow-present`.

## Reminder

Never place new code after the last entry (`0x3ECB2..0x3F000` in this build): the
region is not executable. Keep every patch same-length and inside the application
payload.
