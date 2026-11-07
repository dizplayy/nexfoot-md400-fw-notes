#!/usr/bin/env python3
"""Example: apply same-length operand patches to app.bin and rebuild the image.

Usage:
    python build_patch.py --template image_plain.bin --app app.bin \
                          --patch patches.txt --out image_patched.bin

`patches.txt` lines (one per patch):
    <VA> <old-hex> <new-hex>   # comment
e.g.
    0x1E13FC6 3171 2171        # mov r1,#0x13 -> mov r1,#0x12

The script refuses to apply a patch when the bytes at the target do not match
`old-hex`, so a wrong build is caught before flashing.

VA base: 0x1E00120 for app.bin (see docs/05-ghidra-q32s.md).
"""
import argparse
import struct
import sys

from mkimage import APP_DATA, APP_ENTRY, APP_SIZE, fix_entry
from roundtrip import crc16, decrypt, encrypt

VA_BASE = 0x1E00120


def load_patches(path):
    out = []
    for line in open(path):
        line = line.split("#")[0].strip()
        if not line:
            continue
        va, old, new = line.split()[:3]
        out.append((int(va, 16), old.lower(), new.lower()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True)
    ap.add_argument("--app", required=True)
    ap.add_argument("--patch", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-encrypt", action="store_true")
    args = ap.parse_args()

    app = bytearray(open(args.app, "rb").read())

    for va, old, new in load_patches(args.patch):
        if len(old) != len(new):
            raise SystemExit("patch at 0x%X changes length (%d -> %d)" % (va, len(old) // 2, len(new) // 2))
        off = va - VA_BASE
        cur = app[off:off + len(old) // 2].hex()
        if cur != old:
            raise SystemExit("unexpected bytes at 0x%X: %s (want %s)" % (va, cur, old))
        app[off:off + len(new) // 2] = bytes.fromhex(new)
        print("0x%08X  %s -> %s" % (va, old, new))

    plain = bytearray(open(args.template, "rb").read())
    fix_entry(plain, bytes(app))

    out = bytearray(plain)
    if not args.no_encrypt:
        encrypt(out)
    open(args.out, "wb").write(out)
    open(args.out + ".plain", "wb").write(plain)

    back = bytearray(out)
    if not args.no_encrypt:
        decrypt(back)
    assert bytes(back) == bytes(plain), "round-trip mismatch"
    print("wrote %s, app crc=0x%04x" % (args.out, crc16(app)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
