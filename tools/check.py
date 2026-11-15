#!/usr/bin/env python3
"""Run each Lua Abuse mode through pdsim and check the report blames the right thing.

Standard library only. See tools/expectations.json for what each mode must show.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "Source"
OUT = REPO / "out"
EXPECTATIONS = Path(__file__).resolve().parent / "expectations.json"
DEFAULT_SDK = "Developer/PlaydateSDK-3.1.2"

MAX_SPIKE_GROUP = 3      # frames a single spike (plus its GC tail) may span
SPIKE_SLACK = 5          # groups may start up to this many frames early
AUTO_MODES = 7           # modes the auto-cycle steps through (control first)


# --- evaluation (pure) ------------------------------------------------------

def post_warmup(frames, warmup):
    return [fr for fr in frames if fr["index"] >= warmup]


def category_totals(frames, exclude=()):
    totals = {}
    for fr in frames:
        for cat, ms in fr["categories"].items():
            if cat not in exclude:
                totals[cat] = totals.get(cat, 0.0) + ms
    return totals


def dominant_category(frames, exclude):
    totals = category_totals(frames, exclude)
    return max(totals, key=totals.get) if totals else ""


def over_budget_fraction(frames):
    if not frames:
        return 0.0
    return sum(1 for fr in frames if fr["over_budget"]) / len(frames)


def spike_groups(frames):
    groups = []
    for fr in frames:
        if not fr["over_budget"]:
            continue
        i = fr["index"]
        if groups and groups[-1][-1] == i - 1:
            groups[-1].append(i)
        else:
            groups.append([i])
    return groups


def top_hotspot(report):
    hotspots = report.get("hotspots") or []
    return hotspots[0]["name"] if hotspots else ""


def control_windows(n_frames, cycle, n_modes):
    """Frame ranges in which the auto-cycle is running control (the first mode)."""
    return [range(start, min(start + cycle, n_frames))
            for start in range(0, n_frames, cycle * n_modes)]


def evaluate(expect, report, frames, requested, warmup):
    got = report.get("frames", len(frames))
    if got < requested:
        return [f"game stopped at frame {got} of {requested}"]

    fails = []
    body = post_warmup(frames, warmup)

    if "dominant_category" in expect:
        exclude = expect.get("dominant_exclude", ["display"])
        actual = dominant_category(body, exclude)
        if actual != expect["dominant_category"]:
            fails.append(f"dominant category is {actual}, expected {expect['dominant_category']}")

    if "top_hotspot_matches" in expect:
        name = top_hotspot(report)
        if not re.search(expect["top_hotspot_matches"], name):
            fails.append(f"top hotspot is {name!r}, expected match for /{expect['top_hotspot_matches']}/")

    if "over_budget" in expect:
        over = [fr["index"] for fr in body if fr["over_budget"]]
        if expect["over_budget"]:
            frac = over_budget_fraction(body)
            if frac <= 0.5:
                fails.append(f"only {len(over)}/{len(body)} frames over budget, expected more than half")
        elif over:
            shown = ", ".join(str(i) for i in over[:10])
            fails.append(f"{len(over)} frames over budget, expected none (first: {shown})")

    if "spike_period" in expect:
        period = expect["spike_period"]
        groups = spike_groups(body)
        if len(groups) < 3:
            fails.append(f"{len(groups)} spike groups, expected at least 3")
        for g in groups:
            if len(g) > MAX_SPIKE_GROUP:
                fails.append(f"spike group at {g[0]} lasts {len(g)} frames, expected at most {MAX_SPIKE_GROUP}")
        for a, b in zip(groups, groups[1:]):
            if b[0] - a[0] < period - SPIKE_SLACK:
                fails.append(f"over-budget frame {b[0]} only {b[0] - a[0]} frames after {a[0]}, expected ~{period}")

    if expect.get("auto_control_clean"):
        cycle = expect["config"]["cycleFrames"]
        n_modes = expect.get("auto_modes", AUTO_MODES)
        by_index = {fr["index"]: fr for fr in frames}
        for win in control_windows(got, cycle, n_modes):
            # Like the warm-up: the first frames after a switch may still be
            # paying for the previous mode's teardown and garbage.
            over = [i for i in win[warmup:] if by_index.get(i, {}).get("over_budget")]
            if over:
                fails.append(f"control over budget during auto-cycle at frame {over[0]} "
                             f"(window {win.start}-{win.stop - 1}, {len(over)} frames)")

    if "avg_rows_updated_min" in expect:
        mean = sum(fr["rows_updated"] for fr in body) / len(body) if body else 0
        if mean < expect["avg_rows_updated_min"]:
            fails.append(f"average rows updated {mean:.0f}, expected at least {expect['avg_rows_updated_min']}")

    return fails


def config_check(data_dir, mode):
    """The game must never write config.json: after a run it still names `mode`."""
    try:
        cfg = json.loads((data_dir / "config.json").read_text())
    except (OSError, ValueError):
        cfg = None
    if not isinstance(cfg, dict) or cfg.get("mode") != mode:
        return ["config.json was overwritten"]
    return []


# --- running pdsim ----------------------------------------------------------

def find_sdk(env):
    given = env.get("PLAYDATE_SDK_PATH")
    if given and Path(given).is_dir():
        return Path(given)
    home = env.get("HOME")
    if home and (Path(home) / DEFAULT_SDK).is_dir():
        return Path(home) / DEFAULT_SDK
    return None


def pdsim_command(pdsim_dir):
    binary = pdsim_dir / "target" / "release" / "pdsim"
    if binary.is_file():
        return [str(binary)]
    if (pdsim_dir / "Cargo.toml").is_file():
        return ["cargo", "run", "--quiet", "--release", "--manifest-path",
                str(pdsim_dir / "Cargo.toml"), "-p", "pdsim-cli", "--"]
    return None


def run_mode(mode, frames, out_dir, sdk, pdsim, calibration, config=None):
    data_dir = Path(tempfile.mkdtemp(prefix=f"abuse-{mode}-"))
    (data_dir / "config.json").write_text(json.dumps(config or {"mode": mode}))
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "report.json"
    frames_path = out_dir / "frames.jsonl"
    for p in (report_path, frames_path):
        if p.exists():
            p.unlink()
    cmd = pdsim + ["run", str(SOURCE), "--frames", str(frames), "--data-dir", str(data_dir),
                   "--report", str(report_path), "--frames-out", str(frames_path),
                   "--screenshot", str(out_dir / "last.png"), "--sdk", str(sdk)]
    if calibration:
        cmd += ["--calibration", calibration]
    env = dict(os.environ, PLAYDATE_SDK_PATH=str(sdk))
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    (out_dir / "pdsim.log").write_text(proc.stdout + proc.stderr)
    report = json.loads(report_path.read_text()) if report_path.exists() else {"frames": 0}
    frame_list = []
    if frames_path.exists():
        frame_list = [json.loads(line) for line in frames_path.read_text().splitlines() if line.strip()]
    return report, frame_list, data_dir


def summary_line(mode, ok, report, frames, warmup):
    body = post_warmup(frames, warmup)
    top = dominant_category(body, ["display"]) or "-"
    over = sum(1 for fr in body if fr["over_budget"])
    return (f"{'PASS' if ok else 'FAIL'}  {mode:<9} top={top:<5} "
            f"hotspot={top_hotspot(report) or '-'}  over={over}/{len(body)}")


def setup_error(msg):
    print(f"check.py: {msg}", file=sys.stderr)
    sys.exit(2)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", help="check only this mode")
    ap.add_argument("--frames", type=int, help="frames per mode (default from expectations.json)")
    ap.add_argument("--calibration", help="pdsim calibration profile to pass through")
    args = ap.parse_args(argv)

    sdk = find_sdk(os.environ)
    if sdk is None:
        setup_error(f"no Playdate SDK found: set PLAYDATE_SDK_PATH or install it at ~/{DEFAULT_SDK}")
    pdsim_dir = Path(os.environ.get("PDSIM_DIR", REPO.parent / "playdate-performance-simulator"))
    pdsim = pdsim_command(pdsim_dir)
    if pdsim is None:
        setup_error(f"pdsim not found in {pdsim_dir}: build it or set PDSIM_DIR")

    spec = json.loads(EXPECTATIONS.read_text())
    modes = spec["modes"]
    if args.mode:
        if args.mode not in modes:
            setup_error(f"no expectations for mode {args.mode!r} (known: {', '.join(modes)})")
        modes = {args.mode: modes[args.mode]}

    warmup = spec.get("warmup", 10)
    all_ok = True
    for mode, expect in modes.items():
        frames = args.frames or expect.get("frames", spec.get("frames", 300))
        config = expect.get("config") or {"mode": mode}
        report, frame_list, data_dir = run_mode(mode, frames, OUT / mode, sdk, pdsim, args.calibration, config)
        fails = evaluate(expect, report, frame_list, frames, warmup) + config_check(data_dir, config["mode"])
        shutil.rmtree(data_dir, ignore_errors=True)
        all_ok &= not fails
        print(summary_line(mode, not fails, report, frame_list, warmup))
        for msg in fails:
            print(f"      {msg}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
