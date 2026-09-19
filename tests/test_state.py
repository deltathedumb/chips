"""The engine: prices, the tick, the clock, and saving."""

import json
import math
import os
import tempfile
import shutil
import unittest

from pclengine.core import acts, clock, research, war
from pclengine.modding import loader
from pclengine.store import save
from pclengine.core.state import Game, scaled_price

ALL_PRICE_FUNCTIONS = [
    ("unit", lambda g: g.unit_price("miner")),
    ("stepper", lambda g: g.stepper_cost),
    ("scanner", lambda g: g.scanner_cost),
    ("design win", lambda g: g.design_win_cost),
    ("war unit", lambda g: war.unit_price(g, "guards")),
    ("lab", lambda g: research.lab_price(g)),
]


class TestPrices(unittest.TestCase):
    def test_scaled_price_never_returns_nan(self):
        """`inf * 0` is nan, which is not a price and crashes the HUD."""
        for base in (0.0, 1.0, 1e300, float("inf"), float("nan")):
            for scale in (0.0, 1e-9, 1.0, 1e9):
                with self.subTest(base=base, scale=scale):
                    value = scaled_price(base, scale)
                    self.assertFalse(value != value, "produced a nan")

    def test_zero_multiplier_means_free(self):
        g = Game()
        g.hw_scale = 0.0
        for name, price_of in ALL_PRICE_FUNCTIONS:
            with self.subTest(price=name):
                self.assertEqual(price_of(g), 0.0)

    def test_no_nan_across_the_overflow_window(self):
        """exp() can succeed while the multiply that follows overflows."""
        for owned in (1e9, 7.07e10, 7.074e10, 7.08e10, 1e11, 1e300):
            for scale in (0.0, 1.0):
                g = Game()
                g.miners = owned
                g.hw_scale = scale
                with self.subTest(owned=owned, scale=scale):
                    value = g.unit_price("miner")
                    self.assertFalse(value != value, "produced a nan")

    def test_buying_never_goes_negative(self):
        g = Game()
        g.act = 2
        g.unsold = 1000.0
        g.buy_units("miner", 10 ** 9)
        self.assertGreaterEqual(g.unsold, 0.0)

    def test_free_hardware_still_buys(self):
        g = Game()
        g.act = 2
        g.unsold = 10.0
        g.hw_scale = 0.0
        g.researched.update({"metrology", "computing", "autonomy"})
        self.assertGreater(g.buy_units("miner", 5000), 0)


class TestTick(unittest.TestCase):
    def test_every_act_ticks_without_raising(self):
        for act in acts.ALL:
            g = Game()
            g.act = act.number
            with self.subTest(act=act.number):
                for _ in range(20):
                    g.tick(0.1)

    def test_elapsed_tracks_dt(self):
        g = Game()
        for _ in range(100):
            g.tick(0.05)
        self.assertAlmostEqual(g.elapsed, 5.0, places=6)

    def test_mode_clock_scales_time(self):
        g = Game()
        g.time_scale = 0.4
        g.tick(1.0)
        self.assertAlmostEqual(g.elapsed, 0.4, places=6)

    def test_hand_etching_consumes_wafers(self):
        g = Game()
        before = g.wafers
        made = g.make_chip(5)
        self.assertGreater(made, 0)
        self.assertEqual(g.wafers, before - 5)


class TestPacer(unittest.TestCase):
    """Lag must widen the step, never drop the time."""

    def _elapsed(self, frames):
        g = Game()
        pacer = clock.Pacer()
        for frame in frames:
            pacer.frame(g, frame)
        return g.elapsed

    def test_smooth_and_chunky_agree(self):
        smooth = self._elapsed([0.05] * 400)
        chunky = self._elapsed([1.0] * 20)
        self.assertAlmostEqual(smooth, 20.0, places=3)
        self.assertAlmostEqual(chunky, 20.0, places=3)

    def test_a_long_freeze_is_covered_not_dropped(self):
        self.assertAlmostEqual(self._elapsed([120.0]), 120.0, places=3)

    def test_steps_are_capped_but_time_is_not(self):
        g = Game()
        taken = clock.advance(g, 600.0)
        self.assertLessEqual(taken, clock.MAX_STEPS)
        self.assertAlmostEqual(g.elapsed, 600.0, places=3)


