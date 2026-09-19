"""Catching problems and showing them, instead of dumping a traceback.

Nothing here tries to make a broken game keep working. The aim is that when
something does go wrong you see what and where, inside the UI, with the
terminal still in a sane state and the run still on disk -- rather than a
stack trace and a lost session.
"""

import time
import traceback

from pclengine import paths

LOG_PATH = paths.CRASH_LOG
MAX_KEPT = 30


class Failure:
    __slots__ = ("where", "kind", "message", "trace", "when", "count")

    def __init__(self, where, exc):
        self.where = where
        self.kind = type(exc).__name__
        self.message = str(exc)
        self.trace = traceback.format_exc()
        self.when = time.time()
        self.count = 1

    @property
    def headline(self):
        return f"{self.kind}: {self.message}" if self.message else self.kind

    def lines(self):
        return [f"in {self.where}", "", self.headline, ""] + \
            self.trace.rstrip().splitlines()

    def as_dict(self):
        return {"where": self.where, "kind": self.kind,
                "message": self.message, "trace": self.trace,
                "count": self.count}


FAILURES = []


def capture(where, exc, log=True):
    """Record a failure. Repeats of the same one are counted, not piled up."""
    if FAILURES and FAILURES[-1].where == where \
            and FAILURES[-1].headline == f"{type(exc).__name__}: {exc}":
        FAILURES[-1].count += 1
        return FAILURES[-1]
    failure = Failure(where, exc)
    FAILURES.append(failure)
    del FAILURES[:-MAX_KEPT]
    if log:
        _write(failure)
    return failure


def _write(failure):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(f"\n==== {time.strftime('%Y-%m-%d %H:%M:%S')} "
                     f"in {failure.where} ====\n{failure.trace}")
    except OSError:
        pass            # a logging failure must not become the new problem


def latest():
    return FAILURES[-1] if FAILURES else None


def clear():
    del FAILURES[:]


def guarded(where, default=None):
    """Run a call, record anything it raises, and carry on.

        value = guarded("panel", default=[])(build_panel, game)
    """
    def call(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:          # noqa: BLE001 - that is the point
            capture(where, exc)
            return default
    return call


class Guard:
    """Context manager form. `Guard("tick")` swallows and records."""

    __slots__ = ("where", "failure")

    def __init__(self, where):
        self.where = where
        self.failure = None

    def __enter__(self):
        self.failure = None
        return self

    def __exit__(self, kind, exc, tb):
        if exc is None or isinstance(exc, (KeyboardInterrupt, SystemExit)):
            return False
        self.failure = capture(self.where, exc)
        return True                        # handled

    def __bool__(self):
        return self.failure is not None
