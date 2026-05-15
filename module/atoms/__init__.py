"""Atoms — leaf-level IO and primitive operations.

Atoms should:
  - stay focused on one concrete capability (one IO target, one primitive op)
  - stay small (target: under 100 lines per atom)
  - take inputs explicitly, return results explicitly
  - NEVER import from api_app, sdk, services_*, or boards
  - NEVER make policy decisions (those belong in services_*)

The scanner enforces the import-law at module load. See PROTOCOL.md "Atom
Protocol" for the contract.
"""
