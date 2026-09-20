"""Every frame must be an exact rectangle.

The terminal repaints by overwriting rows, so a line of the wrong visible
width corrupts the screen. Colour escapes make this easy to get wrong, which
is why it is asserted for every act, panel and width.
"""

import unittest

from pclengine import errors
from pclengine.core import acts
from pclengine.modding import loader
from pclengine.ui import editor, menus as menu, screen
from pclengine.core.state import Game

WIDTHS = (80, 97, 120, 160, 200)
HEIGHTS = (24, 30, 44)
PANEL_VIEWS = ("ops", "war", "research")


def furnished(act=1):
    """A game with enough in it that every panel has something to draw."""
    g = Game()
    g.act = act
    g.entropy_on = True
    g.scanners_unlocked = True
    g.counter_unlocked = True
    g.firmware = 20
    g.labs = 500
    g.forces = {"guards": 10, "fighters": 1e6, "pickets": 1e9}
    for attr in ("miners", "pullers", "foundries", "solar", "batteries",
                 "lifters", "radiators", "fronts", "shells", "sinks",
                 "lattices", "domains", "substrates", "nests", "warfabs",
                 "screens", "editors", "anchors", "capability",
                 "verification", "archivists", "vaults", "watchers", "masks",
                 "seed_fabs"):
        if hasattr(g, attr):
            setattr(g, attr, 8e10)
    return g


class TestGeometry(unittest.TestCase):
    def setUp(self):
        loader.reset()

    def assert_rectangular(self, lines, label):
        for index, line in enumerate(lines):
            self.assertEqual(
                screen.vlen(line), screen.W,
                f"{label}: row {index} is {screen.vlen(line)} wide, not {screen.W}")

    def test_every_act_and_panel(self):
        for act in acts.ALL:
            g = furnished(act.number)
            for panel_view in PANEL_VIEWS:
                g.panel_view = panel_view
                for width in WIDTHS:
                    lines = screen.render(g, width, 34)
                    self.assert_rectangular(
                        lines, f"act {act.number} / {panel_view} / {width}")

    def test_every_height(self):
        g = furnished(2)
        for height in HEIGHTS:
            for help_on in (False, True):
                lines = screen.render(g, 100, height, help_on)
                self.assert_rectangular(lines, f"height {height}")
                self.assertLessEqual(len(lines), height)

    def test_altered_runs_still_fit(self):
        """A clock or cost note in the header must not push a row over."""
        g = furnished(2)
        g.time_scale = 0.4
        g.cost_scale = 0.001
        g.hw_scale = 1e6
        self.assert_rectangular(screen.render(g, 80, 30), "annotated header")

    def test_too_small_terminal_says_so(self):
        lines = screen.render(furnished(), 40, 10)
        self.assertTrue(any("80" in line for line in lines))

    def test_menu_pages(self):
        ctx = menu.Context(furnished(), developer=True)
        for page in menu.PAGES:
            ctx.page = page
            screen = menu.Menu(page, menu.PAGES[page], ctx)
            for width in WIDTHS:
                self.assert_rectangular(screen.frame(width, 30), f"menu {page}")

    def test_save_editor(self):
        session = editor.Editor("does-not-exist.json")
        for project_view in (False, True):
            session.project_view = project_view
            for width in WIDTHS:
                self.assert_rectangular(session.frame(width, 30),
                                        f"editor {width}")

    def test_error_screen(self):
        try:
            raise ValueError("something went wrong")
        except ValueError as exc:
            failure = errors.capture("a test", exc, log=False)
        for width in WIDTHS:
            self.assert_rectangular(screen.error_screen(failure, width, 28),
                                    f"error {width}")

    def test_intro_and_ending_are_not_ragged(self):
        g = furnished()
        for lines in (screen.intro(100, 30), screen.ending(g, 100, 30)):
            for line in lines:
                self.assertLessEqual(screen.vlen(line), 100)


