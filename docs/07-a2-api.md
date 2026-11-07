# 7. Companion API (`a2`) and BLE services

The device exposes a small host-side API called **`a2`** in the vendor software
(**Livtra** / ToneCommand). It is used to read device state, configure the
controls and trigger maintenance actions. This note records only what was
observed; it is not a complete specification.

## Transports

| Transport | Notes |
|---|---|
| USB (device port) | The device enumerates as a USB-MIDI interface; `a2` frames travel over it |
| BLE | Proprietary GATT service `0000ae00-...` (write `0xae01`, notify `0xae02`) |
| BLE-MIDI | Standard service `03b80e5a-ede8-4b33-a751-6ce34ec4c700`, characteristic `7772e5db-3868-4112-a1a9-f2669d106bf3` |

The standard BLE-MIDI characteristic is for MIDI traffic. The proprietary
`0xae00` service carries `a2` requests/replies over BLE.

## Observed opcodes

| Op | Meaning | Reply (shape) |
|---|---|---|
| `16` | device list | `{"devices":[{"kind":"md400","midi":true,"dfu":false}]}` |
| `61` | ping | `{"text":"PONG"}` |
| `62` | capabilities | firmware, protocol, feature flags, `outputMask`, `typeMask` |
| `63` | compact state | mode/page/selection fields |
| `77` | selected control | assignment object |
| `93` / `94` | SysEx slot get/set | body bytes |
| `96` | detach to UBOOT | `{"detach":true}` |
| `154` | status | mode/page/pedal fields |
| `160` | GetState | `bleStats`, `deviceEvent`, `messages[]` |
| `168` | subscribe to notifications | — |

`messages[]` is the device MIDI monitor. **It is a local mirror**: it shows
messages even when nothing is attached to the USB host port, so it must not be
used as proof of delivery.

## Assignment object

The selected control (op `77`) returns a structure with these fields:

```json
{
  "type": 0,
  "channel": 1,
  "data1": 11,
  "min": 0,
  "max": 127,
  "default": 0,
  "behavior": 0,
  "outputs": 15,
  "sysex": 0
}
```

* `outputs` is the destination bitmask (device / host / BLE / internal).
* `behavior` selects the trigger mode (set, toggle, momentary, push).
* For a CC assignment, `default` carries the controller number and `max` the
  value. For a PC assignment the two fields map to the program numbers sent on
  press and release.

Setting an assignment (op `81`/`82`) was not fully reverse-engineered during this
work: the endpoint exists but the accepted payload encoding is still unknown. The
vendor editor handles it, so assignments are practical through the UI.

## Capabilities (example)

```json
{
  "firmware": "1.0.0",
  "protocol": 1,
  "features": {
    "bleMidiState": true, "editKeyState": true, "groupedPreset": true,
    "ledState": true, "midiOut": true, "uartDetach": true, "usbHost": true
  },
  "outputMask": 15,
  "typeMask": 127,
  "encoders": 4,
  "presets": 20
}
```
