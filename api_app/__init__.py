"""api_app — HTTP transport layer.

Allowed responsibilities:
  - FastAPI app boot
  - routers
  - schemas
  - middleware
  - dependency injection
  - response shaping

Not allowed:
  - hidden domain orchestration (push to module.services)
  - hardcoded runtime constants (push to config/_cfg.json)
  - duplicating service logic
  - direct atom imports (the scanner enforces this)

See PROTOCOL.md "Layer Responsibilities" for the contract.
"""
