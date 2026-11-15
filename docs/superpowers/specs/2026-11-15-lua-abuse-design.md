# playdate-lua-abuse — design

Date: 2026-11-15

## Intent

A Playdate game, written in Lua, whose modes each commit one well-known
performance sin on purpose and drop frames because of it. Its job is to be a
**showcase for the Playdate Performance Simulator** (`../playdate-performance-simulator`,
"pdsim"): run a mode in the simulator and its report or perf panel should point
straight at the cause — the right cost category dominates and the guilty
function or API call is the top hotspot.

"Working" here means **the simulator finds the culprit** (option A). Matching
real-device timings side by side (option B) is out of scope for now; the game
still runs on a real Playdate so B stays possible later.

## Goals

- One game, several modes, each a short, readable demo of one bad idea.
- Each mode stresses a *different* pdsim cost category, so together they show
  the simulator diagnosing, not just timing.
- An on-device menu to pick a mode, plus an **auto-cycle** entry that steps
  through every mode on a timer — for live demos in the pdsim desktop app,
  where you watch the perf panel change.
- Headless selection of a mode via `config.json` in the data folder (the same
  trick `examples/lua-stress` uses), so CI can run each mode alone.
- A check script in this repo that runs pdsim once per mode and asserts the
  report blames the right thing.

## Non-goals

- Device-vs-simulator timing comparison, calibration, or on-device frame-time
  logging (deferred; see Future).
- C code. Lua only.
- A CI workflow. `check.py` runs locally; "headless" means scriptable, not
  wired into CI yet. *(My call: CI would need to build pdsim and provide the
  SDK — a separate piece of work.)*
- Being a fun game to play. Modes are demos with a title and a one-line
  caption, not levels.

## Anti-goals (failure even if it "works")

- A mode whose report blames something other than its bad idea (e.g. the
  "sprite pile" mode where `gc` dominates). Muddled attribution defeats the
  point; fix the mode, not the expectation.
- Modes so clever the bad idea is hard to see in the source. Each mode file
  should read like a "don't do this" example.
- Assertions tied to exact cycle counts or ms values. Calibration will change
  absolute numbers; checks must be relative (which category is biggest, which
  hotspot is first, over budget or not).

## Constraints

- Must run unchanged on a real Playdate (built with `pdc`) and in pdsim.
- **SDK:** the Playdate SDK 3.1.2 is installed at
  `~/Developer/PlaydateSDK-3.1.2` (`PLAYDATE_SDK_PATH` is not set by default).
  Modes may use the real CoreLibs (`object`, `graphics`, `sprites`, `timer`).
  Tuning and checks run with the real SDK: `check.py` sets
  `PLAYDATE_SDK_PATH` to that path when it's unset, and fails clearly if no
  SDK is found rather than silently using pdsim's stand-ins. The build
  check is "`pdc Source abuse.pdx` succeeds and the game runs in Panic's
  simulator". Running it on a physical device is a manual, optional step for
  the owner.
- pdsim runs games from the `Source/` folder: PNG images and `.fnt` fonts
  only, no compiled `pdz`/`pdi` assets. Draw everything procedurally to avoid
  asset questions entirely.
- pdsim limits (`docs/accuracy.md`): sound is stubbed, all Lua C-library calls
  cost the same average, caches are folded into averages. Don't build modes
  whose story depends on those.
- Report fields available for checks (`docs/cli.md`): `avg_category_ms`
  (`lua, c, gfx, gc, display, audio, io, other`), `hotspots` (top 25,
  `{name, self_cycles, total_cycles}`, names like `fn main.lua:40`,
  `[graphics.fillRect]`, `[sprite.update]`, `[gc]`), `over_budget_frames`,
  `over_budget_frame_indices`. Per-frame JSONL (`--frames-out`) has
  `categories`, `rows_updated`, `over_budget`.
- `playdate.datastore.write` is charged to `io` in pdsim
  (`crates/pdsim-lua/lua/api.lua`).
- Simulation is deterministic: same game + config + profile → same frames.

## Approaches considered

1. **One game, one mode per run (chosen).** Each mode in its own file; menu on
   device, `config.json` in the simulator; check script runs pdsim per mode.
   Clean per-mode attribution and still one game.
2. **One tiny game per bad idea**, like pdsim's `examples/`. Simplest demos,
   but six copies of boilerplate and not "a game with modes" as the README says.
3. **One game that cycles all modes on a timer.** Best live demo, but the
   aggregate report mixes modes; checking needs per-frame slicing by frame
   range, which is fragile.

Picked 1, **plus an auto-cycle menu entry** to get 3's live-demo effect
without making the checks depend on it.

## Modes

Each mode is chosen so one category dominates. "Expected" is what the check
script asserts. Mode ids are the `config.json` values.

