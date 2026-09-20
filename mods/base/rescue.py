"""The emergency loan: FOUNDRY's way out of a corner it let you build.

Act II prices its drones in finished chips rather than money, and nothing
stops you spending the whole stock on miners that have no power to run on.
Miners with no power make no chips; no chips means no array; no array means
no power. The run is over and the clock keeps going.

Rather than forbid the purchase -- overbuying the wrong thing is a real and
fair way to lose a few minutes -- the fab's bank notices the line has been
dead for two minutes and offers to cover it. Money on those terms is not
free: the loan is repaid out of production, at a rate you feel.
"""

import math

from pclengine.core import rescue


#: What fraction of everything you produce goes to the bank until the debt
#: is clear. A quarter hurts enough to be a bailout rather than a bonus.
GARNISH = 0.25
#: What you pay back per unit borrowed. The bank is helping, not a charity.
INTEREST = 2.0
#: How much slack the loan buys, as a multiple of the bare minimum needed
#: to restart. Bare minimum would restart the fab and instantly re-strand
#: it on the next purchase, which is a rescue in name only.
HEADROOM = 1.5


#: What the Act II bailout hands over, flat. Sizing it off the chain gave
#: millions of chips -- enough to buy the act back rather than to restart
#: it. A fixed, legible figure you can plan against is the better bargain:
#: it restarts the line and leaves the climb to you.
ACT_TWO_LOAN = 100_000.0


def _need(g):
    """What the loan hands over, and which purse it lands in.

    Act I buys wafers with money; from Act II the purse is finished chips.
    """
    if g.act < 2:
        # Enough for a lot of wafers and the stepper to run them through.
        return max(g.spot_price * 20.0, g.stepper_cost) * HEADROOM, "funds"
    return ACT_TWO_LOAN, "unsold"


def _idle_not_stuck(g):
    """True when there is still an affordable move that leads somewhere.

    Sitting at the opening screen without touching anything looks exactly
    like a softlock to a stopwatch -- no number moves -- but a fab with
    money in the bank and a wafer market open is not stranded, it is just
    not being played. Only the absence of any move is a corner.
    """
    if g.act < 2:
        return g.wafers >= 1 or g.funds >= g.spot_price
    return False


def _offer(g):
    """Build the loan, or decline because they are idle rather than stuck."""
    if g.finished or _idle_not_stuck(g):
        return None
    amount, purse = _need(g)
    if amount <= 0 or amount == float("inf"):
        return None
    # Already able to pay for the fix themselves? Then the line is stopped
    # because they stopped it, and that is their business.
    if getattr(g, purse) >= amount:
        return None
    unit = "¤" if purse == "funds" else "chips"
    owed = amount * INTEREST

    def accept(game):
        setattr(game, purse, getattr(game, purse) + amount)
        game.debt += owed
        game.log(f"Emergency loan: {amount:,.0f} {unit}. "
                 f"You owe {owed:,.0f}.")

    if g.act < 2:
        why = "The fab has no wafers and no money to buy any."
        fix = "enough to buy wafers and run them through"
    else:
        why = "Your line has stalled, and no chips left to restart it."
        fix = "a fixed advance against the line getting going again"
    return rescue.Offer(
        headline=why,
        terms=(f"Borrow {amount:,.0f} {unit}; repay {owed:,.0f} "
               f"at {GARNISH * 100:.0f}% of output."),
        accept=accept,
        detail=("Nothing you own has produced anything for two minutes.",
                f"The bank will advance {fix}.",
                "Production is garnished until the debt is clear.",
                "If it is not enough, they will lend again."))


def repay(g, dt):
    """Take the bank's cut of whatever was produced this tick."""
    if g.debt <= 0:
        return
    made = g.made_rate * dt
    if made <= 0:
        return
    cut = min(g.debt, made * GARNISH)
    if g.act < 2:
        # Before Act II the cut lands on the sale, not the stock, so it is
        # taken as the chips reach the warehouse.
        g.unsold = max(0.0, g.unsold - cut)
    else:
        g.unsold = max(0.0, g.unsold - cut)
    g.debt -= cut
    if g.debt <= 0:
        g.debt = 0.0
        g.log("The emergency loan is repaid.")


def install(api):
    api.field("debt", 0.0)
    # Several, because any one of them moving means the run is alive, and
    # only all of them standing still is a softlock: a fab that is mining
    # but not yet smelting is making progress and must not be interrupted.
    # Research is deliberately absent -- it climbs in a dead fab, which is
    # exactly how a check like this misses the state it exists to catch.
    api.progress_metric(lambda g: g.chips)
    api.progress_metric(lambda g: g.acquired)
    api.progress_metric(lambda g: g.wafers)
    api.progress_metric(lambda g: g.funds)
    api.rescue_offer(_offer)
    api.system_tick(repay)
