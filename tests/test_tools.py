"""Input, mods, developer tools and error handling."""

import os
import tempfile
import unittest

from pclengine import errors
from pclengine.content import firmware
from pclengine.core import projects, research, war
from pclengine.core.state import Game
from pclengine.dev import console, tools
from pclengine.modding import loader
from pclengine.store import runconfig
from pclengine.ui import actions, panels

EVERY_KEY = list(" wasmtbcurlhjfdgxq?[]0-+") + [
    "UP", "DOWN", "LEFT", "RIGHT", "ENTER", "ESC", "TAB", "BACKSPACE",
    "HOME", "END", "S", "1", "2", "8",
]


class TestKeyHandling(unittest.TestCase):
    def setUp(self):
        loader.reset()

    def test_no_key_raises_in_any_act_or_view(self):
        from pclengine.core import acts
        for act in acts.ALL:
            for panel_view in ("ops", "war", "research"):
                g = Game()
                g.act = act.number
                g.panel_view = panel_view
                g.funds = 1e9
                g.unsold = 1e30
                g.bandwidth = 50
                g.firmware = 10
                for key in EVERY_KEY:
                    with self.subTest(act=act.number, view=panel_view, key=key):
                        actions.handle_key(key, g)

    def test_quit_and_menu_are_reported(self):
        g = Game()
        self.assertEqual(actions.handle_key("q", g), "quit")
        self.assertEqual(actions.handle_key("ESC", g), "menu")

    def test_tab_cycles_panels(self):
        g = Game()
        seen = set()
        for _ in range(len(panels.VIEWS) + 1):
            actions.handle_key("TAB", g)
            seen.add(g.panel_view)
        self.assertEqual(seen, {v.key for v in panels.visible(g)})

    def test_a_hidden_tab_appears_once_it_has_something_to_show(self):
        """A conditional tab stays away until its tech is in, then renders."""
        g = Game()
        hidden = [v for v in panels.VIEWS if not v.visible(g)]
        self.assertTrue(hidden, "no tab is conditional any more")
        g.research = 1e9
        for _ in range(len(research.TREE) + 2):
            for tech in research.available(g):
                research.buy(g, tech.id)
        for view in hidden:
            with self.subTest(tab=view.key):
                self.assertTrue(view.visible(g))
                self.assertTrue(view.build(g))

    def test_burst_respects_its_cooldown(self):
        g = Game()
        g.researched.update({"metrology", "computing", "parallelism"})
        self.assertGreater(g.fire_burst(), 0)
        self.assertEqual(g.fire_burst(), 0.0)

    def test_firmware_cannot_be_overspent(self):
        g = Game()
        g.firmware = 2
        for key, _label, _blurb in firmware():
            g.adjust_firmware(key, 1)
        self.assertLessEqual(g.firmware_allocated(), g.firmware)


class TestDeveloperActions(unittest.TestCase):
    def setUp(self):
        loader.reset()

    def test_every_action_runs(self):
        for action in tools.ACTIONS:
            g = Game()
            g.unsold = 1e20
            with self.subTest(action=action.key):
                message, lines = tools.run(g, action.key, action.default)
                self.assertTrue(message)

    def test_values_arrive_as_text_and_are_coerced(self):
        """Front ends hand over strings; numeric actions must cope."""
        g = Game()
        message, _ = tools.run(g, "chips", "1000000000000.0")
        self.assertEqual(g.chips, 1e12)
        self.assertNotIn("failed", message)

    def test_a_bad_value_is_reported_not_raised(self):
        g = Game()
        message, _ = tools.run(g, "chips", "banana")
        self.assertIn("needs", message)

    def test_an_action_that_raises_is_caught(self):
        g = Game()
        message, _ = tools.run(g, "no-such-action", None)
        self.assertIn("no such", message)

    def test_run_settings_round_trip(self):
        from pclengine.core.state import Game
        setup = runconfig.Setup(time_scale=0.5, cost_scale=2.0, hw_scale=0.1)
        g = setup.apply(Game())
        self.assertEqual(runconfig.from_game(g).as_dict(), setup.as_dict())
        self.assertIn("clock", runconfig.label_of(g))

    def test_knobs_snap_onto_normal(self):
        knob = runconfig.BY_ATTR["time_scale"]
        self.assertEqual(knob.nudge(0.9, 1), 1.0)
        self.assertEqual(knob.nudge(1.2, -1), 1.0)
        self.assertLessEqual(knob.nudge(knob.high, 1), knob.high)
        self.assertGreaterEqual(knob.nudge(knob.low, -1), knob.low)

    def test_cost_multipliers_apply_everywhere(self):
        g = Game()
        tools.run(g, "cost", "0")
        self.assertEqual(g.cost_scale, 0.0)
        self.assertEqual(g.hw_scale, 0.0)
        self.assertEqual(g.unit_price("miner"), 0.0)
        self.assertEqual(war.unit_price(g, "guards"), 0.0)
        self.assertEqual(research.lab_price(g), 0.0)


