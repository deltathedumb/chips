"""Derived numbers: what a stepper costs, what a wafer is worth.

These are properties on the engine's Game, which is why they are written
with `self` even though they live in a mod.
"""


from pclengine.core.state import scaled_price

from base import constants

#: Operations you get per byte of compute you send that way instead.
OPS_PER_BYTE = 1.0


@property
def node(self):
    """Smallest process node you have brought up, in nanometres."""
    nm = constants.START_NODE
    for project_id, size in constants.NODES:
        if project_id in self.completed:
            nm = size
    return nm


@property
def buffer_bytes(self):
    return self.buffer * 2000


@property
def compute_rate(self):
    """Everything your threads and accelerators turn out per second.

    Threads are throttled by bandwidth: buying more past the ceiling still
    helps, but each one carries less. Accelerators have their own link and
    are not throttled, which is most of why they are worth having.

    The total is split between the data buffer and the benchmark circuit's
    ops by `ops_share`, so the two are the same compute spent two ways.
    """
    r = self.threads * 25.0 * self.thread_perf * self.bandwidth_ratio
    r += self.accelerators * 250.0
    if self.telemetry:
        r += (self.miners + self.pullers) ** 0.5 * 10.0
    return r


@property
def data_rate(self):
    """Bytes into the buffer: whatever is not going into ops."""
    return self.compute_rate * max(0.0, 1.0 - self.ops_share)


@property
def ops_rate(self):
    """Operations into the benchmark circuit, if you have opened it."""
    if not self.can("ops"):
        return 0.0
    return self.compute_rate * self.ops_share * OPS_PER_BYTE


@property
def stepper_cost(self):
    return scaled_price(5.0 * 1.1 ** self.steppers, self.hw_scale)


@property
def scanner_cost(self):
    return scaled_price(500.0 * 1.07 ** self.scanners, self.hw_scale)


@property
def design_win_cost(self):
    return scaled_price(100.0 * 2.0 ** (self.design_wins - 1),
                        self.hw_scale)

# -- the manual compute burst ------------------------------------------
# Dumps a slab of data into the buffer at once, then has to recharge.
# Entropy buys bigger slabs and a shorter wait.
