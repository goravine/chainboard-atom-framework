"""idempotent_hook — fire-once-per-identity external side effects.

Wraps the "persistent seen set" pattern described in docs/USE_CASES.md §4:
a side effect (notification, webhook, "tell the outside world") must fire
at most once per content identity, regardless of how many times the
producing pipeline re-runs the row.

The atom owns the set's persistence, the locking, and the failure
isolation. It does NOT own the action or the identity scheme — both come
from the caller, which knows the domain.

Storage backend here is a JSON file. Swap for SQLite / Redis / Postgres
by writing a parallel atom; the public shape (`fire_once`) stays the same.

Example:

    from module.atoms.idempotent_hook import fire_once

    fire_once(
        identity=request_id,
        store_path="/var/lib/app/notified.json",
        action=lambda: send_telegram(message),
    )

Calling `fire_once` after the side effect has already happened for that
identity is a silent no-op. Failures in storage or the action are
swallowed — the surrounding pipeline must not break because the hook
couldn't fire.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Callable, Iterable


# Process-wide lock per store path. Concurrent calls within one process
# (e.g. retry worker + foreground submit) need this; the rename-on-write
# below covers the cross-process case.
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(path: str) -> threading.Lock:
    with _LOCKS_GUARD:
        lk = _LOCKS.get(path)
        if lk is None:
            lk = threading.Lock()
            _LOCKS[path] = lk
        return lk


def _load_set(path: str) -> set[str]:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return set()
    if isinstance(data, list):
        return {str(x) for x in data}
    return set()


def _save_set(path: str, identities: Iterable[str]) -> None:
    """Write the set atomically — temp file + rename, so a crash mid-write
    leaves the previous state intact, not a truncated file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(sorted(identities), fh)
    os.replace(tmp, path)


def fire_once(
    *,
    identity: str,
    store_path: str,
    action: Callable[[], None],
) -> bool:
    """Run `action` iff `identity` has not been fired before.

    Returns True when the action ran, False when it was skipped (already
    fired) or when the hook itself failed. The caller's pipeline must
    not branch on the return — this is fire-and-forget; the return is
    informational only (e.g. for logging).

    Failure is swallowed: a storage error, a permission error, or an
    exception inside `action` will not propagate. The whole point of an
    "external side effect hook" is that the row write doesn't care if
    the notification got through.
    """
    try:
        key = str(identity or "").strip()
        if not key:
            return False
        with _lock_for(store_path):
            seen = _load_set(store_path)
            if key in seen:
                return False
            action()
            seen.add(key)
            _save_set(store_path, seen)
            return True
    except Exception:
        return False


def has_fired(identity: str, store_path: str) -> bool:
    """Read-only check — useful for tests and admin diagnostics."""
    return str(identity or "").strip() in _load_set(store_path)
