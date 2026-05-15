"""Example orchestration — shows how to compose atoms via a ChainResult.

This is a *private child* of the service gate. External callers must NOT
import from `module.services_example` directly — they import from
`module.services` which re-exports.

The scanner enforces this gate boundary.
"""

from __future__ import annotations

from module._chain import ChainResult
from module.atoms.example_io import echo, upper_echo


def run_example_workflow(payload: str):
    """Orchestrate a tiny two-step workflow using ChainResult.

    The scanner validates this chain at import time:
      - starts with `.of(...)` (✓)
      - straight-line construction (✓)
      - unique step names (echo, upper_echo are distinct) (✓)
      - no `.on(...)` registered after `.pipe(...)` (no observers here) (✓)
    """
    result = (
        ChainResult.of(payload)
        .pipe(echo)
        .pipe(upper_echo)
        .collect()
    )
    return result
