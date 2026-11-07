#!/usr/bin/env python3
"""JieLi BD19 / AC632N UBOOT flasher (Windows, must run elevated).

The device must already be in ROM UBOOT mode (mass-storage disk with inquiry
string "BD19 UBOOT"). Switching the device to UBOOT is device-specific and is not
performed here.

Usage:
    python jflash.py --loader bd19loader.bin --read-only
    python jflash.py --loader bd19loader.bin --write IMAGE.bin
    python jflash.py --loader bd19loader.bin --verify IMAGE.bin
    python jflash.py --loader bd19loader.bin --sector-test 0x3F000

Flags:
    --allow-present   reuse an UBOOT that is already enumerated. Only after a
                      physical replug (a live RAM loader may reinterpret FB 06).
    --from ADDR       start writing/erasing at ADDR (resume a failed write).
    --chunk BYTES     write chunk size, default 0x8000.

Protocol: see docs/02-uboot-scsi.md.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import hashlib
import sys
import time

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
IOCTL = 0x4D014
SECTOR = 0x1000


def crc16(data, crc=0):
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


class SPTD(ctypes.Structure):
    _fields_ = [("Length", wt.USHORT), ("ScsiStatus", ctypes.c_ubyte),
                ("PathId", ctypes.c_ubyte), ("TargetId", ctypes.c_ubyte),
                ("Lun", ctypes.c_ubyte), ("CdbLength", ctypes.c_ubyte),
                ("SenseInfoLength", ctypes.c_ubyte), ("DataIn", ctypes.c_ubyte),
                ("DataTransferLength", wt.ULONG), ("TimeOutValue", wt.ULONG),
                ("DataBuffer", ctypes.c_void_p), ("SenseInfoOffset", wt.ULONG),
                ("Cdb", ctypes.c_ubyte * 16)]


k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p,
                            wt.DWORD, wt.DWORD, wt.HANDLE]
k32.CreateFileW.restype = wt.HANDLE
k32.DeviceIoControl.argtypes = [wt.HANDLE, wt.DWORD, ctypes.c_void_p, wt.DWORD,
                                ctypes.c_void_p, wt.DWORD,
                                ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
k32.DeviceIoControl.restype = wt.BOOL
k32.CloseHandle.argtypes = [wt.HANDLE]
INVALID = ctypes.c_void_p(-1).value


def log(*a):
    print(*a, flush=True)


def ioctl(h, cdb, xfer, data_in, payload=None, timeout=8):
    buf = (ctypes.c_ubyte * max(xfer, 1))()
    if payload is not None:
        ctypes.memmove(buf, payload, min(len(payload), max(xfer, 1)))
    s = SPTD()
    s.Length = ctypes.sizeof(SPTD)
    s.TargetId = 1
    s.CdbLength = 16
    s.DataIn = 1 if data_in else 0
    s.DataTransferLength = xfer
    s.TimeOutValue = timeout
    s.DataBuffer = ctypes.cast(buf, ctypes.c_void_p)
    for i, b in enumerate(cdb[:16]):
        s.Cdb[i] = b
    r = wt.DWORD(0)
    ok = k32.DeviceIoControl(h, IOCTL, ctypes.byref(s), ctypes.sizeof(s),
                             ctypes.byref(s), ctypes.sizeof(s), ctypes.byref(r), None)
    return bool(ok), bytes(buf[:xfer]), s.ScsiStatus


def inquiry(h):
    ok, data, st = ioctl(h, bytes([0x12, 0, 0, 0, 36, 0]), 36, True)
    if not ok or st != 0:
        return None
    return data[8:16].decode("latin1").strip(), data[16:32].decode("latin1").strip()


def open_drive(n):
    return k32.CreateFileW("\\\\.\\PhysicalDrive%d" % n,
                           GENERIC_READ | GENERIC_WRITE, 3, None, 3, 0, None)


def find_uboot():
    for n in range(16):
        h = open_drive(n)
        if not h or h == INVALID:
            continue
        try:
            r = inquiry(h)
            if r and ("BD19" in r[0] + r[1] or "UBOOT" in (r[0] + r[1]).upper()):
                return n, h, r
        except Exception:
            pass
        k32.CloseHandle(h)
    return None, None, None


def upload_loader(h, blob):
    for off in range(0, len(blob), 512):
        chunk = blob[off:off + 512]
        cdb = (bytes([0xFB, 0x06]) + (0x2000 + off).to_bytes(4, "big") +
               len(chunk).to_bytes(2, "big") + b"\x00" +
               crc16(chunk).to_bytes(2, "little") + b"\xff" * 5)
        ok, _, st = ioctl(h, cdb, len(chunk), False, chunk)
        if not ok or st != 0:
            log("  loader upload FAIL at +0x%x" % off)
            return False
    log("  loader uploaded (%d bytes)" % len(blob))
    return True


def jump_loader(h):
    cdb = bytes([0xFB, 0x08]) + (0x2000).to_bytes(4, "big") + (0x81).to_bytes(2, "big") + b"\xff" * 8
    ok, data, st = ioctl(h, cdb, 16, True, timeout=10)
    log("  jump ok=%s reply=%s" % (ok, data.hex()))
    return ok and st == 0


def read_flash(h, addr, ln):
    cdb = bytes([0xFD, 0x05]) + addr.to_bytes(4, "big") + ln.to_bytes(2, "big") + b"\xff" * 8
    ok, data, st = ioctl(h, cdb, ln, True, timeout=20)
    return data if ok and st == 0 else None


def erase_sector(h, addr):
    cdb = bytes([0xFB, 0x01]) + addr.to_bytes(4, "big") + b"\xff" * 11
    ok, _, st = ioctl(h, cdb, 16, True, timeout=20)
    return ok and st == 0


def write_flash(h, addr, data):
    cdb = (bytes([0xFB, 0x04]) + addr.to_bytes(4, "big") + len(data).to_bytes(2, "big") +
           b"\x00" + crc16(data).to_bytes(2, "little") + b"\xff" * 5)
    ok, _, st = ioctl(h, cdb, len(data), False, data, timeout=20)
    return ok and st == 0


def program(h, image, start=0, chunk=0x8000):
    size = len(image)
    lo = start & ~0xFFF
    log("erase 0x%x..0x%x" % (lo, size))
    for addr in range(lo, size, SECTOR):
        for attempt in range(3):
            if erase_sector(h, addr):
                break
        else:
            log("  ERASE FAIL at 0x%x" % addr)
            return False
    log("write 0x%x..0x%x (chunk 0x%x)" % (start, size, chunk))
    off = start
    while off < size:
        n = min(chunk, size - off)
        for attempt in range(3):
            if write_flash(h, off, image[off:off + n]):
                break
            time.sleep(0.3)
        else:
            log("  WRITE FAIL at 0x%x" % off)
            return False
        off += n
        log("  written 0x%x / 0x%x" % (off, size))
    got = dump(h, size)
    if got is None:
        return False
    same = got == image
    log("verify: equal=%s diffs=%d" % (same, sum(1 for a, b in zip(got, image) if a != b)))
    return same


def dump(h, size, step=0x8000):
    out = bytearray(size)
    for addr in range(0, size, step):
        ln = min(step, size - addr)
        d = read_flash(h, addr, ln)
        if d is None:
            log("  read FAIL at 0x%x" % addr)
            return None
        out[addr:addr + ln] = d
    return bytes(out)


def sector_test(h, addr, size=SECTOR):
    pattern = bytes((i * 37 + 11) & 0xFF for i in range(size))
    if not erase_sector(h, addr):
        return False
    if not write_flash(h, addr, pattern):
        return False
    got = read_flash(h, addr, size)
    ok = got == pattern
    log("  pattern verify: %s" % ok)
    if not ok:
        return False
    if not erase_sector(h, addr):
        return False
    got = read_flash(h, addr, size)
    ok = got == b"\xff" * size
    log("  restore to FF: %s" % ok)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loader", required=True)
    ap.add_argument("--read-only", action="store_true")
    ap.add_argument("--write")
    ap.add_argument("--verify")
    ap.add_argument("--sector-test")
    ap.add_argument("--allow-present", action="store_true")
    ap.add_argument("--from", dest="start", type=lambda s: int(s, 0), default=0)
    ap.add_argument("--chunk", type=lambda s: int(s, 0), default=0x8000)
    args = ap.parse_args()

    log("jflash: admin=%s" % bool(ctypes.windll.shell32.IsUserAnAdmin()))
    n, h, info = find_uboot()
    if h and not args.allow_present:
        log("UBOOT already present (%s). Refusing: a previous RAM loader may still be alive." % (info,))
        log("Replug the device and re-run.")
        return 1
    if not h:
        log("UBOOT not found. Put the device in UBOOT mode first.")
        return 1
    log("UBOOT on PhysicalDrive%d %s" % (n, info))

    try:
        blob = open(args.loader, "rb").read()
        log("loader %d bytes sha256=%s" % (len(blob), hashlib.sha256(blob).hexdigest()[:16]))
        if not upload_loader(h, blob) or not jump_loader(h):
            return 1
        time.sleep(0.4)

        if args.sector_test:
            return 0 if sector_test(h, int(args.sector_test, 0)) else 1

        if args.write or args.verify:
            image = open(args.write or args.verify, "rb").read()
            log("image %s %d bytes" % (args.write or args.verify, len(image)))
            if args.verify:
                got = dump(h, len(image))
                ok = got == image
                log("verify-only: equal=%s" % ok)
                return 0 if ok else 1
            return 0 if program(h, image, args.start, args.chunk) else 1

        got = dump(h, 0x40000)
        if got is None:
            return 1
        log("dump sha256=%s" % hashlib.sha256(got).hexdigest())
        return 0
    finally:
        k32.CloseHandle(h)


if __name__ == "__main__":
    sys.exit(main())
