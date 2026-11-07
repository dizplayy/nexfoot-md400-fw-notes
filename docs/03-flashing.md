# 3. Flashing procedure and practical lessons

The full pipeline is:

```
application patch -> rebuild image (CRCs + re-encrypt) -> erase -> write -> verify
```

`tools/jflash.py` implements the device side; `tools/mkimage.py` rebuilds the
image from a modified `app.bin`.

## Procedure

1. Put the device into ROM UBOOT (the vendor tool performs this; on some
   firmwares a "detach" command exists). The device re-enumerates as a
   `BD19 UBOOT` mass-storage disk.
2. Upload the RAM loader with `FB 06` writes at `0x2000`.
3. `FB 08` jump to `0x2000` with argument `0x81`.
4. Check `FC 14`: the first 4 bytes must become `fc 14 00 00`. If they stay
   `00 00 00 00` the loader did not start.
5. Erase the target sectors (`FB 01`, 4 KB each).
6. Write the image in **32 KB chunks** (`FB 04`).
7. Read back and compare (`FD 05`).
8. Reset/replug; the application starts from the written image.

## Chunk size matters

With **512-byte** chunks (504 transactions for a 258 048-byte image) the RAM
loader died around `0x3C400`. The flash was left partially written and the
device fell back to ROM UBOOT on the next boot.

With **32 KB (`0x8000`)** chunks the whole image is erased, written and verified
in seconds with no errors.

Use `0x8000`. Smaller chunks are slower and hit the watchdog/timeout.

## Recovery

If the application does not start:

1. Replug the device. The ROM UBOOT is in mask ROM and is always reachable; the
   device enumerates as `BD19 UBOOT` on its own.
2. Re-run the flasher with `--allow-present`. A physical replug guarantees that
   no RAM loader from the previous run is still active.

The flasher refuses to reuse an UBOOT that is already present **unless**
`--allow-present` is given, because a live RAM loader reinterprets `FB 06`
(memory write) while the ROM interprets it differently. Only use
`--allow-present` immediately after a physical replug.

## Validating the write path safely

Before touching the application, test on an **empty** sector (all `0xFF`):

```
erase sector -> write a 4 KB pattern -> read back (must match) -> erase -> read back (all FF)
```

`tools/jflash.py --sector-test 0x3F000` does exactly this.

## Verifying a patch offline

1. Decrypt the dump.
2. Apply the patch.
3. Recompute entry CRCs (see `docs/01-image-format.md`).
4. Re-encrypt.
5. Decrypt again and compare with the expected plaintext.

`tools/mkimage.py --check` rebuilds the original image from the unmodified
`app.bin` and must produce a byte-identical file.
