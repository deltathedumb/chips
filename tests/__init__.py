"""Regression tests for FOUNDRY.

    python foundry.py --test          run everything
    python -m unittest discover -s tests

These exist because this game has been changed faster than it could be
checked by hand: several "fixes" during development broke something else and
were only caught by luck. Anything that has broken once should be asserted
here.
"""

import atexit
import os
import shutil
import tempfile

from pclengine.store import save as _save

# The suite presses every key in every act, and one of those keys is "S",
# which calls save.save(g) with no path -- the player's real game file.
# This ran for a long time before anyone noticed, and it destroyed a save.
#
# The redirect lives here rather than in the --test runner so that it holds
# however the suite is started: unittest discover, pytest, an IDE.
_SANDBOX = tempfile.mkdtemp(prefix="foundry-test-")
_save.SAVE_BASE = os.path.join(_SANDBOX, "test")
atexit.register(shutil.rmtree, _SANDBOX, ignore_errors=True)
