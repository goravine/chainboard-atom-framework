"""Service gate — the stable orchestration surface.

This file is the public service entry point. External callers (SDK, api_app,
boards, tools) must import from here, not from the private children
(`module/services_*.py`).

The scanner enforces this via the service-gate boundary rule.

Rules for this file:
  - Stay small: maximum 350 lines / 20 functions (enforced).
  - Re-export from private children rather than implementing here.
  - Implementation lives in `module/services_<domain>.py` files.
  - Adding a new orchestration domain? Create a new `services_<domain>.py`
    child and add re-exports here.

Seed contents below are deliberately minimal. Grow as your project grows.
"""

from module.services_example import (
    run_example_workflow,
)

__all__ = [
    "run_example_workflow",
]
