# JieLi AC632N / BD19 firmware notes

Reverse-engineering notes and tools for the **Nexfoot MIDI foot controller**
(MD400 platform, JieLi **AC632N / BD19** core). Everything here was derived from
a device owned by the author, for interoperability and repair purposes.

The device is configured with the vendor software **Livtra** (ToneCommand), which
speaks the `a2` API documented in `docs/07-a2-api.md`.

**No firmware images or other copyrighted binaries are distributed in this
repository.** Only documentation, scripts and offsets are published.

## What is inside

| Path | Content |
|---|---|
| `docs/01-image-format.md` | JieLi `newfw` image layout, CRCs, ENC/SFC cipher |
| `docs/02-uboot-scsi.md` | ROM UBOOT SCSI command set used for read/erase/write |
| `docs/03-flashing.md` | Flash procedure, chunk size, watchdog, recovery |
| `docs/04-midi-queues.md` | MIDI router architecture (ring buffers per port/direction) |
| `docs/05-ghidra-q32s.md` | Ghidra + `ghidra-jieli` workflow, q32s encodings, in-place patching |
| `docs/06-usb-host.md` | USB host behaviour: which devices mount and which do not |
| `docs/07-a2-api.md` | Companion API (`a2`) opcodes, BLE services, assignment fields |
| `tools/` | decrypt/encrypt, image packer, SCSI flasher, Ghidra scripts |

## Platform summary

* CPU core: JieLi **q32s** (32-bit, 2-byte aligned instructions).
* Firmware container: JieLi **`newfw`**, encrypted with the default chip key
  `0xFFFF`. Protection is a position-based XOR stream (ENC) plus a 32-byte block
  cipher (SFC), not a secure boot.
* Application code is mapped at `0x1E00000`. The application entry used for
  static analysis is `0x1E00120`.
* The ROM exposes a **USB mass-storage UBOOT** ("BD19 UBOOT") that accepts raw
  SCSI CDBs. It can read, erase and program the internal flash, and can upload a
  small loader into RAM and jump to it.

## Target device

* **Nexfoot** MIDI foot controller, **MD400** platform, JieLi AC632N (BD19) core.
* USB **device** port to a PC (USB-MIDI) and USB **host** port (USB-A) for a MIDI
  device.
* BLE: standard BLE-MIDI service plus a proprietary `a2` service.
* Host-side configuration with **Livtra** (ToneCommand), which uses the `a2` API
  described in `docs/07-a2-api.md`.

## Key findings

1. The image can be decrypted and re-encrypted byte-for-byte; `tools/roundtrip.py`
   proves the round-trip.
2. A patched application can be repacked, flashed and booted (see
   `docs/03-flashing.md`).
3. The MIDI subsystem is a set of 256-byte ring buffers, one per port and
   direction, drained by a central task (`docs/04-midi-queues.md`).
4. **Code caves after the last image entry are not executable.** A jump there
   bricks the boot until the image is rewritten from ROM UBOOT. All patches must
   therefore be same-length operand replacements inside the application area.
5. The USB host only supports **USB-MIDI class (interface class 1, subclass 3)**.
   Devices with a vendor-specific interface (class `0xFF`) never mount, and some
   composite devices (audio + several MIDI interfaces) are not mounted either
   (`docs/06-usb-host.md`).

## Legal

* Use only on hardware you own.
* No copyrighted firmware is included; obtain your own dump from your own device.
* The information is provided for interoperability, repair and security research.
* No warranty. Flashing can brick a device; recovery is described in
  `docs/03-flashing.md` but is not guaranteed.

## License

MIT for the code, CC BY 4.0 for the documentation. See `LICENSE`.