class TestSave(unittest.TestCase):
    def setUp(self):
        loader.reset()
        handle, self.path = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        os.remove(self.path)

    def tearDown(self):
        for path in (self.path, self.path + ".bak"):
            if os.path.exists(path):
                os.remove(path)

    def test_round_trip_is_lossless(self):
        g = Game()
        for _ in range(200):
            g.tick(1.0)
        g.forces["guards"] = 7
        g.researched.add("metrology")
        g.fw["survey"] = 2
        g.completed.add("improved_steppers")
        self.assertTrue(save.save(g, self.path))
        loaded, unknown = save.load(self.path)
        self.assertEqual(unknown, [])
        for field in vars(g):
            # Underscore names are scratch space and deliberately not
            # written out; see the note in save.to_dict.
            if field in save.SKIP_FIELDS or field.startswith("_"):
                continue          # rebuilt on load, not written out
            with self.subTest(field=field):
                self.assertEqual(getattr(g, field), getattr(loaded, field))
        # The generator is not saved, but the seed is, so a reloaded run
        # keeps rolling the numbers it would have.
        self.assertEqual(g.seed, loaded.seed)

    def test_corrupt_file_is_not_fatal(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        loaded, unknown = save.load(self.path)
        self.assertIsNone(loaded)

    def test_unknown_fields_are_reported_not_dropped_silently(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"act": 2, "from_another_version": 1}, handle)
        loaded, unknown = save.load(self.path)
        self.assertEqual(loaded.act, 2)
        self.assertIn("from_another_version", unknown)

    def test_a_save_from_a_build_with_more_acts_still_loads(self):
        """Acts were removed; a run parked on one must land somewhere real."""
        from pclengine.core import acts
        data = save.to_dict(Game())
        data["act"] = acts.last_number() + 5
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        loaded, _ = save.load(self.path)
        self.assertEqual(loaded.act, acts.last_number())
        for _ in range(20):
            loaded.tick(0.1)

    def test_act_target_is_never_none(self):
        """The finish check multiplies it, so None is a crash."""
        g = Game()
        for act in range(-2, 20):
            g.act = act
            with self.subTest(act=act):
                self.assertIsNotNone(g.act_target)

    def test_infinite_batch_survives(self):
        g = Game()
        g.batch = float("inf")
        save.save(g, self.path)
        loaded, _ = save.load(self.path)
        self.assertEqual(loaded.batch, float("inf"))


if __name__ == "__main__":
    unittest.main()


class TestSaveFormat(unittest.TestCase):
    """Saving, in whatever format is installed.

    The format is a registry: JSON is built in and always works, and a mod
    may register another and claim the default. These tests exercise the
    registry rather than any one format, so they keep working whichever is
    installed.
    """

    def setUp(self):
        loader.load(loader.discover())
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def path(self, name):
        return os.path.join(self.dir, name)

    def furnished(self):
        g = Game(seed=7)
        g.chips, g.funds, g.act = 1.5e30, 940.25, 3
        g.completed.update({"verilog_haiku", "entropy"})
        g.researched.add("metrology")
        g.messages.append("a line of log")
        g.act_log.append((3, 120.0))
        g.batch = float("inf")
        return g

    def test_a_save_round_trips_field_for_field(self):
        g = self.furnished()
        path = self.path("run" + os.path.splitext(save.default_path())[1])
        self.assertTrue(save.save(g, path))
        back, unknown = save.load(path)
        self.assertEqual(unknown, [])
        for field in vars(g):
            if field in save.SKIP_FIELDS or field.startswith("_"):
                continue
            with self.subTest(field=field):
                self.assertEqual(getattr(back, field), getattr(g, field))

    def test_the_header_reads_without_loading_the_game(self):
        g = self.furnished()
        path = self.path("run.json")
        save.save(g, path)
        header = save.describe(path)
        self.assertEqual(header["act"], g.act)
        self.assertEqual(header["game"], "FOUNDRY")

    def test_a_damaged_file_is_caught_rather_than_half_loaded(self):
        g = self.furnished()
        path = self.path("run.json")
        save.save(g, path)
        with open(path, "rb") as fh:
            blob = bytearray(fh.read())
        del blob[len(blob) // 2:]
        with open(path, "wb") as fh:
            fh.write(blob)
        self.assertIsNone(save.read_raw(path))
        loaded, _unknown = save.load(path)
        self.assertIsNone(loaded)

    def test_json_saves_load_whatever_else_is_installed(self):
        """People have saves from before any format mod existed."""
        g = self.furnished()
        path = self.path("old.json")
        self.assertTrue(save.save(g, path, as_json=True))
        with open(path, encoding="utf-8") as fh:
            self.assertIsInstance(json.load(fh), dict)
        back, _unknown = save.load(path)
        self.assertEqual(back.act, g.act)
        self.assertEqual(back.completed, g.completed)

    def test_the_format_follows_the_file_not_the_name(self):
        g = self.furnished()
        odd = self.path("named-wrong.dat")
        save.save(g, odd, as_json=True)
        back, _unknown = save.load(odd)
        self.assertIsNotNone(back)
        self.assertEqual(back.act, g.act)

    def test_a_save_can_be_rewritten_as_plain_json(self):
        g = self.furnished()
        source, plain = self.path("run.sav"), self.path("run.json")
        save.save(g, source)
        self.assertTrue(save.convert(source, plain, as_json=True))
        with open(plain, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["act"], g.act)

    def test_json_is_always_available_as_a_fallback(self):
        from pclengine.store import codecs
        self.assertIn(codecs.JSON, codecs.CODECS)
        loader.load([], with_base=False)
        self.assertEqual(codecs.default().name, "json")
        loader.reset()
