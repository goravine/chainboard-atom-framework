"""Example atom — replace with your project's leaf-level IO.

An atom is a focused leaf operation. Inputs and outputs are explicit; no
config lookups, no upward imports, no policy decisions.

This file exists to show the shape. Delete and replace with real atoms
(e.g., db.py, gcs.py, sheets.py) as your project grows.
"""

from __future__ import annotations


def echo(payload: str) -> str:
    """Return the input verbatim. The simplest possible atom."""
    return payload


def upper_echo(payload: str) -> str:
    """Return the input uppercased. Demonstrates that atoms can do pure
    transformation — but never policy."""
    return payload.upper()
