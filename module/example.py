"""ExampleBoard — capability surface demonstrating the Board pattern.

A Board:
  - inherits from BoardBase
  - declares dependencies on other boards (here: none)
  - enforces gate state on every method
  - delegates orchestration to `module.services`
  - may provide a `_fallback_*` method for closed-gate behavior

Delete this file and `module/services_example.py` once you've created your
own Board(s). Don't forget to update `module/__init__.py` exports too.
"""

from module._base import BoardBase


class ExampleBoard(BoardBase):
    def __init__(self):
        super().__init__(deps=[])

    def run(self, payload: str):
        """Run the example workflow through the service gate.

        When the board's gate is open: full path through services.
        When closed: returns a fallback value (demonstrates the pattern).
        """
        if self.gate != "open":
            return self._fallback_run(payload)
        self._assert_deps_open()
        from module.services import run_example_workflow

        result = run_example_workflow(payload)
        return result.value

    def _fallback_run(self, payload: str) -> str:
        """Closed-gate behavior. Returns input unchanged.

        Real fallbacks should be intentional — e.g., serve a stale cache,
        return a sentinel that callers can detect. Don't add a fallback
        unless you have a specific use case for closed-gate operation.
        """
        return payload
