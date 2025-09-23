from typing import Optional, Tuple

def _parse_hhmm(s: Optional[str]) -> Optional[Tuple[int, int]]:
    """'HH:MM' -> (hour, minute) or None"""
    if not s or not isinstance(s, str) or ":" not in s:
        return None
    try:
        h, m = s.split(":")
        h = int(h); m = int(m)
        if 0 <= h < 24 and 0 <= m < 60:
            return h, m
    except Exception:
        return None
    return None


def _minutes_between(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return (b[0] * 60 + b[1]) - (a[0] * 60 + a[1])


def _overlap_minutes(a_start, a_end, b_start, b_end) -> int:
    """Same-day overlap minutes (no overnight)."""
    a1 = a_start[0] * 60 + a_start[1]
    a2 = a_end[0] * 60 + a_end[1]
    b1 = b_start[0] * 60 + b_start[1]
    b2 = b_end[0] * 60 + b_end[1]
    lo = max(a1, b1)
    hi = min(a2, b2)
    return max(hi - lo, 0)