class TestWarfare(unittest.TestCase):
    """Warfare has to be able to end a run, and to be survivable."""

    def setUp(self):
        loader.reset()

    def test_ignoring_a_threat_loses_the_run(self):
        g = Game()
        g.act = 2
        g.pressure["insurgency"] = 5e5
        for _ in range(6000):
            g.tick(0.1)
            if g.defeated:
                break
        self.assertTrue(g.defeated)
        self.assertTrue(g.finished)

    def test_answering_a_threat_holds_it(self):
        g = Game()
        g.act = 2
        g.pressure["insurgency"] = 5e5
        g.forces["fighters"] = 10 ** 9
        for _ in range(600):
            g.tick(0.1)
        self.assertFalse(g.defeated)
        self.assertGreater(g.integrity, 0.9)

    def test_you_are_warned_before_you_lose(self):
        g = Game()
        g.act = 2
        g.pressure["insurgency"] = 5e5
        for _ in range(6000):
            g.tick(0.1)
            if g.defeated:
                break
        warnings = [m for m in g.messages if "Integrity" in m]
        self.assertGreaterEqual(len(warnings), 3)

    def test_losing_takes_long_enough_to_react(self):
        g = Game()
        g.act = 2
        g.pressure["insurgency"] = 5e5
        for _ in range(6000):
            g.tick(0.1)
            if g.defeated:
                break
        self.assertGreater(g.elapsed, 120,
                           "defeat should take minutes, not seconds")

    def test_the_clock_speed_does_not_change_how_deadly_war_is(self):
        """A faster run should be shorter, not disproportionately deadlier."""
        times = []
        for clock in (0.5, 1.0, 3.0):
            g = Game()
            g.act = 2
            g.time_scale = clock
            g.pressure["insurgency"] = 5e5
            real = 0.0
            while not g.defeated and real < 3000:
                g.tick(0.1)
                real += 0.1
            times.append(real)
        self.assertTrue(g.defeated)
        spread = max(times) / max(min(times), 1e-9)
        self.assertLess(spread, 1.25,
                        f"defeat took {times} real seconds at x0.5/x1/x3")

    def test_integrity_shows_on_the_main_hud_once_it_slips(self):
        """You must not lose a run to something hidden behind TAB."""
        from pclengine.ui import panels
        g = Game()
        g.act = 2
        g.integrity = 0.5
        labels = [row["label"] for panel in panels.left(g)
                  for row in panel["rows"]]
        self.assertIn("INTEGRITY", labels)

    def test_act_one_defenders_are_paid_in_money(self):
        g = Game()
        g.funds = 10_000.0
        g.unsold = 0.0
        self.assertGreater(war.buy_unit(g, "guards", 5), 0)
        self.assertLess(g.funds, 10_000.0)


class TestDials(unittest.TestCase):
    """Acts IV, VII and X each have a knob to manage."""

    def test_every_dial_belongs_to_its_act(self):
        from pclengine.core import acts
        for spec in acts.DIALS:
            g = Game()
            g.act = spec.act
            self.assertTrue(acts.adjust_dial(g, spec.key, 3))
            self.assertEqual(acts.dial(g, spec.key), 3)
            g.act = spec.act + 1
            self.assertFalse(acts.adjust_dial(g, spec.key, 1))

    def test_dials_are_bounded(self):
        from pclengine.core import acts
        for spec in acts.DIALS:
            g = Game()
            g.act = spec.act
            acts.adjust_dial(g, spec.key, 500)
            self.assertLessEqual(acts.dial(g, spec.key), acts.DIAL_MAX)
            acts.adjust_dial(g, spec.key, -500)
            self.assertGreaterEqual(acts.dial(g, spec.key), 0)

    def test_arrows_drive_the_dial_in_those_acts(self):
        from pclengine.core import acts
        for spec in acts.DIALS:
            g = Game()
            g.act = spec.act
            actions.handle_key("RIGHT", g)
            self.assertEqual(acts.dial(g, spec.key), 1)

    def test_arrows_still_do_their_old_job_elsewhere(self):
        g = Game()
        g.act = 1
        before = g.price
        actions.handle_key("LEFT", g)
        self.assertNotEqual(g.price, before)


