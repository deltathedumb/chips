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

    def test_taking_the_loan_restarts_the_line(self):
        g = self.stranded()
        for _ in range(int(rescue.PATIENCE) + 30):
            g.tick(1.0)
        before = g.chips
        actions.handle_key("ENTER", g)
        self.assertGreater(g.debt, 0.0)
        self.assertIsNone(g.overlay)
        # Spend it the way the popup says to: the empty links, then power.
        for kind, count in (("puller", 2_000), ("foundry", 20),
                            ("solar", 10_000_000)):
            g.buy_units(kind, count)
        for _ in range(600):
            g.tick(1.0)
        self.assertGreater(g.chips, before, "the loan did not restart it")

    def test_the_debt_is_repaid_out_of_production(self):
        g = self.stranded()
        for _ in range(int(rescue.PATIENCE) + 30):
            g.tick(1.0)
        actions.handle_key("ENTER", g)
        owed = g.debt
        for kind, count in (("puller", 2_000), ("foundry", 20),
                            ("solar", 10_000_000)):
            g.buy_units(kind, count)
        for _ in range(600):
            g.tick(1.0)
        self.assertLess(g.debt, owed, "the bank was never repaid")

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


if __name__ == "__main__":
    unittest.main()
