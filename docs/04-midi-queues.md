# 4. MIDI router architecture

The MIDI subsystem is **not** a direct send/receive. Every port and direction has
a 256-byte ring buffer in RAM, and a central task drains the buffers and calls
one handler per chunk.

Addresses below are from the specific build analysed here; the architecture is
the reusable part.

## Ring buffer model

```
struct ring {
    u8  data[256];   // base address, e.g. 0x7700
    u16 head;        // read index
    u16 tail;        // write index
    u8  state;       // wrap/overflow flag used by the helpers
};
```

The head/tail/state variables live in a separate RAM structure (base `0x5890` in
this build), not inside the 256-byte data buffer.

Three helpers implement everything:

```c
// bytes available
u16 avail(u16 head, u16 tail, u8 state);

// push: 5th and 6th arguments are passed on the stack
int push(u16 base, u16 *head, u16 *tail, u8 *state, const u8 *data, u16 len);

// drain: copies up to 32 bytes into a stack buffer and calls up to two
// callbacks (buf, len) for each chunk
void drain(u16 base, u16 *head, u16 *tail, u8 *state, cb1, cb2);
```

## Observed queue map

| Base | Direction | Producer | Consumer |
|---|---|---|---|
| `0x7D00` | MIDI input from the BLE parser | stream parser | drain -> USB-device TX + host TX |
| `0x7900` | MIDI input from the USB host | USB host IN endpoint poll | drain -> USB-device TX + BLE TX |
| `0x7A00` | unused in this build | — | — |
| `0x7800` | **BLE-MIDI TX** | push helper | BLE-MIDI packetizer -> GATT notify |
| `0x7B00` | USB device (PC) TX | push helper | USB device endpoint |
| `0x7700` | USB host TX | push helper | USB host endpoint |
| `0x7600` | internal / status | push helper (+ status ring) | internal |

The central task drains `0x7D00`, `0x7A00` and `0x7900`; the other queues are
drained by their own consumers.

## BLE-MIDI output

Queue `0x7800` is drained into a **BLE-MIDI packetizer** that prepends a header
`0x80` and inserts a `0x80` timestamp before every status byte, then calls the
GATT send helper:

```
BLE-MIDI packet = 0x80 (header)
                  then for each MIDI byte:
                    0x80 (timestamp) before bytes with bit7 set
                    byte
```

The GATT send helper takes `(connection_handle, attribute_handle, data, len,
flags)`. The attribute handle must be the **characteristic value handle**
(`0x12` in this build), not the CCCD descriptor (`0x13`).

## Output routing mask

A small router sends an internally generated MIDI message to several
destinations according to a bitmask:

| bit | destination |
|---|---|
| 0 | USB device (built as 4-byte USB-MIDI event packets) |
| 1 | USB host queue |
| 2 | BLE-MIDI queue |
| 3 | internal queue |

The default mask is `0x7` (device + host + BLE).

## Diagnostic note

The device exposes a second MIDI input port to the PC that mirrors the internal
MIDI bus. **It is a local mirror**: it shows the same bytes even when the USB
host port has no device attached. Do not use it as proof that data reached a
downstream device; use the downstream device's own reaction.