class TestOpportunityCosts(unittest.TestCase):
    """Choices have to actually shut other choices out."""

    def setUp(self):
        loader.reset()

    def test_taking_a_fork_forecloses_its_sibling(self):
        forks = [p for p in projects.ALL if p.excludes]
        self.assertGreaterEqual(len(forks), 4, "the tree needs real forks")
        for project in forks:
            g = Game()
            g.data = g.entropy = 1e9
            g.steppers = 100
            g.completed = {"industry_standard", "swarm_pathing",
                           "conflict_free"}
            project.buy(g)
            for other in project.excludes:
                with self.subTest(project=project.id, shut=other):
                    self.assertIn(other, g.foreclosed)

    def test_a_foreclosed_project_never_appears(self):
        g = Game()
        g.data = g.entropy = 1e9
        g.steppers = 100
        projects.BY_ID["euv_scanners"].buy(g)
        offered = {p.id for p in projects.available(g)}
        self.assertNotIn("greenfield_capacity", offered)

    def test_the_road_not_taken_explains_itself(self):
        g = Game()
        g.data = g.entropy = 1e9
        g.steppers = 100
        projects.BY_ID["euv_scanners"].buy(g)
        hint = projects.BY_ID["greenfield_capacity"].unlock_hint(g)
        self.assertIn("ruled out", hint)

    def test_research_gates_capabilities(self):
        """You cannot do computing before you have researched Computing."""
        g = Game()
        g.bandwidth, g.funds = 20, 10_000.0
        self.assertFalse(research.has(g, "computing"))
        self.assertFalse(g.buy_thread(), "bought a thread without Computing")
        g.researched.update({"metrology", "computing"})
        self.assertTrue(g.buy_thread())

    def test_threads_cost_money_and_bandwidth_only_throttles(self):
        """You may always buy another; bandwidth decides what it carries."""
        g = Game()
        g.researched.update({"metrology", "computing"})
        g.bandwidth, g.funds = 2, 10_000.0
        for _ in range(6):
            self.assertTrue(g.buy_thread(), "a thread was refused")
        self.assertGreater(g.threads, g.bandwidth)
        self.assertLess(g.bandwidth_ratio, 1.0)
        capped = g.data_rate
        g.bandwidth = g.threads
        self.assertGreater(g.data_rate, capped, "the ceiling did not lift")

    def test_a_thread_you_cannot_pay_for_is_refused(self):
        g = Game()
        g.researched.update({"metrology", "computing"})
        g.bandwidth, g.funds = 100, 0.0
        self.assertFalse(g.buy_thread())
        self.assertIn("costs", g.why_not_thread())

    def test_the_buffer_costs_money_and_stock_and_raises_the_cap(self):
        g = Game()
        g.researched.update({"metrology", "computing"})
        g.funds, g.unsold = 10_000.0, 100_000.0
        before = (g.funds, g.unsold, g.stock_cap)
        self.assertTrue(g.buy_buffer())
        self.assertLess(g.funds, before[0], "money was not taken")
        self.assertLess(g.unsold, before[1], "stock was not taken")
        self.assertGreater(g.stock_cap, before[2], "the cap did not rise")

    def test_a_full_warehouse_throttles_the_line(self):
        """Not to a stop -- selling frees room -- but to the sale rate."""
        g = Game()
        g.steppers, g.wafers, g.die_yield = 50, 1e9, 10.0
        free = Game()
        free.steppers, free.wafers, free.die_yield = 50, 1e9, 10.0
        g.unsold = g.stock_cap
        start, start_free = g.chips, free.chips
        for _ in range(5):
            g.tick(1.0)
            free.tick(1.0)
        made, unhindered = g.chips - start, free.chips - start_free
        self.assertLess(made, unhindered * 0.2, "the ceiling did not bite")
        self.assertTrue(any("Warehouse full" in m for m in g.messages))

    def test_the_warehouse_ceiling_lifts_with_the_order_book(self):
        """Past Act I chips are the currency; capping them caps your money."""
        g = Game()
        g.act = 2
        self.assertEqual(g.stock_cap, float("inf"))

    def test_research_gates_acts(self):
        from pclengine.core import acts
        g = Game()
        for act in range(2, acts.last_number() + 1):
            with self.subTest(act=act):
                self.assertFalse(research.act_open(g, act))
        g.research = 1e9
        for _ in range(30):
            for tech in research.available(g):
                research.buy(g, tech.id)
        for act in range(2, acts.last_number() + 1):
            with self.subTest(act=act):
                self.assertTrue(research.act_open(g, act))

    def test_every_tech_is_reachable(self):
        """No node may be orphaned behind a prerequisite that never opens.

        A fork's losing side is a different thing: it is reachable, you
        simply chose otherwise. So this asks whether each node could be
        reached at all, with foreclosure set aside.
        """
        g = Game()
        g.research = 1e12
        for _ in range(len(research.TREE) + 2):
            g.foreclosed_tech.clear()          # ignore the choices, not the tree
            for tech in research.available(g):
                research.buy(g, tech.id)
        missing = [t.id for t in research.TREE if t.id not in g.researched]
        self.assertEqual(missing, [])

    def unlock_up_to(self, g, tech):
        """Grant everything this node stands on, depth first."""
        for need in tech.requires:
            parent = research.BY_ID.get(need)
            if parent is not None and need not in g.researched:
                self.unlock_up_to(g, parent)
                g.researched.add(need)

    def test_a_fork_closes_its_other_side(self):
        """And the tree has some, or it is a list you read top to bottom."""
        forks = [t for t in research.TREE if t.excludes]
        self.assertTrue(forks, "the tech tree has no choices in it")
        g = Game()
        g.research = 1e12
        tech = forks[0]
        self.unlock_up_to(g, tech)
        self.assertTrue(research.buy(g, tech.id))
        for other in tech.excludes:
            with self.subTest(shut=other):
                self.assertIn(other, g.foreclosed_tech)
                self.assertNotIn(other, [t.id for t in research.available(g)])

    def test_a_tech_that_does_something_does_it_once(self):
        doers = [t for t in research.TREE if t.effect]
        self.assertTrue(doers, "no node in the tree actually does anything")
        for tech in doers[:4]:
            g = Game()
            g.research = 1e12
            self.unlock_up_to(g, tech)
            # ints as well as floats: +1 research bench is a change.
            before = {f: getattr(g, f) for f in vars(g)
                      if isinstance(getattr(g, f), (int, float))
                      and not isinstance(getattr(g, f), bool)}
            research.buy(g, tech.id)
            changed = [f for f, was in before.items()
                       if getattr(g, f) != was and f != "research"]
            with self.subTest(tech=tech.id):
                self.assertTrue(changed, f"{tech.id} changed nothing")

    def test_every_act_has_a_tech_that_opens_it(self):
        from pclengine.core import acts
        for act in range(2, acts.last_number() + 1):
            with self.subTest(act=act):
                self.assertIsNotNone(research.act_tech(act))

    def test_prerequisites_all_exist(self):
        for tech in research.TREE:
            for needed in tech.requires:
                with self.subTest(tech=tech.id):
                    self.assertIn(needed, research.BY_ID)


