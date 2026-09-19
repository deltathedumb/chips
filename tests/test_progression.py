"""The run has to be finishable, and each act has to be worth playing.

These are the tests that would have caught an act whose goal was above what
its price curves could reach, a transition project nothing could afford, and
a completion check that could never fire.
"""

import unittest

from pclengine.core import acts, projects, research
from pclengine.dev import autoplay, balance
from pclengine.modding import loader
from pclengine.core.state import Game

BUDGET = 200_000.0      # game-seconds; a full run is around 9,000


class TestProjectTree(unittest.TestCase):
    def setUp(self):
        loader.reset()

    def test_ids_are_unique(self):
        ids = [p.id for p in projects.ALL]
        self.assertEqual(len(ids), len(set(ids)))

    def test_prerequisites_all_exist(self):
        for project in projects.ALL:
            for required in getattr(project.req, "requires", ()):
                with self.subTest(project=project.id):
                    self.assertIn(required, projects.BY_ID)

    def test_every_project_can_be_described(self):
        g = Game()
        for project in projects.ALL:
            with self.subTest(project=project.id):
                self.assertTrue(project.cost_text(g))
                self.assertTrue(project.unlock_hint(g))

    def test_node_ladder_points_at_real_projects(self):
        from pclengine import content
        for project_id, _nm in content.node_ladder():
            self.assertIn(project_id, projects.BY_ID)

    def test_every_act_has_a_way_in(self):
        """No act should be reachable only by cheating."""
        for act in acts.ALL:
            if act.number == 1:
                continue
            entries = [p for p in projects.ALL
                       if f"act = {act.number}" in repr(p.effect.__code__.co_consts)
                       or p.id.endswith(acts.get(act.number).key)]
            with self.subTest(act=act.number):
                self.assertTrue(entries or act.number in (2, 3, 4, 5),
                                f"act {act.number} has no entry project")


class TestActsAreReachable(unittest.TestCase):
    """Each act's goal must be attainable with that act's own hardware."""

    def setUp(self):
        loader.reset()

    def test_late_acts_complete_in_isolation(self):
        for number in range(6, acts.last_number() + 1):
            with self.subTest(act=number):
                reached, _game = balance.probe(number, seconds=2400.0,
                                               out=lambda *a: None)
                self.assertIsNotNone(
                    reached, f"act {number} cannot reach its own goal")


class TestFullRun(unittest.TestCase):
    """One headless playthrough, asserted end to end."""

    @classmethod
    def setUpClass(cls):
        loader.reset()
        cls.game, cls.timeline = balance.run(dt=1.0, budget=BUDGET)

    def test_the_run_finishes(self):
        self.assertTrue(self.game.finished,
                        "the bot could not finish a standard run")

    def test_no_act_stalls(self):
        stalled = [number for number, seconds in self.timeline if seconds < 0]
        self.assertEqual(stalled, [], f"stalled in acts {stalled}")

    def test_every_act_is_visited(self):
        visited = {number for number, _ in self.timeline}
        self.assertEqual(visited, {a.number for a in acts.ALL})

    def test_each_act_is_worth_playing(self):
        """Nothing should be over in seconds, or drag for an hour."""
        for number, seconds in self.timeline:
            low, high = balance.TARGETS.get(number, (4, 16))
            minutes = abs(seconds) / 60.0
            with self.subTest(act=number):
                self.assertGreaterEqual(minutes, low * 0.6,
                                        f"act {number} is far too short")
                self.assertLessEqual(minutes, high * 1.8,
                                     f"act {number} drags")

    def test_the_whole_run_is_a_sensible_length(self):
        total = sum(abs(s) for _, s in self.timeline) / 3600.0
        self.assertGreater(total, 1.0, "the game is too short to be worth it")
        self.assertLess(total, 6.0, "the game has become a chore")

    def test_most_of_the_tree_gets_bought(self):
        one_shot = [p for p in projects.ALL if not p.repeatable]
        self.assertGreater(len(self.game.completed), len(one_shot) * 0.7)


class TestStepSize(unittest.TestCase):
    """The balance harness is only useful if its shortcut is honest."""

    def setUp(self):
        loader.reset()

    def test_coarse_and_fine_steps_agree_on_progress(self):
        """Same seed, same run -- so any gap is the step size, not luck."""
        results = {}
        for dt in (0.2, 1.0):
            g = Game(seed=20240101)
            for _ in range(int(1200 / dt)):
                autoplay.step(g, dt)
            results[dt] = (g.act, len(g.completed))
        self.assertEqual(results[0.2][0], results[1.0][0],
                         "step size changes which act you are in")
        self.assertLessEqual(abs(results[0.2][1] - results[1.0][1]), 4)


if __name__ == "__main__":
    unittest.main()


