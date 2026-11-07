# 1. Firmware image format (JieLi `newfw`)

The device stores an encrypted container in the internal flash. With the default
chip key `0xFFFF` the protection is fully reversible: it is a position-based XOR
stream (ENC) and a 32-byte block XOR (SFC), not a secure boot.

All offsets below are relative to the start of the flash image (`0x000000`).
They describe the image used during this work and may differ on other builds.

## Layout (observed)

| Offset | Size | Content |
|---|---|---|
| `0x0000` | 32 B | flash header |
| `0x0020` | 4 x 32 B | top-level entries (`uboot.boot`, `isd_config.ini`, `app_dir_head`, `key_mac`) |
| `0x00A0` | — | `uboot.boot` (BANKCB container) |
| `0x2000` | 32 B | `app_area_head` |
| `0x2020` | 32 B | `app.bin` entry |
| `0x2120` | `0x3B8A0` B | `app.bin` payload (application code) |
| `0x3D9C0` | 722 B | `cfg_tool.bin` |
| `0x3DC92` | 4128 B | `p11_code.bin` |
| `0x3ECB2` | — | end of the last entry |

The application is mapped at `0x1E00000`; the `app.bin` payload therefore starts
at VA `0x1E00120`.

## Entry structure

Every 32-byte entry starts with a CRC16:

```
struct entry {
    u16 header_crc;    // crc16 over bytes 2..31
    u16 data_crc;      // crc16 over the payload
    u16 type;
    u16 flags;
    u32 size;          // payload size  (offset +8)
    ...
};
```

Both CRCs use **CRC-16/CCITT-FALSE** (poly `0x1021`, init `0x0000`, no final XOR).

When the payload changes, the entry must be updated:

```python
entry[2:4] = crc16(payload)            # data CRC
entry[8:12] = len(payload)             # size
entry[0:2] = crc16(entry[2:32])        # header CRC
```

The flash header at `0x0000` follows the same rule: `hcrc = crc16(header[2:32])`.

## Encryption

Two primitives, both keyed with `0xFFFF` in this image.

### ENC

Per-byte XOR with the low byte of a 16-bit LFSR:

```python
def enc_cipher(buf, off, size, key=0xFFFF):
    for i in range(size):
        buf[off + i] ^= key & 0xFF
        key = ((key << 1) ^ (0x1021 if key & 0x8000 else 0)) & 0xFFFF
```

### SFC

XOR applied in 32-byte blocks, each block with a key derived from its position:

```python
def sfc_cipher(buf, off, size, base, key=0xFFFF, block=32):
    for i in range(0, size, block):
        enc_cipher(buf, off + i, min(size - i, block),
                   key ^ ((off + i - base) >> 2))
```

### Ranges

| Range | Primitive |
|---|---|
| `0x0000..0x0020` | ENC |
| `0x0020..0x00A0` (4 entries) | ENC |
| `0x00A0..` `uboot.boot` | ENC (BANKCB headers and contents) |
| `0x2000..0x3ECB2` | SFC (base `0x2000`) |

`uboot.boot` is a **BANKCB** container:

```
u16 bank_id;     // index 0: number of banks
u16 bank_size;
u32 bank_load;
u32 bank_offset; // relative to the BANKCB base
u16 bank_crc;
```

The header of each bank is 16 bytes. Decryption must read the fields *while*
decrypting, because the sizes are needed to know what to decrypt next.

## Decrypt / encrypt order

`decrypt`:

1. ENC the flash header (32 B).
2. ENC the four top-level entries (32 B each).
3. For each BANKCB bank: ENC its 16-byte header, read the fields, ENC its
   contents.
4. SFC the app area `0x2000..0x3ECB2`.

`encrypt` is the exact reverse order.

`tools/roundtrip.py` implements both and verifies that
`encrypt(decrypt(image)) == image` byte-for-byte.
