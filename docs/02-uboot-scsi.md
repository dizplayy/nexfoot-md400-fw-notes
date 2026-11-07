# 2. ROM UBOOT SCSI command set

The ROM exposes a USB mass-storage device (inquiry string `BD19` / `UBOOT1.00`).
Besides normal SCSI it accepts a vendor command set through **SCSI pass-through**
on the CDB, which allows reading, erasing and programming the internal flash.

## Pass-through setup (Windows)

```c
IOCTL_SCSI_PASS_THROUGH_DIRECT = 0x0004D014

SPTD {
    USHORT Length;
    UCHAR  ScsiStatus;
    UCHAR  PathId;
    UCHAR  TargetId;      // 1
    UCHAR  Lun;
    UCHAR  CdbLength;     // 16
    UCHAR  SenseInfoLength;
    UCHAR  DataIn;        // 1 = device -> host, 0 = host -> device
    ULONG  DataTransferLength;
    ULONG  TimeOutValue;  // seconds
    PVOID  DataBuffer;
    ULONG  SenseInfoOffset;
    UCHAR  Cdb[16];
}
```

Open `\\.\PhysicalDriveN` with `GENERIC_READ | GENERIC_WRITE` (requires
administrator). All addresses and lengths inside the CDB are **big-endian**; the
payload CRC is **little-endian**.

## Commands

### `FB 06` — write memory (used to upload the RAM loader)

```
FB 06 | addr32 BE | len16 BE | 00 | crc16 LE | FF FF FF FF FF
DataIn = 0, payload = len bytes
```

### `FB 08` — jump to memory

```
FB 08 | addr32 BE | arg16 BE | FF x 8
DataIn = 1, 16-byte reply
```

The captured loader is entered with `addr = 0x2000`, `arg = 0x81`.

### `FD 05` — read flash

```
FD 05 | addr32 BE | len16 BE | FF x 8
DataIn = 1, reply = len bytes
```

### `FB 01` — erase sector

```
FB 01 | addr32 BE | FF x 11
DataIn = 1, 16-byte reply
```

Sector size on this part: `0x1000` (4 KB).

### `FB 04` — write flash

```
FB 04 | addr32 BE | len16 BE | 00 | crc16 LE | FF FF FF FF FF
DataIn = 0, payload = len bytes
```

### `FC 14` — buffer size / status

```
FC 14 | FF x 14
DataIn = 1, 16-byte reply; the first 4 bytes change from 00 00 00 00 (loader
dead / ROM active) to fc 14 00 00 (loader running).
```

### `FC 0C` — reset / run application

Vendor-specific, device exits UBOOT and boots the application.

## CRC

`crc16` is CRC-16/CCITT-FALSE over the payload:

```python
def crc16(data, crc=0):
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc
```

## RAM loader

The ROM accepts a small loader uploaded with repeated `FB 06` writes at
`0x002000` and started with `FB 08`. The public loader used here is 23 040 bytes
and was uploaded in 512-byte chunks (45 writes). Once running, the loader
implements `FB 01`, `FB 04`, `FD 05` on the flash and reuses `FD 05` for reads.

The loader is itself encrypted with the same chip key, so an arbitrary loader
cannot be substituted without the key. The stock loader is enough for
read/erase/write.
