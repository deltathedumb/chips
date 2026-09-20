"""The emergency loan, and the softlock detector behind it.

A real run was lost to this: Act II prices drones in finished chips, the
whole stock went on miners, and with no solar array the miners made nothing
to buy an array with. The clock ran and every number stood still.

These assert the two halves separately -- that the detector does not cry
wolf at a game that is merely slow, and that the loan actually restarts a
line rather than only saying it will.
"""

import unittest

from pclengine.core import rescue, research
from pclengine.core.state import Game
from pclengine.modding import loader
from pclengine.ui import actions


class TestSoftlock(unittest.TestCase):

    def setUp(self):
        loader.load(loader.discover())

    def stranded(self):
        """A fab with every drone it could buy and nothing to run them on."""
        g = Game(seed=5)
        g.act = 2
        for tech in research.TREE:
            g.researched.add(tech.id)
        g.unsold, g.funds, g.chips = 2.0e7, 0.0, 5.0e7
        g.solar = 0.0
        g.buy_units("miner", 10_000_000)
        return g

    def test_a_working_game_is_never_softlocked(self):
        g = Game(seed=1)
        for _ in range(int(rescue.PATIENCE) + 60):
            g.tick(1.0)
        self.assertFalse(g.softlocked)
        self.assertIsNone(g.overlay)

    def test_a_dead_line_opens_the_popup(self):
        g = self.stranded()
        for _ in range(int(rescue.PATIENCE) + 30):
            g.tick(1.0)
        self.assertTrue(g.softlocked)
        self.assertEqual(g.overlay, "loan")

    def test_the_popup_waits_before_it_fires(self):
        """A pause is not a softlock. Two minutes of nothing is."""
        g = self.stranded()
        for _ in range(int(rescue.PATIENCE) - 30):
            g.tick(1.0)
        self.assertIsNone(g.overlay)

    def test_only_enter_signs_for_it(self):
        g = self.stranded()
        for _ in range(int(rescue.PATIENCE) + 30):
            g.tick(1.0)
        for key in ("a", "w", "TAB", "s", "5"):
            actions.handle_key(key, g)
            self.assertEqual(g.overlay, "loan", f"{key} dismissed the loan")
            self.assertEqual(g.debt, 0.0, f"{key} signed for a loan")
        actions.handle_key("ESC", g)
        self.assertIsNone(g.overlay)
        self.assertEqual(g.debt, 0.0)

    def small(self):
        """A modest fab in the same corner: stalled, but within 100k of out.

        The loan is a fixed sum, so what it can rescue is a question of
        scale. This is the size it is meant for.
        """
        g = Game(seed=6)
        g.act = 2
        for tech in research.TREE:
            g.researched.add(tech.id)
        g.unsold, g.funds, g.chips = 0.0, 0.0, 1.0e6
        g.miners, g.pullers, g.foundries, g.solar = 400.0, 400.0, 1.0, 0.0
        return g

    def test_the_loan_pays_out_what_it_says(self):
        g = self.stranded()
        for _ in range(int(rescue.PATIENCE) + 30):
            g.tick(1.0)
        from base import rescue as bailout
        held = g.unsold
        actions.handle_key("ENTER", g)
        self.assertIsNone(g.overlay)
        self.assertAlmostEqual(g.unsold - held, bailout.ACT_TWO_LOAN,
                               places=2)
        self.assertAlmostEqual(g.debt,
                               bailout.ACT_TWO_LOAN * bailout.INTEREST,
                               places=2)

    def test_taking_the_loan_restarts_a_fab_its_size(self):
        g = self.small()
        for _ in range(int(rescue.PATIENCE) + 30):
            g.tick(1.0)
        self.assertEqual(g.overlay, "loan")
        before = g.chips
        actions.handle_key("ENTER", g)
        g.buy_units("solar", 1_000)
        for _ in range(600):
            g.tick(1.0)
        self.assertGreater(g.power_ratio, 0.0)
        self.assertGreater(g.chips, before, "the loan did not restart it")

    def test_the_debt_is_repaid_out_of_production(self):
        g = self.small()
        for _ in range(int(rescue.PATIENCE) + 30):
            g.tick(1.0)
        actions.handle_key("ENTER", g)
        owed = g.debt
        g.buy_units("solar", 1_000)
        for _ in range(600):
            g.tick(1.0)
        self.assertLess(g.debt, owed, "the bank was never repaid")

    def test_it_can_be_taken_again_while_still_stuck(self):
        """One fixed sum will not dig out every hole, so it is not one-shot."""
        g = self.stranded()
        for _ in range(int(rescue.PATIENCE) + 30):
            g.tick(1.0)
        actions.handle_key("ENTER", g)
        first = g.debt
        g.buy_units("foundry", 1)          # spends it, still not enough
        for _ in range(int(rescue.PATIENCE) + 30):
            g.tick(1.0)
        self.assertEqual(g.overlay, "loan", "the bank never came back")
        actions.handle_key("ENTER", g)
        self.assertGreater(g.debt, first, "a second loan added no debt")

    def test_no_offer_when_they_can_already_afford_the_fix(self):
        """Standing still by choice is not a softlock, and gets no bank."""
        g = self.stranded()
        g.unsold = 1e18
        for _ in range(int(rescue.PATIENCE) + 30):
            g.tick(1.0)
        self.assertFalse(g.softlocked)
        self.assertIsNone(g.overlay)

    def test_research_alone_does_not_count_as_progress(self):
        """The bug that would make the whole check useless.

        Research keeps climbing in a fab with no power. If it counted as
        movement the stopwatch would never fire on the one state it exists
        to catch.
        """
        g = self.stranded()
        g.labs = 200.0
        start = g.research
        for _ in range(int(rescue.PATIENCE) + 30):
            g.tick(1.0)
        self.assertGreater(g.research, start, "research should still tick")
        self.assertEqual(g.overlay, "loan")


class TestOverlayReachesTheBrowser(unittest.TestCase):
    """An overlay the web front end cannot see is a keyboard black hole.

    The overlay layer is exclusive: while one is open the server consumes
    every key and returns nothing to the panels underneath. The browser
    drew no popup, so the loan opened itself, ate everything the player
    pressed, and the game looked broken.
    """

    def setUp(self):
        loader.load(loader.discover())

    def stranded(self):
        g = Game(seed=5)
        g.act = 2
        for tech in research.TREE:
            g.researched.add(tech.id)
        g.unsold, g.funds, g.chips = 2.0e7, 0.0, 5.0e7
        g.solar = 0.0
        g.buy_units("miner", 10_000_000)
        return g

    def test_a_quiet_game_reports_no_overlay(self):
        from mods.web import view
        self.assertIsNone(view.snapshot(Game(seed=1))["overlay"])

    def test_the_loan_reaches_the_snapshot(self):
        from mods.web import view
        g = self.stranded()
        for _ in range(int(rescue.PATIENCE) + 30):
            g.tick(1.0)
        info = view.snapshot(g)["overlay"]
        self.assertIsNotNone(info, "the browser was told nothing")
        self.assertEqual(info["kind"], "loan")
        self.assertTrue(info["terms"])
        self.assertTrue(info["accept"] and info["dismiss"],
                        "no way to answer it")

    def test_every_overlay_is_at_least_dismissible(self):
        """Including ones the browser has its own screen for."""
        from mods.web import view
        g = Game(seed=1)
        g.overlay = "tech"
        info = view.snapshot(g)["overlay"]
        self.assertIsNotNone(info)
        self.assertTrue(info["dismiss"])


if __name__ == "__main__":
    unittest.main()
