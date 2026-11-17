# Ferrite-inspired K6 UI

This is a K6-sized design direction based on the interaction ideas in Ferrite, adapted to Aura and Blowfang rather than treated as a firmware port. Ferrite targets different radio hardware; the K6 has one FD6818B RF chip and a 128×64 monochrome LCD.

## Design goals

- Keep Aura as the radio: its VFO, A/B selection, memories, tuning, squelch, transmit and channel settings remain the source of truth.
- Make the standby screen calm and readable at a glance. Give the selected VFO the visual weight; show the other VFO as a compact secondary row.
- Keep the UI strictly monochrome: inverse video for selection and status, thin rules for grouping, and whitespace instead of color or dense icons.
- Keep Blowfang modules as first-class apps. The existing Blowfang launcher remains the home for installed modules; AURA RADIO returns to the normal Aura radio.
- Prefer existing Aura settings screens over parallel copies. A short route to those settings is more reliable and smaller than implementing a second settings stack.

## Proposed screens

The companion SVG shows three 128×64 mock screens at readable scale.

1. **Radio** — Aura remains in control. Highlight the active VFO/frequency, keep the other VFO and its receive state visible, and use the bottom strip for the current channel/zone and key hints. The exact fields should be drawn from Aura's live state rather than duplicated module state.
2. **Quick** — a shallow overlay for the few settings people change while operating: squelch, power, step, and tone/offset. It should hand off to Aura's existing editors for detailed changes.
3. **Blowfang** — a compact app shelf with installed modules and a clear `AURA RADIO` return entry. Each module keeps its own focused screen and exits back to the shelf/radio without changing the user's VFO or memory selection.

## Feature mapping

| Ferrite idea | K6 implementation | Placement |
| --- | --- | --- |
| A/B VFO cards | Aura's two VFOs, active side prominent and other side compact | Aura standby presentation |
| Multiple simultaneous receivers | Not available with one FD6818B; offer a scan/watch cycle and show which VFO is currently receiving | Aura RF service, cooperative scan |
| Channels and zones | Keep Aura channel manager and memory storage | Aura |
| Quick settings | Shortcuts into Aura's existing controls/editors | Aura overlay or existing menu |
| App launcher | Existing Blowfang module list, with installed modules surfaced directly | Blowfang host |
| APRS, KISS, modem tools | Separate modules backed by shared Aura/host RF and serial services | Sideloaded modules |
| GPS, Bluetooth, broadcast/HF receiver, crossband | Requires hardware the K6 does not expose | Out of scope for K6 |

## Build order

1. Freeze the screen layout and key routes in the simulator, using the actual 128×64 display model.
2. Add the radio screen treatment without replacing Aura's tuning, memory, PTT or settings logic.
3. Add a quick overlay only where Aura has an existing safe operation to call.
4. Keep module discovery and dispatch in the current Blowfang loader; expose APRS/KISS features through shared services rather than embedding each app into the base image.
5. Verify key navigation, power-off behavior, module return, and unchanged VFO/memory state in the simulator before building a radio image. Confirm display behavior on the K6 after that.

This is a design proposal, not a claim that the mock screens are already in the firmware. The simulator validates the image and control flow; only the physical radio can confirm the final LCD appearance and RF behavior.

## Reference

- [Ferrite feature list](https://ferritefw.dev/features/) — interaction inspiration only.
- [Ferrite source license](https://github.com/FerriteFW/ferrite/blob/main/LICENSE.md) — implement the adaptation independently; do not copy Ferrite code into this MIT-licensed project.
