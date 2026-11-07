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

## Working setup: route through a host

The host port is not the only way out of the device. The **device** port to a PC
carries MIDI too, so the pedal can already control a downstream device with a
computer in the middle, without any firmware change:

```
pedal (USB device)  ->  PC / SBC (USB host)  ->  target (USB device)
```

This is not a workaround specific to this pedal: it is how USB-MIDI foot
controllers are connected to USB-only amplifiers in general. Two USB devices
cannot talk to each other; a host has to sit between them and route the stream.
A USB **hub** is not a host and does not help.

A Raspberry Pi class board is enough. A user report on r/BossKatana describes
routing a Line6 FBV3 to a Katana 50 Mk2 with a **Raspberry Pi 1B (512 MB)**
running a small Python script (`podtana`), i.e. plain Linux `usbmidi` on the
cheapest possible host. The same thread states the requirement explicitly:
"you need to connect both to a USB host, i.e. a PC or similar (a Raspberry Pi or
other microcomputer)". See
<https://www.reddit.com/r/BossKatana/comments/msd597/controlling_the_katana_with_a_midi_controller/>.

Practical notes for this pedal:

* Route to the port the target actually listens on. On a Katana 50 Mk2 that is
  `KATANA DAW CTRL`; a Program Change sent to `KATANA` or `KATANA CTRL` does
  nothing. Select the destination port explicitly in the router.
* The pedal's extra MIDI input port seen by the PC is a **local mirror** (see
  above); do not route it back, or messages loop.
* No latency penalty worth mentioning: routing adds one USB frame, not audible.
* This path needs no UBOOT, no patching and no recovery risk.

If a standalone (pedal -> target, no computer) link is required, the only option
is a target that exposes a **single, class-compliant USB-MIDI interface** and is
mounted by this host stack; otherwise the host probe described above has to be
extended in firmware.
