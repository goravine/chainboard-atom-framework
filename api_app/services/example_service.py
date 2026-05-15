"""api_app-side service wrapper for the example router.

This thin wrapper sits between routers and `module.services`. It exists to:
  - shape the HTTP response (e.g., raise HTTPException on specific service errors)
  - keep routers free of orchestration logic
  - present an SDK-style method surface that's easy to unit test

For real projects, replace with a service class that wraps the relevant SDK
methods + module.services calls.
"""

from __future__ import annotations

from module.services import run_example_workflow


def run(payload: str) -> str:
    result = run_example_workflow(payload)
    return result.value