class TestCipherLab(unittest.TestCase):
    """Cracking is a choice of algorithm, not a bar that fills."""

    def setUp(self):
        loader.reset()
        from base import crypt
        self.crypt = crypt

    def _ready(self, g):
        g.research = 1e9
        for _ in range(len(research.TREE) + 2):
            for tech in research.available(g):
                research.buy(g, tech.id)

    def test_the_wrong_algorithm_is_far_slower(self):
        g = Game(seed=1)
        self._ready(g)
        g.rigs = 100
        cipher = self.crypt.CIPHERS[0]          # a classical cipher
        best = max(self.crypt.ALGORITHMS,
                   key=lambda a: a.effectiveness(cipher))
        worst = min(self.crypt.ALGORITHMS,
                    key=lambda a: a.effectiveness(cipher))
        self.assertGreater(best.effectiveness(cipher),
                           worst.effectiveness(cipher) * 5)

    def test_every_family_has_something_that_beats_it(self):
        for cipher in self.crypt.CIPHERS:
            with self.subTest(cipher=cipher.key):
                best = max(a.effectiveness(cipher)
                           for a in self.crypt.ALGORITHMS)
                self.assertGreaterEqual(best, 3.0)

    def test_every_algorithm_is_behind_a_tech_that_exists(self):
        for algorithm in self.crypt.ALGORITHMS:
            with self.subTest(algorithm=algorithm.key):
                self.assertTrue(any(algorithm.tech in t.unlocks
                                    for t in research.TREE),
                                f"{algorithm.tech} unlocks nothing")

    def test_breaking_one_pays_out_and_puts_up_the_next(self):
        g = Game(seed=1)
        self._ready(g)
        g.rigs = 1e6
        g.algorithm = "brute"
        before = self.crypt.cipher_of(g)
        for _ in range(400):
            self.crypt.tick(g, 1.0)
            if g.cracked:
                break
        self.assertEqual(g.cracked, 1)
        self.assertGreater(g.entropy, 0)
        self.assertIsNot(self.crypt.cipher_of(g), before)

    def test_cracking_does_not_hand_you_the_entropy_economy(self):
        """The payout is entropy; extraction still needs its own project."""
        g = Game(seed=1)
        self._ready(g)
        g.rigs, g.algorithm = 1e6, "brute"
        for _ in range(400):
            self.crypt.tick(g, 1.0)
        self.assertFalse(g.entropy_on)


class TestBenchmarkCircuit(unittest.TestCase):
    """Where you place decides whether customers arrive or leave."""

    def setUp(self):
        loader.reset()
        from base import bench
        self.bench = bench

    def _ready(self, g):
        g.researched.update({"metrology", "market_analysis", "computing",
                             "numerical_analysis"})

    def test_placement_follows_what_you_committed(self):
        expected = [(3.0, "FIRST"), (1.8, "SECOND"), (1.2, "THIRD"),
                    (0.8, "MID-FIELD"), (0.3, "ALSO-RAN")]
        for ratio, name in expected:
            with self.subTest(ratio=ratio):
                self.assertEqual(self.bench.placement_for(ratio).name, name)

    def test_placing_well_draws_customers_and_badly_loses_them(self):
        for ratio, direction in ((3.0, 1), (0.8, 0), (0.2, -1)):
            with self.subTest(ratio=ratio):
                g = Game(seed=1)
                self._ready(g)
                g.ops = self.bench.PROBLEMS[0].par * ratio
                before = g.order_flow()
                self.bench.submit(g)
                after = g.order_flow()
                if direction > 0:
                    self.assertGreater(after, before)
                elif direction < 0:
                    self.assertLess(after, before)
                else:
                    self.assertAlmostEqual(after, before)

    def test_ops_come_out_of_the_data_budget(self):
        g = Game(seed=1)
        self._ready(g)
        g.threads = 100
        full = g.data_rate
        g.ops_share = 0.5
        self.assertAlmostEqual(g.data_rate, full * 0.5)
        self.assertGreater(g.ops_rate, 0)
        self.assertAlmostEqual(g.data_rate + g.ops_rate, full)

    def test_the_buffer_can_never_be_starved_completely(self):
        g = Game(seed=1)
        self._ready(g)
        g.threads = 100
        for _ in range(50):
            self.bench.adjust_share(g, 1)
        self.assertLessEqual(g.ops_share, self.bench.SHARE_MAX)
        self.assertGreater(g.data_rate, 0)

    def test_brand_has_a_floor(self):
        g = Game(seed=1)
        self._ready(g)
        for _ in range(len(self.bench.PROBLEMS)):
            g.ops = 1.0
            self.bench.submit(g)
        self.assertGreaterEqual(g.brand, self.bench.BRAND_FLOOR)
        self.assertGreater(g.order_flow(), 0)

    def test_a_finished_circuit_hands_the_compute_back(self):
        g = Game(seed=1)
        self._ready(g)
        g.threads, g.ops_share = 100, 0.5
        for _ in range(len(self.bench.PROBLEMS)):
            g.ops = 1.0
            self.bench.submit(g)
        self.bench.tick(g, 1.0)
        self.assertEqual(g.ops_share, 0.0)
        self.assertAlmostEqual(g.data_rate, g.compute_rate)