class TestPrestige(unittest.TestCase):
    def setUp(self):
        loader.reset()

    def test_a_deeper_run_is_worth_more(self):
        from pclengine.core import prestige
        shallow = Game()
        shallow.act = 2
        deep = Game()
        deep.act = 10
        self.assertGreater(prestige.credits_earned(deep),
                           prestige.credits_earned(shallow))

    def test_losing_still_teaches_you_something(self):
        from pclengine.core import prestige
        g = Game()
        g.act = 6
        g.defeated = True
        self.assertGreater(prestige.credits_earned(g), 0)

    def test_upgrades_cost_credits_and_stick(self):
        from pclengine.core import prestige
        g = Game()
        g.mask_credits = 1000.0
        upgrade = prestige.UPGRADES[0]
        self.assertTrue(prestige.buy(g, upgrade.key))
        self.assertLess(g.mask_credits, 1000.0)
        fresh = Game()
        fresh.legacy = dict(g.legacy)
        prestige.apply_legacy(fresh)
        self.assertGreater(fresh.research, Game().research)

    def test_you_cannot_buy_what_you_cannot_afford(self):
        from pclengine.core import prestige
        g = Game()
        g.mask_credits = 0.0
        self.assertFalse(prestige.buy(g, prestige.UPGRADES[0].key))

    def test_repeatable_upgrades_get_dearer_and_cap(self):
        from pclengine.core import prestige
        g = Game()
        g.mask_credits = 1e9
        upgrade = prestige.BY_KEY["grant"]
        first = upgrade.price(g.legacy)
        prestige.buy(g, "grant")
        self.assertGreater(upgrade.price(g.legacy), first)
        for _ in range(50):
            prestige.buy(g, "grant")
        self.assertLessEqual(upgrade.owned(g.legacy), upgrade.cap)


