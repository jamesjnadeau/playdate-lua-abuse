import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check  # noqa: E402

CATS = ("lua", "c", "gfx", "gc", "display", "audio", "io", "other")


def f(i, over=False, rows=240, **cats):
    categories = {c: 0.0 for c in CATS}
    categories.update(cats)
    return {"index": i, "over_budget": over, "rows_updated": rows, "categories": categories}


def report(frames=300, hotspots=None):
    return {"frames": frames, "hotspots": hotspots or [{"name": "fn main.lua:1"}]}


def run(expect, frames, requested=None, rep=None, warmup=0):
    requested = requested if requested is not None else len(frames)
    return check.evaluate(expect, rep or report(requested), frames, requested, warmup)


class EvaluateTests(unittest.TestCase):
    def test_post_warmup_drops_first_frames(self):
        frames = [f(i) for i in range(15)]
        self.assertEqual([x["index"] for x in check.post_warmup(frames, 10)], [10, 11, 12, 13, 14])

    def test_dominant_excludes_display(self):
        frames = [f(i, display=5, gc=2, lua=1) for i in range(5)]
        self.assertEqual(check.dominant_category(frames, ["display"]), "gc")

    def test_over_budget_true_needs_majority(self):
        six = [f(i, over=i < 6) for i in range(10)]
        self.assertEqual(run({"over_budget": True}, six), [])
        five = [f(i, over=i < 5) for i in range(10)]
        self.assertEqual(len(run({"over_budget": True}, five)), 1)

    def test_over_budget_false_needs_zero(self):
        frames = [f(i, over=i == 7) for i in range(10)]
        fails = run({"over_budget": False}, frames)
        self.assertEqual(len(fails), 1)
        self.assertIn("7", fails[0])

    def test_spike_groups_pass(self):
        over = {60, 61, 120, 180, 240}
        frames = [f(i, over=i in over) for i in range(300)]
        self.assertEqual(run({"spike_period": 60}, frames), [])

    def test_spike_groups_fail_extra_frame(self):
        over = {60, 61, 90, 120, 180, 240}
        frames = [f(i, over=i in over) for i in range(300)]
        self.assertNotEqual(run({"spike_period": 60}, frames), [])

    def test_spike_groups_fail_too_few(self):
        over = {60, 120}
        frames = [f(i, over=i in over) for i in range(300)]
        self.assertNotEqual(run({"spike_period": 60}, frames), [])

    def test_spike_groups_fail_long_group(self):
        over = {60, 61, 62, 63, 120, 180, 240}
        frames = [f(i, over=i in over) for i in range(300)]
        self.assertNotEqual(run({"spike_period": 60}, frames), [])

    def test_top_hotspot_regex(self):
        frames = [f(i) for i in range(10)]
        rep = report(10, [{"name": "loop hotloop.lua:12"}])
        self.assertEqual(run({"top_hotspot_matches": r"hotloop\.lua"}, frames, rep=rep), [])
        fails = run({"top_hotspot_matches": r"^\[graphics"}, frames, rep=rep)
        self.assertEqual(len(fails), 1)
        self.assertIn("loop hotloop.lua:12", fails[0])

    def test_dominant_category_failure_names_actual(self):
        frames = [f(i, display=5, lua=2, gc=1) for i in range(5)]
        fails = run({"dominant_category": "gc"}, frames)
        self.assertEqual(len(fails), 1)
        self.assertIn("lua", fails[0])

    def test_rows_updated_min(self):
        frames = [f(i, rows=200) for i in range(10)]
        fails = run({"avg_rows_updated_min": 230}, frames)
        self.assertEqual(len(fails), 1)

    def test_short_run_fails(self):
        frames = [f(i, over=True) for i in range(120)]
        fails = check.evaluate({"over_budget": False}, report(120), frames, 300, 10)
        self.assertEqual(fails, ["game stopped at frame 120 of 300"])


if __name__ == "__main__":
    unittest.main()