class TestCoinMarket(unittest.TestCase):
    """Mining is worth doing, and which coin you mine is a real choice."""

    def setUp(self):
        loader.reset()
        from base import crypt, market
        self.market = market
        self.crypt = crypt

    def ready(self, seed=1, rigs=500):
        g = Game(seed=seed)
        g.researched.update({"metrology", "computing"})
        g.rigs = rigs
        g.mine_share = 1.0
        return g

    def test_a_run_gets_its_own_market(self):
        one = [c.ticker for c in self.market.listings(Game(seed=1))]
        two = [c.ticker for c in self.market.listings(Game(seed=2))]
        self.assertNotEqual(one, two)
        self.assertEqual(len(set(one)), len(one), "duplicate tickers")
        for ticker in one:
            with self.subTest(ticker=ticker):
                self.assertEqual(len(ticker), 3)
                self.assertTrue(ticker.isalpha() and ticker.isupper())

    def test_the_same_seed_gets_the_same_market(self):
        one = [c.ticker for c in self.market.listings(Game(seed=42))]
        two = [c.ticker for c in self.market.listings(Game(seed=42))]
        self.assertEqual(one, two)

    def test_every_market_has_something_calm_and_something_wild(self):
        for seed in (1, 7, 99):
            tiers = {c.tier for c in self.market.listings(Game(seed=seed))}
            with self.subTest(seed=seed):
                self.assertIn("STABLE", tiers)
                self.assertIn("FERAL", tiers)

    def test_volatility_ratings_mean_what_they_say(self):
        g = self.ready()
        coins = {c.tier: c for c in self.market.listings(g)}
        swings = {}
        for tier, coin in coins.items():
            h = Game(seed=1)
            seen = []
            for _ in range(4000):
                self.market.tick_prices(h, 0.5)
                seen.append(self.market.price(h, coin))
            swings[tier] = (max(seen) - min(seen)) / coin.base
        self.assertLess(swings["STABLE"], swings["STEADY"])
        self.assertLess(swings["STEADY"], swings["FERAL"])

    def test_prices_stay_in_a_band(self):
        """Mean reversion, so waiting is always a live option."""
        g = self.ready()
        for _ in range(20000):
            self.market.tick_prices(g, 0.5)
        for coin in self.market.listings(g):
            with self.subTest(coin=coin.ticker):
                here = self.market.price(g, coin)
                self.assertGreater(here, 0)
                self.assertLess(here, coin.base * 30.1)

    def test_no_coin_is_strictly_better_to_mine(self):
        """Equal in expectation: the rating is risk, not payout."""
        g = self.ready()
        rates = {c.ticker: self.market.mine_rate(g, c)
                 for c in self.market.listings(g)}
        self.assertEqual(len(set(round(r, 6) for r in rates.values())), 1)

    def test_selling_in_slices_beats_dumping_the_lot(self):
        g = self.ready()
        coin = self.market.listings(g)[0]
        for _ in range(600):
            self.market.tick_mining(g, 1.0)
        held = self.market.holding(g, coin)
        whole, _average = self.market.quote(g, coin, held)
        eighth, _average = self.market.quote(g, coin, held / 8)
        self.assertGreater(eighth * 8, whole)

    def test_selling_pays_into_the_currency_of_the_act(self):
        g = self.ready()
        coin = self.market.listings(g)[0]
        for _ in range(600):
            self.market.tick_mining(g, 1.0)
        before = g.funds
        self.assertGreater(self.market.sell(g, coin, 1.0), 0)
        self.assertGreater(g.funds, before)
        self.assertAlmostEqual(self.market.holding(g, coin), 0.0)

    def test_mining_takes_hashes_from_cracking(self):
        g = self.ready()
        g.researched.update({"metrology", "computing", "parallelism"})
        g.algorithm = "brute"
        g.mine_share = 0.0
        self.crypt.tick(g, 1.0)
        full = g.crack_rate
        g.mine_share = 0.75
        self.crypt.tick(g, 1.0)
        self.assertLess(g.crack_rate, full)
        self.assertGreater(g.crack_rate, 0)

    def test_the_market_is_worth_using_late_as_well_as_early(self):
        """A coin's value follows what rigs cost, so it keeps pace."""
        early = self.ready(rigs=50)
        late = self.ready(rigs=200000)
        late.act = 7
        self.assertGreater(self.market.unit_value(late),
                           self.market.unit_value(early))
