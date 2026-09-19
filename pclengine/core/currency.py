"""What a project can be priced in.

The engine has no idea what a byte of telemetry or a gram of silicon is. It
only knows that a project costs some amount of some named thing, that the
thing is held in a field on the game, and that the amount has to be written
out somewhere. Content registers the rest.

    api.add_currency(api.Currency("data", "data", size))

Register them in the order you want them shown.
"""

ALL = []
BY_NAME = {}


class Currency:
    """One thing a project can be priced in."""

    __slots__ = ("name", "field", "render")

    def __init__(self, name, field=None, render=None):
        self.name = name
        #: The attribute on the game that holds how much you have.
        self.field = field or name
        self.render = render or (lambda amount: f"{amount:,.0f} {name}")

    def held(self, g):
        return getattr(g, self.field, 0.0)

    def spend(self, g, amount):
        setattr(g, self.field, self.held(g) - amount)

    def text(self, amount):
        return self.render(amount)


def add(currency):
    ALL.append(currency)
    BY_NAME[currency.name] = currency
    return currency


def reset():
    del ALL[:]
    BY_NAME.clear()


def names():
    return [c.name for c in ALL]
