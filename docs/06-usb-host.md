# 6. USB host behaviour

The device has a USB **host** port (USB-A) intended to talk to a MIDI device, and
a USB **device** port (to a PC). This note documents what the host stack accepts,
based on live tests.

## What the host probe requires

The enumeration code parses the configuration descriptor and looks for an
interface with:

```
bInterfaceClass    = 0x01   (Audio)
bInterfaceSubClass = 0x03   (MIDI Streaming)
```

For each matching interface it walks the endpoint descriptors and requires a
**bulk** endpoint (attributes & 3 == 2):

- bulk IN  -> MIDI receive (host -> device)
- bulk OUT -> MIDI transmit (device -> host)

If no interface matches, or the endpoints cannot be allocated, the device is not
mounted and the transmit path is skipped entirely (there is no endpoint to write
to).

## Devices that do NOT mount

- **Vendor-specific USB** (interface class `0xFF`), even when the vendor driver
  exposes MIDI ports to the operating system. The host stack only implements the
  standard USB-MIDI class, so such a device is never enumerated.
- **Composite devices** with an audio function plus **several** MIDI
  interfaces: observed not to mount on this firmware, even though the operating
  system exposes the MIDI interfaces as standard class-compliant ports. The
  probe appears to expect a simpler topology.

## Compatibility observed (Nexfoot host port)

| Target | USB descriptor | Result on the Nexfoot host |
|---|---|---|
| Boss Katana 50 **Mk1** | vendor-specific: `Class_FF / SubClass_FF / Prot_00`, vendor driver | never mounts (no class 1/3 interface) |
| Boss Katana 50 **Mk2** | class-compliant USB-MIDI, 3 ports (`KATANA`, `KATANA DAW CTRL`, `KATANA CTRL`) | not mounted (composite audio + 3 MIDI) |

On a PC the Mk2 behaves normally: the identity request is answered on each port
(each reply returns on its own port) and a Program Change changes the amp **only
on `KATANA DAW CTRL`**. The same messages sent by the Nexfoot do not reach the amp
and the identity request sent by the Nexfoot is not answered, i.e. the device is
not delivering at all.

## Diagnostics methodology

Two traps to avoid when debugging this path:

1. **Local mirror vs. delivery.** The firmware exposes an extra MIDI input port
   to the PC that mirrors the internal MIDI bus. It shows the same bytes even
   when nothing is connected to the host port. It is not evidence of delivery.
   Always observe the downstream device's own reaction.
2. **The transmit gate.** Transmission is skipped when a mount flag is clear:

   ```
   lb.u r0, [r11 + 0x1e4]      ; mount flag
   jeq  r0, #0, <skip TX>
   ```

   Forcing this branch open (replacing it with `nop`s) has no effect if the
   mount never happened: the send path then resolves the interface pointer,
   finds zero, and returns. If forcing the gate *does* produce output, the mount
   happened but the flag was cleared.

## Practical conclusion

A device can be perfectly functional on a PC and still not work here: the PC uses
the vendor driver, while this firmware implements only standard USB-MIDI host.
For a target with a vendor-specific USB interface, no MIDI-level patch can help;
the vendor protocol would have to be implemented.