class TestRunSummary(unittest.TestCase):
    def setUp(self):
        loader.reset()

    def test_summary_describes_a_finished_run(self):
        from pclengine.store import summary
        g = Game()
        g.act = 5
        g.elapsed = 3600
        g.finished = True
        g.act_log = [(1, 0.0), (2, 1200.0), (5, 2400.0)]
        report = summary.as_dict(g)
        self.assertTrue(report["title"])
        self.assertTrue(report["rows"])
        self.assertEqual(len(report["acts"]), 3)

    def test_a_lost_run_reads_as_lost(self):
        from pclengine.store import summary
        g = Game()
        g.finished = True
        g.defeated = True
        self.assertIn("TAKEN APART", summary.as_dict(g)["title"])

    def test_history_round_trips(self):
        from pclengine.store import summary
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "runs.json")
            g = Game()
            g.act = 4
            g.finished = True
            summary.record(g, path)
            summary.record(g, path)
            self.assertEqual(len(summary.load_history(path)), 2)
            self.assertEqual(len(summary.history_lines(path)), 2)


class TestConsole(unittest.TestCase):
    def test_expressions_statements_and_errors(self):
        g = Game()
        self.assertEqual(console.run("g.chips = 5", g)["result"], "")
        self.assertEqual(console.run("g.chips", g)["result"], "5")
        self.assertIn("hello", console.run("print('hello')", g)["output"])
        self.assertIn("ZeroDivisionError", console.run("1/0", g)["error"])

    def test_the_game_modules_are_in_scope(self):
        g = Game()
        result = console.run("len(projects.ALL) > 0", g)
        self.assertEqual(result["result"], "True")

    def test_namespace_persists(self):
        g = Game()
        console.run("marker = 41", g)
        self.assertEqual(console.run("marker + 1", g)["result"], "42")


class TestMods(unittest.TestCase):
    def tearDown(self):
        loader.reset()

    def test_discovery_and_reset(self):
        base = len(projects.ALL)
        found = loader.discover()
        loader.load(found)
        self.assertGreaterEqual(len(projects.ALL), base)
        loader.reset()
        self.assertEqual(len(projects.ALL), base)

    def test_no_shipped_mod_fails_to_load(self):
        for info in loader.load(loader.discover()):
            with self.subTest(mod=info.key):
                self.assertIsNone(info.error, f"{info.key}: {info.error}")

    def test_constants_are_restored_on_reset(self):
        from pclengine import content
        before = content.constant("EARTH_MATTER")
        loader.load(loader.discover())
        loader.reset()
        self.assertEqual(content.constant("EARTH_MATTER"), before)

    def test_a_broken_mod_does_not_take_the_game_down(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "broken.py")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("def register(api):\n    raise RuntimeError('no')\n")
            info = loader.ModInfo("broken", "Broken", "", path, True)
            loader.load([info])
            self.assertIsNotNone(info.error)


class TestErrorHandling(unittest.TestCase):
    def setUp(self):
        errors.clear()

    def test_guard_records_and_continues(self):
        with errors.Guard("a test") as guard:
            raise ValueError("boom")
        self.assertTrue(guard)
        self.assertEqual(errors.latest().kind, "ValueError")

    def test_repeats_are_counted_not_piled_up(self):
        for _ in range(20):
            try:
                {}["missing"]
            except KeyError as exc:
                errors.capture("spam", exc, log=False)
        self.assertEqual(len(errors.FAILURES), 1)
        self.assertEqual(errors.FAILURES[0].count, 20)

    def test_keyboard_interrupt_is_not_swallowed(self):
        with self.assertRaises(KeyboardInterrupt):
            with errors.Guard("a test"):
                raise KeyboardInterrupt


if __name__ == "__main__":
    unittest.main()


class TestBrandReachesTheWholeRun(unittest.TestCase):
    """A name has to be worth something after the order book is gone."""

    def setUp(self):
        loader.reset()
        from base import bench
        self.bench = bench

    def test_brand_scales_research_and_defender_cost(self):
        from pclengine.core import war
        g = Game(seed=1)
        g.labs, g.brand = 100, 1.0
        base_research = research.output(g)
        base_guards = war.unit_price(g, "guards")
        g.brand = 8.0
        self.assertGreater(research.output(g), base_research)
        self.assertLess(war.unit_price(g, "guards"), base_guards)
        g.brand = 0.2
        self.assertLess(research.output(g), base_research)
        self.assertGreater(war.unit_price(g, "guards"), base_guards)

    def test_the_knock_on_effects_are_damped(self):
        """Brand compounds, so fifteen times the name is not fifteen times
        the research -- that would simply end the game."""
        g = Game(seed=1)
        g.labs, g.brand = 100, 1.0
        base = research.output(g)
        g.brand = 15.0
        self.assertLess(research.output(g), base * 4)
        self.assertGreater(research.output(g), base * 2)

    def test_a_modifier_nobody_registered_changes_nothing(self):
        from pclengine.core import modifiers
        self.assertEqual(modifiers.of(Game(seed=1), "no_such_number"), 1.0)

    def test_a_broken_modifier_does_not_stop_the_tick(self):
        from pclengine.core import modifiers

        def explode(g):
            raise RuntimeError("no")

        modifiers.add("research_output", explode)
        g = Game(seed=1)
        g.labs = 10
        self.assertGreater(research.output(g), 0)


