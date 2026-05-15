"""SDK — the stable object-facing layer.

This is where your project exposes object-style APIs to api_app / external
consumers. Each SDK class wraps `module.services` calls into a method-call
surface that's stable across refactors of the service implementation.

The seed file is empty; add SDK classes as your project grows. Each class
should:
  - import only from `module.services` (the gate), not from `module/services_*`
  - never import from `module/atoms/*` (the scanner enforces this)
  - present a small, stable surface that hides the orchestration layer
"""

from sdk.exceptions import (
    FrameworkError,
    FrameworkConfigError,
    FrameworkAuthError,
    FrameworkChainError,
    FrameworkStorageError,
)

__all__ = [
    "FrameworkError",
    "FrameworkConfigError",
    "FrameworkAuthError",
    "FrameworkChainError",
    "FrameworkStorageError",
]
