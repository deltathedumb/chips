"""The machine you run the fab on: bandwidth, threads, buffer, bursts.

Bandwidth is the budget; threads turn it into data and the buffer decides
how much data you can hold at once, which is what the project tree is
priced against. The burst spends a slab of it at once, on a cooldown.
"""


BURST_SECONDS = 30.0


BURST_COOLDOWN = 12.0


@property
def burst_seconds(self):
    """How many seconds of thread output one press is worth."""
    return self.BURST_SECONDS * (1.0 + self.burst_level * 0.6)


@property
def burst_cooldown(self):
    # Measured in game seconds, so a slowed clock does not turn a
    # twelve second wait into half a minute of real time.
    scale = max(0.1, getattr(self, "time_scale", 1.0))
    return max(2.0, self.BURST_COOLDOWN * 0.86 ** self.burst_level * scale)


@property
def burst_cost(self):
    return 25.0 * 2.2 ** self.burst_level * self.cost_scale


@property
def burst_yield(self):
    return self.data_rate * self.burst_seconds


def fire_burst(self):
    """Returns the bytes added, or 0 if it is still recharging."""
    if self.burst_cd > 0 or not self.can("burst"):
        return 0.0
    gained = min(self.burst_yield, self.buffer_bytes - self.data)
    self.data += gained
    self.burst_cd = self.burst_cooldown
    self.bursts_fired += 1
    return gained


def upgrade_burst(self):
    if self.entropy < self.burst_cost:
        return False
    self.entropy -= self.burst_cost
    self.burst_level += 1
    self.log(f"Burst overclocked to tier {self.burst_level}: "
             f"{self.burst_seconds:,.0f}s of compute every "
             f"{self.burst_cooldown:,.0f}s.")
    return True


@property
def free_bandwidth(self):
    """Headroom: how many more threads the network will actually carry.

    Not a purse any more. You can always buy another thread; bandwidth
    decides how much of what you own is allowed to talk.
    """
    return max(0, self.bandwidth - self.threads)


@property
def bandwidth_ratio(self):
    """How much of your thread floor is running, 0 to 1.

    Past the ceiling every thread runs slower rather than some of them
    stopping, which is the same shape as the power shortfall in Act II --
    one idea to learn, applied twice.
    """
    if self.threads <= 0:
        return 1.0
    return min(1.0, self.bandwidth / float(self.threads))
