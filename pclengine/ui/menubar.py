"""The buttons along the top, as a registry.

A front end draws a row of them and the engine says what is in it. The
point is that a mod can put one there, take one away, or replace one,
without editing a template it does not own.

    api.menu_button("atlas", "Atlas", screen="atlas", after="tech")
    api.menu_button("saves", hidden=True)          # take one away
    api.menu_button("help", label="Manual")        # replace its label

Calling `menu_button` with an id that already exists edits that button
rather than adding a second one, which is what makes "remove or replace"
as easy as "add" -- a mod should not have to know whether it is first.

The order is what you see. `after` and `before` place a button next to a
named one; without either it goes on the end. `shown(game)` hides it until
it is worth having, `developer` hides it unless developer mode is on, and
`screen` names a panel the front end already knows how to show. A button
with `action` instead posts that name back to the engine.
"""


class Button:
    __slots__ = ("id", "label", "screen", "action", "title", "developer",
                 "shown", "hidden", "icon")

    def __init__(self, button_id, label=None, screen=None, action=None,
                 title="", developer=False, shown=None, hidden=False,
                 icon=""):
        self.id = button_id
        self.label = label if label is not None else button_id.title()
        #: The panel to switch to, if this button is navigation.
        self.screen = screen
        #: A named thing for the engine to do, if it is not.
        self.action = action
        self.title = title
        self.developer = developer
        #: fn(game) -> bool, or None for always.
        self.shown = shown
        self.hidden = hidden
        self.icon = icon

    def visible(self, g, developer=False):
        if self.hidden:
            return False
        if self.developer and not developer:
            return False
        if self.shown is None:
            return True
        try:
            return bool(self.shown(g))
        except Exception:          # a broken predicate hides one button
            return False

    def as_dict(self):
        return {"id": self.id, "label": self.label, "screen": self.screen,
                "action": self.action, "title": self.title,
                "developer": self.developer, "icon": self.icon}


BUTTONS = []
BY_ID = {}


def _place(button, after=None, before=None):
    anchor = after or before
    if anchor and anchor in BY_ID:
        index = BUTTONS.index(BY_ID[anchor])
        BUTTONS.insert(index + 1 if after else index, button)
    else:
        BUTTONS.append(button)


def add(button_id, after=None, before=None, **fields):
    """Add a button, or edit the one that is already there.

    Editing rather than duplicating is deliberate: a mod that wants to
    rename or hide a button should not have to remove it first, and two
    mods touching the same button should not produce two of them.
    """
    existing = BY_ID.get(button_id)
    if existing is not None:
        for name, value in fields.items():
            if not hasattr(existing, name):
                raise AttributeError(f"buttons have no field {name!r}")
            setattr(existing, name, value)
        if after or before:
            BUTTONS.remove(existing)
            _place(existing, after, before)
        return existing
    button = Button(button_id, **fields)
    BY_ID[button_id] = button
    _place(button, after, before)
    return button


def remove(button_id):
    button = BY_ID.pop(button_id, None)
    if button is not None and button in BUTTONS:
        BUTTONS.remove(button)
    return button


def reset():
    del BUTTONS[:]
    BY_ID.clear()


def visible(g, developer=False):
    return [b for b in BUTTONS if b.visible(g, developer)]


def as_data(g, developer=False):
    return [b.as_dict() for b in visible(g, developer)]


#: What every game on this engine has. Content adds to it or edits it.
DEFAULTS = [
    ("game", {"label": "Game", "screen": "game"}),
    ("projects", {"label": "Projects", "screen": "projects"}),
    ("tech", {"label": "Tech Tree", "screen": "tech"}),
    ("newgame", {"label": "New Run", "screen": "newgame"}),
    ("mods", {"label": "Mods", "screen": "mods"}),
    ("saves", {"label": "Saves", "screen": "saves"}),
    ("help", {"label": "Help", "screen": "help"}),
    ("dev", {"label": "Developer", "screen": "dev", "developer": True}),
    ("editor", {"label": "Save Editor", "screen": "editor",
                "developer": True}),
]


def install_defaults():
    reset()
    for button_id, fields in DEFAULTS:
        add(button_id, **fields)


install_defaults()
