"""Price-grounding guard: every ₹ amount in Sara's reply must come from tool results or the user's message
(or simple arithmetic on them: sums, differences, small multiples and per-person splits)."""

import json
import re

AMOUNT = re.compile(r"₹\s?(\d{1,3}(?:[,    ]\d{2,3})+|\d+)")
NUMBER = re.compile(r"(?<![\w.])\d{3,9}(?![\w.])")


def amounts(text: str) -> list[int]:
    out = []
    for m in AMOUNT.findall(text or ""):
        v = int(re.sub(r"\D", "", m))
        if v >= 100:
            out.append(v)
    return out


def numbers_in(obj) -> set[int]:
    """All integers (>= 100) that appear in tool output (JSON strings or dicts)."""
    text = obj if isinstance(obj, str) else json.dumps(obj, default=str)
    nums = {int(n) for n in NUMBER.findall(text.replace(",", ""))}
    return {n for n in nums if n >= 100}


def allowed(base: set[int]) -> set[int]:
    vals = sorted(base)[:80]
    out = set(vals)
    for i, a in enumerate(vals):
        for k in range(2, 10):
            out.add(a * k)
            out.add(round(a / k))
        for b in vals[i + 1:]:
            out.add(a + b)
            out.add(abs(a - b))
    return out


def ungrounded(text: str, base: set[int], tolerance: int = 2) -> list[int]:
    ok = sorted(allowed(base))
    if not ok:
        return amounts(text)
    import bisect
    bad = []
    for v in amounts(text):
        i = bisect.bisect_left(ok, v)
        near = [ok[j] for j in (i - 1, i) if 0 <= j < len(ok)]
        if not any(abs(v - n) <= tolerance for n in near):
            bad.append(v)
    return bad
