#!/usr/bin/env python3
"""Run each Lua Abuse mode through pdsim and check the report blames the right thing.

Standard library only. See tools/expectations.json for what each mode must show.
"""

import re

MAX_SPIKE_GROUP = 3      # frames a single spike (plus its GC tail) may span
SPIKE_SLACK = 5          # groups may start up to this many frames early


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

    if "avg_rows_updated_min" in expect:
        mean = sum(fr["rows_updated"] for fr in body) / len(body) if body else 0
        if mean < expect["avg_rows_updated_min"]:
            fails.append(f"average rows updated {mean:.0f}, expected at least {expect['avg_rows_updated_min']}")

    return fails
