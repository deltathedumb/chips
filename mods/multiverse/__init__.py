"""MULTIVERSE: twenty-four acts past the Successor.

FOUNDRY ends when every atom in one light cone is a transistor. This asks
the obvious next question, and then keeps asking it: there is more than one
universe, they are reachable, most of them are empty, and something else
has been converting them since before you started.

It is an expansion rather than a separate game, so it builds on FOUNDRY's
own hardware model -- the same rigs on the same price curve -- and reaches
the engine through the same `register(api)` everything else uses. Nothing
in here is privileged and nothing in FOUNDRY was edited to make room for it.

    realms.py    the twenty-four acts, as a table
    engine.py    the schedule they are priced off, and the one tick,
                 constraint and pair of panels they all share

Taping out at Act XI still works and still ends the run. Going on into the
multiverse is the other choice, and it is a long one: about four hours on
top of FOUNDRY's two.
"""

NAME = "Multiverse"
DESCRIPTION = "Twenty-four more acts, past the last atom in this universe."

from pclengine.core.acts import Act
from pclengine.core.research import Tech

from base.acts import final as base_final
from base.game import keys as base_keys

from multiverse import engine, realms

#: What the first crossing costs, and how much dearer each one after it is.
#: Priced against Act XI rather than against nothing, so the first crossing
#: is earned instead of automatic.
ENTRY_DATA = 900_000_000
ENTRY_ENTROPY = 60_000
ENTRY_STEP = 1.35

#: The research chain. The growth here is gentle on purpose and the reason
#: is measured: research income across these acts rises about sixfold in
#: total, because labs are bought with chips and lab count goes as the log
#: of what you can spend. A chain that compounds faster than its own income
#: is not a long game, it is a wall with acts painted on it.
FIRST_TECH_COST = 900_000.0
TECH_STEP = 1.10

#: How long one of these ought to take, for `--balance` to judge.
PACING = (6, 16)


def _fields(api):
    """Every act's producer, relief and progress counter."""
    for realm in realms.REALMS:
        api.field(realm.producer[0], 0.0)
        api.field(realm.relief[0], 0.0)
        api.field(realm.quantity, 0.0)


#: The four quarters of the arc, and what colour each is drawn in.
CATEGORIES = [
    ("crossing", "The Crossing", "#5fc8c8", "cyan"),
    ("harvest", "The Harvest", "#8fcf6f", "green"),
    ("others", "The Others", "#e07f9f", "red"),
    ("substrate", "The Substrate", "#a98fe0", "white"),
]
#: One icon per act, in order. Generic shapes: the tree is read as a
#: picture, so what matters is that neighbours look different.
ICONS = ["eye", "bolt", "rift", "wave", "beacon", "anvil",
         "network", "flask", "scales", "crystal", "star", "globe",
         "shield", "scales", "shield", "key", "branch", "infinity",
         "cube", "scales", "rift", "cube", "network", "infinity"]


def _techs(api):
    """One tech per act, in a chain, each one opening its own act."""
    for key, label, colour, term in CATEGORIES:
        api.tech_category(key, label, colour, term)
    previous = "alignment_theory"          # FOUNDRY's last node
    cost = FIRST_TECH_COST
    for index, realm in enumerate(realms.REALMS):
        api.add_tech(Tech(
            realm.key + "_theory", realm.tech, realm.tech_blurb,
            round(cost), requires=(previous,), act=realm.number,
            category=realm.category,
            icon=ICONS[index % len(ICONS)]))
        previous = realm.key + "_theory"
        cost *= TECH_STEP


def _acts(api):
    for realm in realms.REALMS:
        act = api.add_act(Act(
            realm.number, realm.key,
            f"ACT {_roman(realm.number)}  ·  {realm.name}",
            realm.blurb,
            engine.tick_for(realm),
            engine.panels_for(realm),
            engine.material_for(realm),
            keys=realm.keys))
        act.complete = engine.complete_for(realm)
        act.target = engine.target_of(realm)
        # The same key handler FOUNDRY's late acts use: h and j buy the two
        # rigs, because these are the same kind of act.
        act.on_key = base_keys.handle
        api.pacing(realm.number, *PACING)


def _cross(number):
    """Entering a multiverse act, and paying for the crossing.

    Every act here funds itself from its own hardware, so whatever chip
    float the last one finished on is pure carry-over -- and it is enough
    to buy the next act's opening outright. That couples the acts: a long
    one leaves you rich and makes the next one instant, which makes the one
    after that slow, and the pacing oscillates instead of settling.

    So a crossing does not carry stock. What you were holding was made of
    the universe you just left.
    """
    arrive = base_final._enter(number)

    def effect(g):
        arrive(g)
        g.unsold = 0.0
    return effect


def _transitions(api):
    """One project per crossing, gated on the tech and the act before it."""
    data, entropy = ENTRY_DATA, ENTRY_ENTROPY
    for realm in realms.REALMS:
        api.add_project(
            "enter_" + realm.key,
            _title(realm), realm.blurb,
            _cross(realm.number),
            data=round(data), entropy=round(entropy),
            req=base_final._ready(realm.number),
            hint=base_final._hint(realm.number))
        data *= ENTRY_STEP
        entropy *= ENTRY_STEP


def _title(realm):
    return {
        12: "Look for the Others",
        13: "Build the Ladder",
        14: "Go Through",
    }.get(realm.number, "Enter " + realm.name.title())


ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
         (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
         (5, "V"), (4, "IV"), (1, "I")]


def _roman(number):
    out = []
    for value, letter in ROMAN:
        while number >= value:
            out.append(letter)
            number -= value
    return "".join(out)


HELP = [
    "  FOUNDRY ends when every atom in this light cone is a transistor.",
    "  There is more than one light cone.",
    "",
    "  Every act here has the same shape: one line of hardware that makes",
    "  progress (h), one that holds back whatever is stopping it (j), and",
    "  a number to reach. What changes is what happens when the second",
    "  line falls behind the first -- and the CONSTRAINT panel always says",
    "  which of the four it is:",
    "",
    "  THROUGHPUT   everything simply runs slower",
    "  HOLDING      what you have already built leaks away",
    "  SURVIVAL     the producers are destroyed, and stay destroyed",
    "  FOOTING      something else holds the volume and you cannot press",
    "",
    "  Buy the relief line first. It is always the cheaper of the two, and",
    "  on three of those four shapes, falling behind costs you work you",
    "  have already paid for.",
    "",
    "  Taping out at Act XI still works and still ends the run. This is",
    "  the other choice, and it is about four hours long.",
]


def _seed_probe(g, number, chips=None):
    """Probe a multiverse act the way a crossing leaves it: with nothing."""
    if realms.FIRST <= number <= realms.LAST:
        g.unsold = 0.0


def register(api):
    _fields(api)
    _techs(api)
    _acts(api)
    _transitions(api)
    api.probe_seed(_seed_probe)
    api.help_section("THE MULTIVERSE", HELP)
    api.editor_group("THE MULTIVERSE", [
        field for realm in realms.REALMS
        for field in (realm.producer[0], realm.relief[0], realm.quantity)])
    api.credit_bonus(lambda g: max(0.0, min(g.act, realms.LAST)
                                   - realms.FIRST + 1) * 6.0)
