"""Everything you can reach before and between runs.

    widgets  the panelled list itself: entries, panels, selection
    pages    what each page offers, as data
    run      the loop that draws a page and acts on what you choose
"""

from pclengine.ui.menus.pages import PAGES, TITLES, Context
from pclengine.ui.menus.run import run
from pclengine.ui.menus.widgets import Entry, Menu

__all__ = ["Context", "Entry", "Menu", "PAGES", "TITLES", "run"]
