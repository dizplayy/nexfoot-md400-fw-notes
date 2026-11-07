#!/usr/bin/env python3
"""Rebuild a flashable image from a (modified) app.bin.

Usage:
    python mkimage.py --template image_plain.bin --app app.bin --out image_new.bin
    python mkimage.py --template image_plain.bin --app app.bin --out image_new.bin --check REF_ENC.bin

The template is the decrypted flash image (docs/01-image-format.md). The script
replaces the app payload, fixes both entry CRCs, optionally re-encrypts, and
verifies a decrypt round-trip.
"""
import argparse
import struct
import sys

from roundtrip import crc16, decrypt, encrypt

APP_ENTRY = 0x2020
APP_DATA = 0x2120
APP_SIZE = 0x3B8A0   # adjust for other builds


def fix_entry(plain, app):
    plain[APP_DATA:APP_DATA + APP_SIZE] = app[:APP_SIZE]
    struct.pack_into("<I", plain, APP_ENTRY + 8, len(app))     # size
    struct.pack_into("<H", plain, APP_ENTRY + 2, crc16(app))   # data CRC
    struct.pack_into("<H", plain, APP_ENTRY,
                     crc16(bytes(plain[APP_ENTRY + 2:APP_ENTRY + 32])))  # header CRC


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True)
    ap.add_argument("--app", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--check")
    ap.add_argument("--no-encrypt", action="store_true")
    args = ap.parse_args()

    plain = bytearray(open(args.template, "rb").read())
    app = open(args.app, "rb").read()
    if len(app) != APP_SIZE:
        print("warning: app.bin is %d bytes, expected %d" % (len(app), APP_SIZE))

    fix_entry(plain, app)
    out = bytearray(plain)
    if not args.no_encrypt:
        encrypt(out)
    open(args.out, "wb").write(out)
    open(args.out + ".plain", "wb").write(plain)

    back = bytearray(out)
    if not args.no_encrypt:
        decrypt(back)
    assert bytes(back) == bytes(plain), "decrypt round-trip mismatch"
    print("wrote %s (%d bytes), app crc=0x%04x" % (args.out, len(out), crc16(app)))

    if args.check:
        ref = open(args.check, "rb").read()
        same = bytes(out) == ref
        print("matches reference:", same)
        if not same:
            diffs = sum(1 for a, b in zip(out, ref) if a != b)
            print("differing bytes:", diffs)
        return 0 if same else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
