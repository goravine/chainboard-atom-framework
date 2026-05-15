"""Framework core module.

Importing this package runs the scanner. The scanner validates:
  - chain shapes are well-formed
  - no hardcoded runtime URLs / configish defaults in active code
  - import-law compliance across atoms / services / boards / SDK / api_app
  - service-gate boundary (callers must import `module.services`, not children)
  - board file naming + size budgets

If any check fails, `import module` raises ScannerError and the application
will not start. This is intentional — see PROTOCOL.md and `module/_scanner.py`
for the reasoning.

To disable the scanner for a specific file, add it to
`_HARD_CODED_SCAN_SKIP_FILES` in `_scanner.py` WITH a comment justifying why.
Do not bypass the scanner silently.
"""

from module._scanner import validate_chains

validate_chains()

from module._base import BoardBase
from module._chain import ChainResult
from module.example import ExampleBoard

__all__ = [
    "BoardBase",
    "ChainResult",
    "ExampleBoard",
]