class TestWebView(unittest.TestCase):
    """The browser renders whatever the snapshot says, so it must be sane.

    The web front end ships as a mod, so the test loads it rather than
    reaching into the engine for something that is not there any more.
    """

    def setUp(self):
        loader.load(loader.discover())
        from web import view
        self.view = view

    def test_snapshot_for_every_act(self):
        for act in acts.ALL:
            g = furnished(act.number)
            with self.subTest(act=act.number):
                state = self.view.snapshot(g, developer=True)
                for key in ("act", "actName", "node", "headline", "left",
                            "right", "projects", "locked", "log"):
                    self.assertIn(key, state)
                self.assertTrue(state["left"] and state["right"])

    def test_no_nan_leaks_into_the_page(self):
        g = furnished(2)
        g.hw_scale = 0.0
        g.miners = 7.08e10
        state = self.view.snapshot(g)
        values = [row["value"] for panel in state["left"] + state["right"]
                  for row in panel["rows"]]
        for value in values:
            self.assertNotIn("nan", str(value).lower())


if __name__ == "__main__":
    unittest.main()


class TestWebSaveHandoff(unittest.TestCase):
    """The two ways the browser front end lost a save.

    Both were silent: the player pressed save, was told it had worked, and
    found an older game the next time the page loaded.
    """

    def session(self, mode="client"):
        from mods.web import server
        from pclengine.core.state import Game
        return server.Session(Game(seed=4), save_mode=mode)

    def test_held_save_older_than_the_run_is_refused(self):
        s = self.session()
        s.game.elapsed = 50.0
        blob = s.packed()               # a save taken at t=50
        s.game.elapsed = 9000.0         # ...and then two and a half hours
        message = s.adopt(blob)
        self.assertIn("older", message)
        self.assertEqual(s.game.elapsed, 9000.0,
                         "reloading the tab rolled the run back")

    def test_held_save_is_adopted_when_asked_for(self):
        s = self.session()
        s.game.elapsed = 50.0
        blob = s.packed()
        s.game.elapsed = 9000.0
        s.adopt(blob, force=True)
        self.assertEqual(s.game.elapsed, 50.0)

    def test_a_fresh_server_accepts_the_held_save(self):
        s = self.session()
        s.game.elapsed = 9000.0
        blob = s.packed()
        fresh = self.session()          # server restarted: elapsed 0
        fresh.adopt(blob)
        self.assertEqual(fresh.game.elapsed, 9000.0)

    def test_the_handoff_is_only_offered_once(self):
        """Which is why the client must store it before it drops a frame."""
        s = self.session()
        s.keep()
        first = s.snapshot()
        self.assertIn("saveBlob", first)
        self.assertNotIn("saveBlob", s.snapshot())


class TestTheme(unittest.TestCase):
    """Dark mode is a block of tokens, so nothing may name a colour."""

    def stylesheet(self):
        import os
        from pclengine.modding import loader
        path = os.path.join(loader.MODS_DIR, "web", "static", "app.css")
        if not os.path.exists(path):
            self.skipTest("the web front end is not installed")
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    def rules(self):
        """The stylesheet below the token blocks."""
        css = self.stylesheet()
        return css[css.index("body {"):]

    def test_no_rule_names_a_colour_directly(self):
        """The bug this catches shipped once.

        A rule with a literal colour cannot follow the theme, and the one
        that got missed was `body` -- so dark mode left the page white and
        only repainted the parts around it.
        """
        import re
        offenders = [line.strip() for line in self.rules().splitlines()
                     if re.search(r"#[0-9a-fA-F]{3,8}\b", line)]
        self.assertEqual(offenders, [], "these will not follow the theme")

    def test_both_themes_define_the_same_tokens(self):
        import re
        css = self.stylesheet()
        light = css[css.index(":root {"):css.index(':root[data-theme="dark"]')]
        dark = css[css.index(':root[data-theme="dark"]'):css.index("body {")]
        names = lambda block: set(re.findall(r"(--[a-z-]+):", block))
        missing = names(light) - names(dark)
        self.assertEqual(missing, set(), "dark mode would fall back to light")
        self.assertEqual(names(dark) - names(light), set())

    def test_every_token_used_is_defined(self):
        import re
        css = self.stylesheet()
        defined = set(re.findall(r"(--[a-z-]+):", css))
        used = set(re.findall(r"var\((--[a-z-]+)\)", css))
        self.assertEqual(used - defined, set(), "undefined token in a rule")

    def test_the_page_itself_is_themed(self):
        """Whatever else is right, the background and the text must be."""
        body = self.rules()
        body = body[:body.index("}")]
        self.assertIn("background: var(--bg)", body)
        self.assertIn("color: var(--fg)", body)
