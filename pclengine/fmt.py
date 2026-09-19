"""Number formatting for very large quantities."""

_SCALE = [
    "", " thousand", " million", " billion", " trillion", " quadrillion",
    " quintillion", " sextillion", " septillion", " octillion", " nonillion",
    " decillion", " undecillion", " duodecillion", " tredecillion",
    " quattuordecillion", " quindecillion", " sexdecillion", " septendecillion",
    " octodecillion", " novemdecillion", " vigintillion",
]


def big(n, places=3):
    """1284991 -> '1.285 million'. Small values keep comma grouping."""
    n = float(n)
    if n != n:
        return "?"
    if abs(n) == float("inf"):
        return "-infinity" if n < 0 else "infinity"
    neg = n < 0
    n = abs(n)
    if n < 1_000_000:
        out = f"{int(n):,}"
    else:
        exp = 0
        while n >= 1000 and exp < len(_SCALE) - 1:
            n /= 1000.0
            exp += 1
        out = f"{n:,.{places}f}{_SCALE[exp]}"
    return ("-" + out) if neg else out


def small(n):
    """Compact form for HUD counters: '4.2k', '18.3M'."""
    n = float(n)
    if n != n:
        return "?"
    neg = n < 0
    n = abs(n)
    if n == float("inf"):
        return "-"
    for limit, suffix in ((1e0, ""), (1e3, "k"), (1e6, "M"), (1e9, "G"),
                          (1e12, "T"), (1e15, "P"), (1e18, "E"), (1e21, "Z"),
                          (1e24, "Y"), (1e27, "R"), (1e30, "Q")):
        if n < limit * 1000:
            v = n / limit
            s = f"{v:,.0f}{suffix}" if (v >= 100 or not suffix) else f"{v:,.1f}{suffix}"
            return ("-" + s) if neg else s
    mantissa, exponent = f"{n:.1e}".split("e")
    return f"{mantissa}e{int(exponent)}"


def money(n):
    n = float(n)
    if n != n:
        return "$?"
    if abs(n) == float("inf"):
        return "$-"
    if abs(n) < 1_000_000:
        return f"${n:,.2f}"
    return "$" + big(n, 2)


def rate(n, unit="/sec"):
    n = float(n)
    if n == 0:
        return "0" + unit
    if n < 1000:
        return f"{n:,.1f}{unit}"
    return big(n, 2) + unit


def dur(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


_BYTES = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]


def size(n):
    """Bytes for the HUD: 750 -> '750 B', 26000 -> '26.0 KB'."""
    n = float(n)
    if n != n:
        return "?"
    if abs(n) == float("inf"):
        return "-"
    if n < 1000:
        return f"{n:,.0f} B"
    for i, unit in enumerate(_BYTES[1:], start=1):
        n /= 1000.0
        if n < 1000 or i == len(_BYTES) - 1:
            return f"{n:,.1f} {unit}" if n < 100 else f"{n:,.0f} {unit}"
    return f"{n:.1e} B"
