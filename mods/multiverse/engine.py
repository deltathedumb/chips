"""What every multiverse act is made of.

Twenty-four acts share one tick, one pair of panels and one cost schedule.
What differs is the `kind` of constraint and the numbers the schedule hands
out, which is the only way to write this many acts and have them all still
be reachable at the end.

The hardware model is FOUNDRY's own -- this is an expansion, not a separate
game, so it buys `base.acts.rigs.Rig` on the same curve and self-funds the
same way rather than inventing a second economy beside it.
"""

from pclengine.core.acts import panel, row
from pclengine.fmt import small

from base.acts.rigs import RIGS, Rig, rig_panel, self_fund, stock_panel

#: Act 12's producer, and how much dearer each act's hardware is than the
#: last. The curve has to outrun what the previous act left you holding or
#: the first purchase is free and the act is over before it starts.
FIRST_COST = 1.0e44
COST_STEP = 40.0
#: Relief is cheaper than what it relieves, so both come out of one pot.
RELIEF_SHARE = 0.25
#: Progress per producer per second, and how far a single act has to go.
#: Both scale together, so the numbers grow era by era while the time an
#: act takes stays where `pace` puts it.
FIRST_YIELD = 1.0
YIELD_STEP = 2.2
#: Roughly how long one act should take, in game-seconds. Progress goes as
#: the square of the time spent, so this sets the target rather than the
#: other way round. The divisor is measured, not derived: the act does not
#: get all of the self-funding rate, because the relief line is bought out
#: of the same pot as the producers.
TARGET_SECONDS = 540.0
SELF_FUND_SHARE = 1.0 / 9.5
#: The shape of the constraint changes how long an act takes even when the
#: target is the same -- a decay act spends much of its output replacing
#: what leaked. These are measured against the harness, one per kind, so
#: `pace` stays a statement about this act rather than about its kind.
KIND_SCALE = {"throttle": 2.2098, "decay": 1.8832,
              "attrition": 2.0608, "contest": 1.0000}


def index_of(realm):
    return realm.number - 12


def producer_cost(realm):
    return FIRST_COST * COST_STEP ** index_of(realm)


def relief_cost(realm):
    return producer_cost(realm) * RELIEF_SHARE


def yield_of(realm):
    return FIRST_YIELD * YIELD_STEP ** index_of(realm)


def target_of(realm):
    """How far this act has to go, in its own units.

    Producers arrive at a roughly constant rate, so progress accumulates as
    the square of the time spent. The target is therefore set from the time
    the act is meant to take, not guessed and then measured.
    """
    from base.acts.rigs import UNITS_PER_SECOND
    seconds = TARGET_SECONDS * realm.pace
    producers = UNITS_PER_SECOND * SELF_FUND_SHARE * seconds
    raw = 0.5 * producers * yield_of(realm) * seconds
    return raw * KIND_SCALE[realm.kind]


def load_per_producer(realm):
    """What one producer asks of the relief line."""
    return 1.0


def relief_per_unit(realm):
    """What one unit of relief supplies. Relief is cheaper, so it is also
    individually weaker; otherwise buying one of each would settle it."""
    return 0.55


# --------------------------------------------------------------------------
# the hardware
# --------------------------------------------------------------------------
def rigs_of(realm):
    """(producer, relief) for this act, built once and cached in RIGS."""
    existing = RIGS.get(realm.number)
    if existing:
        return existing
    produce_attr, produce_label, produce_hint = realm.producer
    relieve_attr, relieve_label, relieve_hint = realm.relief
    pair = [
        Rig(produce_attr, produce_label, producer_cost(realm), "h",
            produce_hint),
        Rig(relieve_attr, relieve_label, relief_cost(realm), "j",
            relieve_hint),
    ]
    RIGS[realm.number] = pair
    return pair


def _counts(g, realm):
    produce_attr = realm.producer[0]
    relieve_attr = realm.relief[0]
    return getattr(g, produce_attr, 0.0), getattr(g, relieve_attr, 0.0)


def coverage(g, realm):
    """How much of the constraint the relief line is actually holding.

    1.0 means you are keeping up. Below that, the act's `kind` decides what
    it costs you.
    """
    producers, relief = _counts(g, realm)
    load = producers * load_per_producer(realm)
    if load <= 0:
        return 1.0
    capacity = relief * relief_per_unit(realm)
    return max(0.0, min(1.0, capacity / load))