class TestPrestigeCarriesTheNewSystems(unittest.TestCase):
    def setUp(self):
        loader.reset()

    def _bought(self, key, times):
        from pclengine.core import prestige
        g = Game(seed=1)
        g.mask_credits = 1e6
        for _ in range(times):
            prestige.buy(g, key)
        fresh = Game(seed=1)
        fresh.legacy = dict(g.legacy)
        prestige.apply_legacy(fresh)
        return fresh

    def test_reputation_starts_you_with_a_name(self):
        self.assertGreater(self._bought("reputation", 3).brand, Game().brand)

    def test_rig_contract_starts_you_with_rigs(self):
        self.assertGreater(self._bought("rig_contract", 2).rigs, 0)

    def test_published_results_carries_the_reward_too(self):
        fresh = self._bought("published", 2)
        self.assertEqual(fresh.cracked, 2)
        self.assertGreater(fresh.entropy, 0)
        self.assertGreater(fresh.bandwidth, Game().bandwidth)

    def test_the_new_systems_are_worth_mask_credits(self):
        from pclengine.core import prestige
        g = Game(seed=1)
        plain = prestige.credits_earned(g)
        g.solved, g.cracked = 6, 6
        self.assertGreater(prestige.credits_earned(g), plain)


class TestHelp(unittest.TestCase):
    """The help is content's, and all of it has to be reachable."""

    def setUp(self):
        loader.reset()

    def test_every_panel_the_game_has_is_explained(self):
        from pclengine import content
        headings = " ".join(h for h, _ in content.help_sections()).upper()
        for tab in ("BENCH", "CRYPT", "WAR"):
            with self.subTest(tab=tab):
                self.assertIn(tab, headings)

    def test_paging_reaches_every_line(self):
        from pclengine import content
        from pclengine.ui import screen
        g = Game(seed=1)
        screen.render(g, 100, 40, help_on=True)
        seen = []
        for page in range(screen.help_pages(g)):
            g.help_page = page
            body, _count = screen.help_body(g, 30)
            seen.extend(text for text, _bold in body)
        for _heading, lines in content.help_sections():
            for line in lines:
                with self.subTest(line=line[:40]):
                    self.assertIn(line, seen)

    def test_a_heading_never_ends_a_page_alone(self):
        from pclengine.ui import screen
        g = Game(seed=1)
        for rows in (10, 16, 30):
            pages = screen.help_pagination(screen.content.help_sections(), rows)
            for index, page in enumerate(pages):
                trimmed = [t for t, _b in page if t.strip()]
                with self.subTest(rows=rows, page=index):
                    self.assertGreater(len(trimmed), 1)

    def test_an_engine_with_no_content_still_says_something(self):
        from pclengine.ui import screen
        loader.load([], with_base=False)
        try:
            g = Game(seed=1)
            body, count = screen.help_body(g, 10)
            self.assertGreaterEqual(count, 1)
            self.assertTrue(any(t.strip() for t, _b in body))
        finally:
            loader.reset()


class TestModsCanActuallyChangeTheGame(unittest.TestCase):
    """The mod API has to hold up when a mod really uses it."""

    def setUp(self):
        loader.reset()

    def tearDown(self):
        loader.reset()

    def test_a_constant_a_mod_moved_reaches_the_field_built_from_it(self):
        """A field read at import time is read before any mod has run.

        A mod that raises EARTH_MATTER expects a game to start with that
        much. If the field kept the old figure while the act that ends on it
        used the new one, that act could never be finished -- which is what
        happened, and is why this test is here.
        """
        from pclengine import content
        from pclengine.core import state
        loader.load(loader.discover())
        moved = content.constant("EARTH_MATTER")
        self.assertEqual(state.Game().available_matter, moved)

    def test_every_field_built_from_a_constant_is_a_factory(self):
        from base.game import fields
        from base import constants
        pool = {getattr(constants, n) for n in dir(constants)
                if n.isupper() and isinstance(getattr(constants, n), float)}
        for name, default in fields.FIELDS.items():
            if callable(default):
                continue
            with self.subTest(field=name):
                self.assertNotIn(default, pool,
                                 f"{name} freezes a constant at import time")

    def test_directories_are_discovered_as_mods(self):
        """The README says a mod can be a folder. It has to actually be."""
        import os
        found = {i.key for i in loader.discover()}
        on_disk = {e for e in os.listdir(loader.MODS_DIR)
                   if os.path.isfile(os.path.join(loader.MODS_DIR, e,
                                                  "__init__.py"))
                   and e != "base"}
        self.assertTrue(on_disk <= found, f"missed {on_disk - found}")

    def test_the_bot_never_volunteers_to_end_the_run(self):
        from pclengine.core import projects
        from pclengine.dev import autoplay
        loader.load(loader.discover())
        enders = [p for p in projects.ALL if p.ends_run]
        self.assertTrue(enders, "nothing ends the run any more")
        g = Game(seed=1)
        for p in enders:
            g.completed.add(p.id)
        before = set(g.completed)
        autoplay._buy_projects(g)
        self.assertEqual({p.id for p in enders} & (set(g.completed) - before),
                         set())

    def test_a_mod_that_adds_acts_gets_them_paced_and_reachable(self):
        from pclengine.core import acts, research
        from pclengine.dev import balance
        loader.load(loader.discover())
        added = [a for a in acts.ALL if a.number > 11]
        if not added:
            self.skipTest("no mod adding acts is enabled")
        for act in added:
            with self.subTest(act=act.number):
                self.assertIsNotNone(act.complete, "no way to finish it")
                self.assertIn(act.number, balance.TARGETS, "no pacing")
                self.assertIsNotNone(research.act_tech(act.number),
                                     "no tech opens it")
                self.assertTrue(act.panels(Game(seed=1)))


