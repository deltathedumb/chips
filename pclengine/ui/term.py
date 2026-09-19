"""Raw-mode terminal control: alternate screen, flicker-free redraw,
non-blocking single-keypress input. Windows (msvcrt) and POSIX (termios)."""

import os
import shutil
import sys

CSI = "\x1b["
IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    import msvcrt
    _WIN_SPECIAL = {
        "H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT",
        "G": "HOME", "O": "END", "S": "DEL",
    }
else:
    import select
    import termios
    import tty

_ESC_SPECIAL = {
    "A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT",
    "H": "HOME", "F": "END",
}


def _enable_windows_vt():
    """Turn on ANSI escape processing for legacy consoles."""
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = wintypes.DWORD()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


class Terminal:
    def __init__(self):
        self._old = None
        self._prev = []
        self.width = 80
        self.height = 30

    # -- lifecycle ---------------------------------------------------------
    def open(self):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        if IS_WINDOWS:
            _enable_windows_vt()
        else:
            fd = sys.stdin.fileno()
            self._old = termios.tcgetattr(fd)
            tty.setcbreak(fd)
        sys.stdout.write(CSI + "?1049h" + CSI + "?25l" + CSI + "2J")
        sys.stdout.flush()
        self.measure()

    def close(self):
        sys.stdout.write(CSI + "?25h" + CSI + "?1049l")
        sys.stdout.flush()
        if not IS_WINDOWS and self._old is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._old)
            self._old = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    # -- output ------------------------------------------------------------
    def measure(self):
        size = shutil.get_terminal_size(fallback=(80, 30))
        self.width, self.height = size.columns, size.lines
        return self.width, self.height

    def render(self, lines):
        """Redraw the screen. Only rewrites rows that actually changed."""
        out = [CSI + "?25l"]
        if len(lines) != len(self._prev):
            out.append(CSI + "2J")
            self._prev = [None] * len(lines)
        for i, line in enumerate(lines):
            if line != self._prev[i]:
                out.append(f"{CSI}{i + 1};1H{line}{CSI}0m{CSI}K")
        self._prev = list(lines)
        sys.stdout.write("".join(out))
        sys.stdout.flush()

    def invalidate(self):
        self._prev = []

    # -- input -------------------------------------------------------------
    def keys(self):
        """Return every keypress buffered since the last call."""
        return self._keys_windows() if IS_WINDOWS else self._keys_posix()

    def _keys_windows(self):
        out = []
        while msvcrt.kbhit():
            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                nxt = msvcrt.getwch()
                name = _WIN_SPECIAL.get(nxt)
                if name:
                    out.append(name)
            else:
                out.append(self._normalize(ch))
        return out

    def _keys_posix(self):
        fd = sys.stdin.fileno()
        data = ""
        while select.select([fd], [], [], 0)[0]:
            chunk = os.read(fd, 1024)
            if not chunk:
                break
            data += chunk.decode("utf-8", "replace")
        out, i = [], 0
        while i < len(data):
            ch = data[i]
            if ch == "\x1b" and i + 2 < len(data) and data[i + 1] == "[":
                name = _ESC_SPECIAL.get(data[i + 2])
                if name:
                    out.append(name)
                    i += 3
                    continue
            out.append(self._normalize(ch))
            i += 1
        return out

    @staticmethod
    def _normalize(ch):
        if ch in ("\r", "\n"):
            return "ENTER"
        if ch == "\t":
            return "TAB"
        if ch == "\x1b":
            return "ESC"
        if ch in ("\x7f", "\x08"):
            return "BACKSPACE"
        if ch == "\x03":
            return "CTRL-C"
        return ch