def progress(g, realm):
    return getattr(g, realm.quantity, 0.0)


def fraction(g, realm):
    return min(1.0, progress(g, realm) / max(target_of(realm), 1e-9))


# --------------------------------------------------------------------------
# the tick, once, for all of them
# --------------------------------------------------------------------------
def _throttle(g, realm, dt, held):
    """Short of relief, everything simply runs slower."""
    producers, _relief = _counts(g, realm)
    gained = producers * yield_of(realm) * held * dt
    setattr(g, realm.quantity, progress(g, realm) + gained)


#: How fast progress leaks while relief is short. Kept gentle on purpose:
#: a steeper leak puts a hard ceiling close to the target, and an act whose
#: length swings from five minutes to seventeen on a small change to its
#: goal is balanced on a knife edge rather than balanced.
DECAY_RATE = 0.012


def _decay(g, realm, dt, held):
    """What you have built leaks away while relief is short."""
    producers, _relief = _counts(g, realm)
    gained = producers * yield_of(realm) * dt
    lost = progress(g, realm) * (1.0 - held) * DECAY_RATE * dt
    setattr(g, realm.quantity, max(0.0, progress(g, realm) + gained - lost))


def _attrition(g, realm, dt, held):
    """The producers themselves are destroyed, and stay destroyed."""
    produce_attr = realm.producer[0]
    producers, _relief = _counts(g, realm)
    gained = producers * yield_of(realm) * dt
    setattr(g, realm.quantity, progress(g, realm) + gained)
    burned = producers * (1.0 - held) * 0.06 * dt
    if burned > 0:
        setattr(g, produce_attr, max(0.0, producers - burned))
        g.units_lost += burned


#: A contested act slows as you take ground, but not to a stop -- a pure
#: share contest approaches the target and never arrives, which is a way of
#: saying the act cannot be finished.
CONTEST_FLOOR = 0.25


def _contest(g, realm, dt, held):
    """Something else holds the volume; you take it a share at a time."""
    producers, _relief = _counts(g, realm)
    theirs = max(CONTEST_FLOOR, 1.0 - fraction(g, realm))
    gained = producers * yield_of(realm) * held * theirs * dt
    setattr(g, realm.quantity, progress(g, realm) + gained)


KINDS = {"throttle": _throttle, "decay": _decay,
         "attrition": _attrition, "contest": _contest}


def tick_for(realm):
    run = KINDS[realm.kind]
    produce_rig, _relief_rig = rigs_of(realm)

    def tick(g, dt):
        run(g, realm, dt, coverage(g, realm))
        self_fund(g, produce_rig, dt)
    return tick


def complete_for(realm):
    target = target_of(realm)

    def done(g):
        return progress(g, realm) >= target * 0.99999
    return done


# --------------------------------------------------------------------------
# the panels, once, for all of them
# --------------------------------------------------------------------------
NOTES = {
    "throttle": ("throughput", "short of relief, everything runs slower"),
    "decay": ("holding", "short of relief, what you have built leaks away"),
    "attrition": ("survival", "short of relief, the producers are destroyed"),
    "contest": ("footing", "short of relief, you cannot press the advantage"),
}


def panels_for(realm):
    pair = rigs_of(realm)
    target = target_of(realm)
    label, note = NOTES[realm.kind]

    def panels(g):
        held = coverage(g, realm)
        done = fraction(g, realm)
        return [
            stock_panel(g),
            rig_panel(realm.name.split()[-1][:14].upper() or "HARDWARE",
                      pair, g),
            panel("CONSTRAINT", [
                row(label, f"{held * 100:.1f}%", bar=held, warn=held < 0.999,
                    hint=note),
                row(realm.unit,
                    f"{small(progress(g, realm))} of {small(target)}",
                    bar=done),
            ]),
        ]
    return panels


def material_for(realm):
    target = target_of(realm)

    def material(g):
        done = fraction(g, realm)
        return panel(realm.key.upper(), [
            row(realm.unit, small(progress(g, realm))),
            row("constraint held", f"{coverage(g, realm) * 100:.0f}%",
                warn=coverage(g, realm) < 0.999),
            row("done", f"{done * 100:.4f}%", bar=done),
        ])
    return material