class TestNumberRowIsReserved(unittest.TestCase):
    """1-8 takes a project. Everywhere, on every tab, in every act."""

    def setUp(self):
        loader.load(loader.discover())

    def furnished(self):
        from pclengine.core import research
        g = Game(seed=1)
        g.research = 1e9
        for _ in range(len(research.TREE) + 2):
            for tech in research.available(g):
                research.buy(g, tech.id)
        g.rigs, g.data, g.buffer, g.funds = 500, 9e6, 4000, 5e6
        g.bandwidth, g.threads = 400, 200
        return g

    def test_no_tab_can_claim_a_number(self):
        from pclengine.ui import keymap, panels
        g = self.furnished()
        for view in panels.visible(g):
            g.panel_view = view.key
            owner = {}
            for name, keys in keymap.describe(g):
                for key in keys:
                    owner[key] = name
            for key in "12345678":
                if key in owner:
                    with self.subTest(tab=view.key, key=key):
                        self.assertEqual(owner[key], "projects")

    def test_a_number_takes_a_project_from_any_tab(self):
        from pclengine.core import projects
        from pclengine.ui import panels
        for view in panels.visible(self.furnished()):
            g = self.furnished()
            g.panel_view = view.key
            available = projects.available(g)
            if not available or not available[0].affordable(g):
                continue
            target = available[0].id
            actions.handle_key("1", g)
            with self.subTest(tab=view.key):
                self.assertIn(target, g.completed)

    def test_every_list_is_driven_the_same_way(self):
        """A cursor and ENTER, so there is one thing to learn."""
        from pclengine.ui import panels
        g = self.furnished()
        for view in panels.visible(g):
            if view.key in ("ops", "projects"):
                continue
            g.panel_view = view.key
            with self.subTest(tab=view.key):
                # Not an assertion about what it does, only that it is
                # offered: a list you cannot move through is a dead list.
                self.assertIsNone(actions.handle_key("DOWN", g))
                self.assertIsNone(actions.handle_key("UP", g))

    def test_defenders_are_still_reachable(self):
        """They used to be on 1-4, which the reservation would have eaten."""
        from pclengine.core import war
        g = self.furnished()
        g.panel_view = "war"
        if not war.units_for(g.act):
            self.skipTest("no defenders in this act")
        actions.handle_key("ENTER", g)
        self.assertTrue(any(g.forces.values()), "nothing could be built")


class TestUniversalSelection(unittest.TestCase):
    """One set of keys for every list: arrows pick, ENTER acts."""

    def setUp(self):
        loader.load(loader.discover())

    def furnished(self):
        g = Game(seed=1)
        g.research = 1e9
        for _ in range(len(research.TREE) + 2):
            for tech in research.available(g):
                research.buy(g, tech.id)
        g.funds, g.unsold, g.rigs = 1e9, 1e30, 500
        g.data, g.buffer, g.bandwidth, g.threads = 9e6, 4000, 900, 400
        return g

    def test_every_tab_answers_the_selection_keys(self):
        for view in panels.visible(self.furnished()):
            for key in ("UP", "DOWN", "ENTER"):
                g = self.furnished()
                g.panel_view = view.key
                with self.subTest(tab=view.key, key=key):
                    # No exception, and no stray action escaping to the loop.
                    self.assertIsNone(actions.handle_key(key, g))

    def test_enter_takes_the_picked_project(self):
        from pclengine.core import projects
        g = self.furnished()
        g.panel_view = "projects"
        listing = projects.available(g)
        if len(listing) < 2:
            self.skipTest("not enough projects to pick between")
        actions.handle_key("DOWN", g)
        wanted = projects.available(g)[1].id
        actions.handle_key("ENTER", g)
        self.assertIn(wanted, g.completed)

    def test_the_arrows_never_leave_a_list_unreachable(self):
        """A list you cannot move through is a list you cannot use."""
        from pclengine.ui import panels as p
        g = self.furnished()
        for view in p.visible(g):
            g.panel_view = view.key
            rows = [r for block in view.build(g) for r in block["rows"]]
            if len(rows) < 2:
                continue
            with self.subTest(tab=view.key):
                self.assertIsNone(actions.handle_key("DOWN", g))


