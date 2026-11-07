#!/usr/bin/env python3
"""JieLi 'newfw' image decrypt / encrypt / round-trip check.

Usage:
    python roundtrip.py decrypt IMAGE.bin -o image_plain.bin
    python roundtrip.py encrypt PLAIN.bin -o image_enc.bin
    python roundtrip.py check   IMAGE.bin

The implementation targets the layout documented in docs/01-image-format.md
(default chip key 0xFFFF). Adjust the constants for other builds.
"""
import argparse
import struct
import sys

ENTRY_OFFS = (0x20, 0x40, 0x60, 0x80)
APP_BASE = 0x2000
APP_END = 0x3ECB2
KEY = 0xFFFF


def enc_cipher(buf, off, size, key=KEY):
    for i in range(size):
        buf[off + i] ^= key & 0xFF
        key = ((key << 1) ^ (0x1021 if key & 0x8000 else 0)) & 0xFFFF
    return key


def sfc_cipher(buf, off, size, base, key=KEY, block=32):
    for i in range(0, size, block):
        enc_cipher(buf, off + i, min(size - i, block), key ^ ((off + i - base) >> 2))


def crc16(data, crc=0):
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def bankcb_ranges(buf, base):
    """Read BANKCB headers (plaintext) -> list of (offset, size)."""
    out = []
    count = 1
    index = 0
    while index < count:
        off = base + index * 16
        bank_id, size, load, bank_off, crc = struct.unpack("<HHIIH", bytes(buf[off:off + 14]))
        if index == 0:
            count = bank_id
        out.append((base + bank_off, size))
        index += 1
    return out


def decrypt(buf):
    enc_cipher(buf, 0, 32)
    for off in ENTRY_OFFS:
        enc_cipher(buf, off, 32)

    base = ENTRY_OFFS[0] + 0x80          # uboot.boot data
    count = 1
    index = 0
    while index < count:
        hdr = base + index * 16
        enc_cipher(buf, hdr, 16)
        bank_id, size, load, bank_off, crc = struct.unpack("<HHIIH", bytes(buf[hdr:hdr + 14]))
        if index == 0:
            count = bank_id
        enc_cipher(buf, base + bank_off, size)
        index += 1

    sfc_cipher(buf, APP_BASE, APP_END - APP_BASE, APP_BASE)


def encrypt(buf):
    sfc_cipher(buf, APP_BASE, APP_END - APP_BASE, APP_BASE)

    base = ENTRY_OFFS[0] + 0x80
    for off, size in bankcb_ranges(buf, base):
        enc_cipher(buf, off, size)

    count = 1
    index = 0
    while index < count:
        hdr = base + index * 16
        bank_id = struct.unpack("<H", bytes(buf[hdr:hdr + 2]))[0]
        if index == 0:
            count = bank_id
        enc_cipher(buf, hdr, 16)
        index += 1

    for off in ENTRY_OFFS:
        enc_cipher(buf, off, 32)
    enc_cipher(buf, 0, 32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("decrypt", "encrypt", "check"))
    ap.add_argument("input")
    ap.add_argument("-o", "--output")
    args = ap.parse_args()

    data = bytearray(open(args.input, "rb").read())

    if args.mode == "decrypt":
        decrypt(data)
        out = args.output or (args.input + ".plain")
        open(out, "wb").write(data)
        print("decrypted ->", out)
        return 0

    if args.mode == "encrypt":
        encrypt(data)
        out = args.output or (args.input + ".enc")
        open(out, "wb").write(data)
        print("encrypted ->", out)
        return 0

    # check: decrypt, validate CRCs, re-encrypt, compare
    orig = bytes(data)
    decrypt(data)
    ok = True
    for off in ENTRY_OFFS:
        hcrc, hdr = struct.unpack_from("<H30s", data, off)
        good = crc16(hdr) == hcrc
        ok &= good
        print("entry @0x%04x crc=0x%04x %s" % (off, hcrc, "OK" if good else "BAD"))
    fcrc, fhdr = struct.unpack_from("<H30s", data, 0)
    hgood = crc16(fhdr) == fcrc
    ok &= hgood
    print("header crc=0x%04x %s" % (fcrc, "OK" if hgood else "BAD"))

    enc = bytearray(data)
    encrypt(enc)
    same = bytes(enc) == orig
    print("round-trip identical:", same)
    return 0 if (ok and same) else 1


if __name__ == "__main__":
    sys.exit(main())
