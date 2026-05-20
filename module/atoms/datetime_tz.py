"""datetime_tz — UTC → local-timezone display.

The framework's storage discipline is "DB is UTC, render is local." This
atom owns the conversion. See docs/USE_CASES.md §2 for the full doctrine.

Use it at every render boundary that surfaces a stored timestamp to a
user: sheet writes, notification messages, server-rendered HTML. Pair
with a scanner rule for browser-side renders (Intl.DateTimeFormat /
.toLocale*).

This atom has no config lookup and no project-specific defaults. The
caller passes the target timezone name. Project code typically wraps
this with a single configured TZ:

    from module.atoms.datetime_tz import format_in_tz
    DISPLAY_TZ = "Asia/Jakarta"
    def to_display(ts): return format_in_tz(ts, DISPLAY_TZ)
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def format_in_tz(
    value,
    tz_name: str,
    *,
    fmt: str = "%Y-%m-%d %H:%M:%S",
    suffix: str = "",
) -> str:
    """Convert a UTC-anchored timestamp string to local-timezone wall time.

    Inputs accepted:
      - ISO 8601 strings with explicit offset ("...Z" / "...+00:00")
      - Naive strings, assumed UTC (matches the storage rule)
      - datetime objects (TZ-aware or naive)
      - Falsy values → ""

    Unparseable strings pass through unchanged. A malformed cell stays
    visible rather than silently blanking — easier to find the bug.

    `suffix` is appended after the formatted time when set; pass the
    timezone abbreviation you want displayed (e.g. "WIB", "JST").
    """
    if value is None or value == "":
        return ""

    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return ""
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    local = dt.astimezone(ZoneInfo(tz_name))
    rendered = local.strftime(fmt)
    return f"{rendered} {suffix}".rstrip() if suffix else rendered


def utc_now_iso() -> str:
    """TZ-aware UTC timestamp ('...Z' suffix), the storage-side counterpart.

    Use this anywhere project code would otherwise write `datetime.now()`.
    Naive local-time strings leaking into storage are the producer side
    of the "double-shift" bug described in docs/USE_CASES.md §2.
    """
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