class TestBufferSupply(unittest.TestCase):
    """Buffer comes off a shelf that refills. Money cannot rush it."""

    def setUp(self):
        loader.reset()

    def rich(self):
        g = Game(seed=1)
        g.researched.update({"metrology", "computing"})
        g.funds, g.unsold = 1e9, 1e9
        return g

    def test_you_cannot_buy_more_than_is_on_the_shelf(self):
        g = self.rich()
        available = g.buffer_in_stock
        self.assertGreater(available, 0)
        for _ in range(available):
            self.assertTrue(g.buy_buffer())
        self.assertEqual(g.buffer_in_stock, 0)
        self.assertFalse(g.buy_buffer(), "bought one that did not exist")

    def test_all_the_money_in_the_world_does_not_help(self):
        g = self.rich()
        g.buffer_stock = 0.0
        g.funds, g.unsold = 1e30, 1e30
        self.assertFalse(g.buy_buffer())
        self.assertIn("stock", g.why_not_buffer())

    def test_the_shelf_refills_and_says_when(self):
        g = self.rich()
        g.buffer_stock = 0.0
        soon = g.buffer_restock_in
        self.assertGreater(soon, 0)
        for _ in range(int(soon) + 2):
            g.tick(1.0)
        self.assertGreaterEqual(g.buffer_in_stock, 1)
        self.assertTrue(g.buy_buffer())

    def test_the_shelf_does_not_grow_past_what_it_holds(self):
        g = self.rich()
        for _ in range(4000):
            g.tick(1.0)
        self.assertLessEqual(g.buffer_stock, g.buffer_stock_max)

    def test_the_supply_limit_actually_binds_in_act_one(self):
        """If it never runs out it is not a constraint, only a delay."""
        from pclengine.dev import autoplay
        g = Game(seed=1)
        emptied = False
        for _ in range(9000):
            autoplay.step(g, 1.0)
            if g.buffer_in_stock < 1 and g.buffer > 4:
                emptied = True
            if g.act > 1:
                break
        self.assertTrue(emptied, "the shelf was never the limiting factor")
        self.assertEqual(g.act, 2, "and yet the act still has to finish")


class TestPriceIsUnlocked(unittest.TestCase):
    """Charge what you like. The order book decides whether that was wise."""

    def setUp(self):
        loader.reset()

    def test_there_is_no_ceiling(self):
        g = Game(seed=1)
        g.set_price(1.99)
        for _ in range(40):
            g.adjust_price(1)
        self.assertGreater(g.price, 2.0, "the old ceiling is still there")

    def test_there_is_still_a_floor(self):
        g = Game(seed=1)
        g.set_price(0.02)
        for _ in range(20):
            g.adjust_price(-1)
        self.assertGreaterEqual(g.price, 0.01)
        self.assertGreater(g.order_flow(), 0)

    def test_the_step_grows_with_the_price(self):
        """A cent at a time is no use at fifty dollars."""
        g = Game(seed=1)
        seen = []
        for value in (0.5, 5.0, 50.0, 500.0):
            g.set_price(value)
            seen.append(g.price_step)
        self.assertEqual(seen, sorted(seen))
        self.assertLess(seen[0], seen[-1])

    def test_a_silly_price_is_still_a_number(self):
        g = Game(seed=1)
        g.set_price(1e9)
        self.assertGreater(g.order_flow(), 0.0)
        self.assertEqual(g.order_flow(), g.order_flow())      # not nan
        g.set_price(float("nan"))
        self.assertEqual(g.price, g.price)

    def test_the_bot_will_use_the_room(self):
        """It aims to clear what it makes; with no ceiling it can."""
        from pclengine.dev import autoplay
        g = Game(seed=3)
        for _ in range(1200):
            autoplay.step(g, 1.0)
        self.assertGreater(g.price, 0.0)
        self.assertGreater(g.chips, 0)
