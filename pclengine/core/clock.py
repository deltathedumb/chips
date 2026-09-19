"""Advancing the simulation without losing time.

A frame loop that just calls `tick(frame_delta)` drifts: clamp the delta and
the game silently runs slow whenever anything stutters; do not clamp it and a
single long pause lands as one enormous step.

`advance` covers the whole elapsed span either way. Normally it runs several
small fixed steps. When the caller has fallen behind it runs the same capped
number of steps but makes each one longer, so a lagging game stays on the
right clock instead of quietly falling behind it.
"""

STEP = 0.05          # the step we would like to take, in seconds
MAX_STEPS = 64       # most sub-steps one call will run before widening them


def advance(game, elapsed, step=STEP, max_steps=MAX_STEPS):
    """Run `elapsed` seconds of simulation. Returns how many steps it took."""
    if elapsed <= 0:
        return 0
    steps = int(elapsed / step)
    if steps < 1:
        steps = 1
    elif steps > max_steps:
        steps = max_steps          # same span, longer steps
    slice_dt = elapsed / steps
    for _ in range(steps):
        game.tick(slice_dt)
    return steps


class Pacer:
    """Tracks real time across frames so nothing between them is dropped."""

    def __init__(self, step=STEP, max_steps=MAX_STEPS):
        self.step = step
        self.max_steps = max_steps
        self.debt = 0.0            # simulated seconds still owed
        self.behind = False        # True while we are widening steps to keep up

    def frame(self, game, real_delta):
        self.debt += max(0.0, real_delta)
        if self.debt < self.step:
            return 0
        owed = self.debt
        self.debt = 0.0
        self.behind = owed > self.step * self.max_steps
        return advance(game, owed, self.step, self.max_steps)
