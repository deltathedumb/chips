"""Taping out: what a finished run leaves behind.

Prestige used to be a flat multiplier. It is now a currency and a shop: a run
earns MASK CREDITS for how far and how well it went, and those buy permanent
changes to how the next run starts. The point is that the upgrades are worth
choosing between, not just accumulating -- the early ones are cheap and the
late ones cost more than one good run will earn.
"""


#: fn(game) -> extra mask credits, for what content thinks a run was worth.
CREDIT_BONUSES = []


def add_credit_bonus(fn):
    CREDIT_BONUSES.append(fn)
    return fn


def credits_earned(g):
    """What this run is worth. Depth counts most; doing it well counts too."""
    reached = max(1, g.act)
    credits = (reached - 1) * 8.0
    if g.finished and not g.defeated:
        credits += 20.0
    if g.defeated:
        credits *= 0.4                       # a lost run still teaches you
    # Holding your ground and leaving a well-aligned successor both pay.
    credits += g.lowest_integrity * 10.0
    credits += getattr(g, "alignment", 0.0) * 15.0
    credits += min(10.0, len(g.completed) / 8.0)
    for bonus in CREDIT_BONUSES:
        try:
            credits += float(bonus(g))
        except Exception:                    # a broken mod earns you nothing
            continue
    return round(credits, 1)


class Upgrade:
    __slots__ = ("key", "name", "blurb", "cost", "apply", "repeatable", "cap")

    def __init__(self, key, name, blurb, cost, apply, repeatable=False, cap=1):
        self.key = key
        self.name = name
        self.blurb = blurb
        self.cost = cost
        self.apply = apply
        self.repeatable = repeatable
        self.cap = cap

    def owned(self, legacy):
        return int(legacy.get(self.key, 0))

    def price(self, legacy):
        return self.cost * (2.0 ** self.owned(legacy) if self.repeatable else 1)

    def maxed(self, legacy):
        return self.owned(legacy) >= self.cap


#: What taping out can buy you. Content fills this in.
UPGRADES = []
BY_KEY = {}


def add_upgrade(upgrade):
    UPGRADES.append(upgrade)
    BY_KEY[upgrade.key] = upgrade
    return upgrade


def reset():
    del UPGRADES[:], CREDIT_BONUSES[:]
    BY_KEY.clear()


def affordable(g, upgrade):
    return (not upgrade.maxed(g.legacy)
            and g.mask_credits >= upgrade.price(g.legacy))


def buy(g, key):
    upgrade = BY_KEY.get(key)
    if upgrade is None or not affordable(g, upgrade):
        return False
    g.mask_credits -= upgrade.price(g.legacy)
    g.legacy[key] = upgrade.owned(g.legacy) + 1
    g.log(f"Legacy: {upgrade.name} (now {g.legacy[key]})")
    return True


def apply_legacy(g):
    """Stamp everything bought in previous runs onto a fresh game."""
    for upgrade in UPGRADES:
        count = upgrade.owned(g.legacy)
        if count:
            try:
                upgrade.apply(g, count)
            except Exception:       # a bad upgrade must not block a new run
                continue
    return g


def summary_rows(g):
    return [("mask credits", f"{g.mask_credits:,.1f}"),
            ("generation", str(g.generation)),
            ("legacy bought", str(sum(int(v) for v in g.legacy.values())))]
