"""BoardBase — the capability-surface contract.

Every Board in this framework inherits from BoardBase. The base class enforces
two things:

  1. **Gate state**: a board can be `open` or `closed`. Methods on the board
     must call `_assert_gate_open()` before doing work. When closed, the
     board may expose a `_fallback_*` method instead of failing — this is the
     "intentional degraded mode" pattern (e.g., cache-only reads when an
     upstream service is unreachable).

  2. **Dependency boundary**: a board can declare other boards as `deps`. On
     each method entry, `_assert_deps_open()` confirms all listed dependencies
     are also `open`. This prevents silent cascades where a closed downstream
     board produces nonsense data through an upstream board that "happens to
     still work."

A board should NOT contain orchestration logic. Boards are capability surfaces
that delegate to `module.services` (the stable service gate). See PROTOCOL.md.
"""

from sdk.exceptions import FrameworkError


class BoardBase:
    def __init__(self, deps=None):
        self.gate = "open"
        self.deps = deps or []

    def _assert_gate_open(self):
        if self.gate != "open":
            raise FrameworkError(f"{self.__class__.__name__} gate is closed")

    def _assert_deps_open(self):
        for dep in self.deps:
            if dep.gate != "open":
                raise FrameworkError(
                    f"{self.__class__.__name__}: dependency "
                    f"{dep.__class__.__name__} gate is closed"
                )
