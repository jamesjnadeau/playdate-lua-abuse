# playdate-lua-abuse
a test playdate game that tries to abuse the hardware and drop frames.

This project is a playdate console game that is goal is to skip frames. It should have a couple modes trying to accomplish this. 

## Modes

Each mode commits one Lua performance sin on purpose. It is a showcase for
[pdsim](../playdate-performance-simulator): run a mode through pdsim and its
report should blame the right cause.

| id | The sin | What pdsim should show |
|---|---|---|
| `control` | none: 8 sprites, dirty-rect redraw, no per-frame allocation | no frame over budget (the simulator doesn't cry wolf) |
| `garbage` | thousands of fresh tables, closures and string pieces every frame | `gc` is the top category; most frames over budget |
| `hotloop` | per-pixel math in a Lua loop, through globals, every frame | `lua` is the top category; top hotspot in `hotloop.lua` |
| `overdraw` | 48 rotated full-screen layers plus text, every frame | `gfx` is the top category; top hotspot is a `[graphics.…]` call; nearly every row updated |
| `sprites` | 100 sprites, each with its own `update` and `moveWithCollisions` | top hotspot is a sprite call; most frames over budget |
| `disk` | `datastore.write` after every change: 100 saves per frame | `io` is the top category; most frames over budget |
| `spike` | a 40,000-table allocation burst every 60th frame, cheap otherwise | short over-budget spikes about 60 frames apart, clean in between |

There is also an **auto-cycle**: it runs every mode in the order above for a
fixed number of frames each (300 by default), control first, and loops.

The bottom line of the screen names the running mode; in auto-cycle it also
shows the mode's position, e.g. `3/7`.

## Choosing a mode

The game reads `config.json` from its data folder at startup:

- `{"mode": "garbage"}` runs that mode directly.
- `{"mode": "auto", "cycleFrames": 60}` runs the auto-cycle with 60 frames per mode.
- No config (or an unknown mode) opens the menu: up/down or the crank to
  move, A to start. B goes back to the menu from any mode.

The game never writes `config.json`.

## Checking every mode against pdsim

```bash
python3 tools/check.py
```

This builds nothing; it runs `Source/` through pdsim once per mode (300
frames by default, 900 for auto-cycle) and checks the report against
[tools/expectations.json](tools/expectations.json). The first 10 frames of
each run are ignored as warm-up. It prints one `PASS`/`FAIL` line per mode
with the reason for each failure, and keeps each run's `report.json`,
`frames.jsonl`, `pdsim.log` and `last.png` in `out/<mode>/`.

Options:

- `--mode garbage` checks one mode (`auto` for the auto-cycle).
- `--frames 600` overrides the frame count for every mode checked.
- `--calibration <profile>` is passed through to pdsim.

It finds things here:

- **pdsim:** `$PDSIM_DIR`, default `../playdate-performance-simulator`. It
  uses `target/release/pdsim` if built, otherwise `cargo run --release -p pdsim-cli`.
- **Playdate SDK:** `$PLAYDATE_SDK_PATH`, default `~/Developer/PlaydateSDK-3.1.2`.

Exit codes: `0` every mode passed, `1` some mode failed, `2` setup problem
(no SDK, no pdsim, unknown mode).

The checker's own tests:

```bash
python3 -m unittest tools/test_check.py
```

## Running a mode in pdsim yourself

Write the config into a data folder and point pdsim at it (with
`PLAYDATE_SDK_PATH` exported, or pass `--sdk`):

```bash
mkdir -p /tmp/abuse-data && echo '{"mode": "overdraw"}' > /tmp/abuse-data/config.json
```

```bash
../playdate-performance-simulator/target/release/pdsim run Source --frames 300 --data-dir /tmp/abuse-data --report /tmp/abuse-report.json
```

Without `--data-dir` pdsim uses an empty temporary folder, so the game opens
the menu. In the pdsim desktop app, open `Source/` and pick a mode from the
menu:

```bash
cd ../playdate-performance-simulator/app && npm install && npx tauri dev -- -- ../../playdate-lua-abuse/Source
```

## Building for a device

```bash
export PLAYDATE_SDK_PATH=~/Developer/PlaydateSDK-3.1.2
```

```bash
"$PLAYDATE_SDK_PATH/bin/pdc" Source abuse.pdx
```

Then sideload `abuse.pdx`, or open it in the SDK's Playdate Simulator. To
pick a mode without the menu, put `config.json` in the game's data folder
(`Data/<bundle id>/` on the device or in the simulator).
