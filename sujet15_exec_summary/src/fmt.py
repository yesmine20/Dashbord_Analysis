"""Number formatting. Every figure sent to the LLM carries a 'value' and a 'display' string."""


def usd_str(v: float) -> str:
    a = abs(v)
    sign = "-" if v < 0 else ""
    if a >= 999_500:
        return f"{sign}${a / 1e6:.2f}M"
    if a >= 1_000:
        return f"{sign}${a / 1e3:.0f}K"
    return f"{sign}${a:.0f}"


def usd(v: float) -> dict:
    return {"value": round(float(v), 2), "display": usd_str(float(v))}


def pct(v: float) -> dict:
    return {"value": round(float(v), 1), "display": f"{float(v):.1f}%"}


def pts(v: float) -> dict:
    return {"value": round(float(v), 1), "display": f"{float(v):.1f} pts"}
