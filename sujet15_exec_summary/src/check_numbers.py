"""Automatic guardrail: every figure written by the LLM must exist in the JSON it received.

Method: extract numeric tokens from the text (those with $, %, M/K, pts, thousands separators or
decimals), convert them to values and look for a matching number in the JSON, within the rounding
precision implied by how the token was written ("$1.49M" -> +/- $5,000).
Plain integers and years (e.g. "3 paragraphs", "2018") are ignored.
This check REDUCES hallucination risk, it does not prove absence of errors: a human still validates.
"""
import re

TOKEN = re.compile(
    r"(?P<cur>\$)?(?P<int>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<dec>\d+))?"
    r"\s?(?P<unit>[MKk]\b|%|pts?\b|pp\b|percentage points?\b|million\b|thousand\b|billion\b)?"
)
SCALE = {"m": 1e6, "million": 1e6, "k": 1e3, "thousand": 1e3, "billion": 1e9}


def json_numbers(obj, acc=None):
    acc = [] if acc is None else acc
    if isinstance(obj, bool):
        return acc
    if isinstance(obj, (int, float)):
        acc.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            json_numbers(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            json_numbers(v, acc)
    return acc


def extract_tokens(text: str):
    """Yield (raw_text, value, precision) for numeric tokens that must be grounded."""
    for m in TOKEN.finditer(text):
        cur, ip, dec, unit = m.group("cur"), m.group("int"), m.group("dec"), (m.group("unit") or "").lower()
        has_comma = "," in ip
        if not (cur or unit or has_comma or dec):
            continue                                   # plain integer / year / id: ignored
        value = float(ip.replace(",", "") + ("." + dec if dec else ""))
        scale = SCALE.get(unit, 1.0)
        value *= scale
        precision = 0.5 * (10 ** -(len(dec) if dec else 0)) * scale
        yield m.group(0).strip(), value, max(precision, 1e-6)


def check_text(text: str, payload: dict) -> dict:
    nums = [abs(x) for x in json_numbers(payload)]
    checked, bad = 0, []
    for raw, value, prec in extract_tokens(text):
        checked += 1
        if not any(abs(value - n) <= prec * 1.0001 for n in nums):
            bad.append({"text": raw, "value": value})
    return {"numbers_checked": checked, "ungrounded": bad, "ok": not bad}