| id | Bad idea | Expected in report |
|---|---|---|
| `control` | A modest, well-written scene (a few sprites moving, partial redraw). The baseline: proves pdsim doesn't cry wolf. | 0 over-budget frames. |
| `garbage` | Allocate new tables/closures every frame; build strings with `..` in a loop; never reuse. | `gc` is the largest non-display category; over budget. |
| `hotloop` | Per-pixel math in Lua, globals instead of locals, recomputing constants inside the loop. | `lua` largest; top hotspot is the mode's loop function in its file. |
| `overdraw` | `gfx.clear()` and redraw the whole screen every frame, many full-screen fills/primitives, drawing that could be cached in an image. | `gfx` largest; top hotspot is a `[graphics.*]` call; average `rows_updated` ≈ 240. |
| `sprites` | Hundreds of sprites, each with its own `update`, all with collision rects and `moveWithCollisions`. | Top hotspot is a `[sprite.*]` call or the sprite update function; over budget. |
| `disk` | `playdate.datastore.write` (a large table) every frame. | `io` largest non-display category. |
| `spike` | Fine for 59 frames, then one huge burst (e.g. build a big table) every 60th frame. | Over-budget frames come only in short groups at the spike frames, ~60 apart (see Check script); the rest are under budget. |

"Over budget" for sustained modes means most frames after warm-up (see
Check script). The `display` category is a near-constant per-row cost in
every mode, which is why some checks say "largest non-display".

Each mode's intensity (allocation count, sprite count, loop size…) is a
constant at the top of its file, tuned so it is clearly over budget under the
built-in estimates *and* plausibly over budget on a device — not 100× over.

## Game structure

```
Source/
  main.lua        menu, mode switching, auto-cycle, config.json handling
  pdxinfo
  modes/
    control.lua  garbage.lua  hotloop.lua  overdraw.lua
    sprites.lua  disk.lua     spike.lua
tools/
  check.py        runs pdsim per mode and asserts expectations
  expectations.json
```

Mode interface (one table per file, returned from the file):

- `name`, `caption` (one line describing the sin, shown on screen)
- `enter()` — set up sprites/state; `update()` — called every frame;
  `exit()` — remove sprites, clear state, so the next mode starts clean.

### Menu and controls

- On launch with no `config.json`: a list of modes plus **Auto-cycle**. Up/down
  (or crank) moves, A starts. In a mode, B returns to the menu (calls `exit()`).
- The mode's name and caption are drawn in a small corner overlay. *(Builder's
  call: keep it small so it doesn't swamp `overdraw`/`control` results.)*
- **Auto-cycle**: runs each mode, `control` first, for a fixed number of
  frames, then `exit()` and the next, looping. Default
  300 frames (10 s at 30 fps). B returns to the menu.

### config.json (headless)

Read with `playdate.datastore.read("config")` at startup:

```json
{ "mode": "garbage" }            // run one mode directly, no menu
{ "mode": "auto", "cycleFrames": 150 }
```

Unknown or missing mode → menu. The game must **not** write `config.json`
itself, and the `disk` mode writes to its own filename so it never clobbers it.

## Check script (`tools/check.py`)

- Python 3, standard library only. *(My call: easy JSON handling, no deps.)*
- Locates pdsim from `$PDSIM_DIR` (default `../playdate-performance-simulator`)
  and runs `cargo run --release -p pdsim-cli -- run <this repo>/Source ...`
  from there. `$PLAYDATE_SDK_PATH` is passed through if set (CoreLibs).
- For each mode in `tools/expectations.json`: make a fresh temp data dir,
  write `config.json` with that mode, run ~300 frames with `--report` and
  `--frames-out` into an output dir (`out/<mode>/`, git-ignored), then evaluate
  that mode's expectations.
- Expectation kinds (small, fixed vocabulary): `dominant_category`
  (optionally excluding `display`), `top_hotspot_matches` (substring/regex),
  `over_budget` (true/false), `over_budget_frames_every` (N),
  `avg_rows_updated_min`.
- Prints a per-mode PASS/FAIL table with the actual top category and hotspot,
  exits non-zero on any failure.
- `--mode <id>` to run one mode.
- **Calibration:** checks run against pdsim's built-in estimates only.
  `--calibration <file>` is passed through for manual runs (e.g.
  `calibration/rev-a.json`) but isn't required to pass. *(My call: tuning
  to two profiles doubles the work for no showcase value yet.)*
- **Warm-up and frame numbering** *(my calls)*:
  - Frame indices are pdsim's 0-based `index` in the per-frame JSONL.
  - The first 10 frames are warm-up (imports, startup, first full draw) and
    are ignored by every expectation.
  - `control`: zero over-budget frames after warm-up.
  - `spike`: the mode counts its own frames from `enter()` and bursts when
    `modeFrame % 60 == 0` (skipping 0). The check finds the over-budget
    frames after warm-up and requires they come in groups ≥ 55 frames
    apart, at least 3 of them — so a GC tail of one or two frames after a
    burst is allowed, and steady-state frames must be clean. The spike
    frame should call `collectgarbage("step")` or similar only if needed to
    keep the tail short; prefer leaving GC natural.
  - "Over budget" for sustained modes: more than half the post-warm-up
    frames.

## Left to the builder

- Exact bad-idea code in each mode and its intensity constants, tuned against
  pdsim until the expectations hold with clear margins.
- Menu visuals.
- Whether `sprites` asserts on `[sprite.update]`, `[sprite.moveWithCollisions]`
  or the Lua update function — whichever pdsim actually ranks first, as long
  as it's sprite work.
- A short README section: what each mode demonstrates and how to run the
  check / open a mode in the pdsim desktop app.

## Future (not now)

- Option B: on-device frame-time logging per mode and a comparison against
  `pdsim --frames-out` with a calibrated profile.
- Modes targeting known simulator blind spots (cache effects, per-function C
  library costs) to find where pdsim is wrong.
