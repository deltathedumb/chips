"""What FOUNDRY prices its projects in.

Three things, in the order the HUD shows them: bytes of data the fab
network produced, entropy distilled out of a saturated buffer, and finished
chips you have not sold. The engine knows none of these by name.
"""

from pclengine.core.acts import row
from pclengine.core.currency import Currency
from pclengine.fmt import big, money, size, small

CURRENCIES = [
    # Money is not a project currency, but labs are bought with it in Act I
    # and the panel needs to know how to write it.
    Currency("funds", "funds", money),
    Currency("data", "data", size),
    Currency("entropy", "entropy", lambda n: f"{big(n, 1)} entropy"),
    # Chips are spent out of the unsold stock, not the lifetime total.
    Currency("chips", "unsold", lambda n: f"{big(n, 1)} chips"),
]


def _burst_row(g):
    """The manual compute burst, shown under the research panel."""
    if not g.can("burst"):
        return None
    return row(f"Overclock Burst  t{g.burst_level}",
               f"{small(g.burst_cost)} entropy", key="u",
               hint=f"{g.burst_seconds:,.0f}s of output every "
                    f"{g.burst_cooldown:,.0f}s")


def install(api):
    for spec in CURRENCIES:
        api.add_currency(spec)
    # Act I pays for labs out of revenue; later acts pay in chips.
    api.lab_currency(lambda g: "funds" if g.act < 2 else "chips")
    api.research_row(_burst_row)
