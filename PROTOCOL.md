# Protocol

This document is the framework contract.

Its purpose is simple:

- explain the architecture without requiring a full codebase scan
- tell contributors where code belongs
- make add/remove/modify decisions predictable
- preserve the modular method, board structure, atom discipline, and chain programming style

If a proposed change conflicts with this document, the change is probably wrong unless the protocol itself is intentionally updated first.

## Zero-Scan Warranty

A contributor should be able to understand the active architecture from this file alone.

This repo follows:

```text
api_app -> sdk -> module.services -> module.atoms.*
                 -> module.boards
                 -> module._chain
```

The active runtime should be understandable with these rules:

- `api_app` is transport and HTTP
- `sdk` is the stable object-facing layer
- `module.services` is orchestration
- `module/atoms` are leaf operations
- `module/*Board` classes are capability surfaces with gates and dependency boundaries
- `module/_chain.py` is the standard multi-step workflow primitive
- `config/_cfg.json` is the framework configuration standard

## Framework Vocabulary

### Module

In this repo, "module" means the framework core under `module/`.

It is the place where internal architecture lives:

- orchestration
- capability boards
- chain workflows
- leaf adapters
- internal guardrails

It is not just a folder name. It is the heart of the framework.

### Board

A board is a bounded capability surface built on `BoardBase`.

Boards exist to:

- group a capability cleanly
- expose an intentional boundary
- enforce gate state
- encode dependency relationships
- provide controlled fallbacks where that behavior is part of the design

The seed template ships with one example:

- `ExampleBoard`

Replace it with your project's real boards. Boards are the framework's operational surface, not random helper classes.

### Atom

An atom is a low-level leaf function module under `module/atoms/`.

Atoms exist for:

- focused IO
- serialization
- auth primitives
- storage primitives
- database helpers
- document helpers
- pure calculations

The seed template ships with one example:

- `example_io.py`

Atoms must stay leaf-like. They should not quietly become service layers.

### Chain

A chain is a `ChainResult` workflow.

Use chains when a flow has:

- multiple ordered steps
- fail-fast semantics
- named steps
- structured errors
- observer support

Canonical pattern:

```python
result = (
    ChainResult.of(payload)
    .pipe(validate_input)
    .pipe(load_state)
    .pipe(transform_state)
    .pipe(save_state)
    .collect()
)
```

Chains should be straight-line and explicit. The scanner enforces this.

## Layer Responsibilities

### `api_app/`

Allowed responsibilities:

- FastAPI app boot
- routers
- schemas
- middleware
- dependency injection
- response shaping

Not allowed:

- hidden domain orchestration
- runtime-specific constants that belong in `_cfg.json`
- duplicated service logic
- direct low-level persistence flow unless the framework contract explicitly says so

### `sdk/`

Allowed responsibilities:

- stable public objects
- translating service results into object methods
- consistent error surface for higher layers

Not allowed:

- becoming a second orchestration layer
- bypassing `module.services` for business workflows

### `module/services.py`

This is the orchestration layer.

It is allowed to:

- load config
- coordinate atoms
- shape workflows
- define chain-based processes
- bridge framework layers

It should be the place where business or domain orchestration lives.

`module/services.py` is also the **stable service gate**.

That means:

- external callers should import `module.services`
- child service modules may exist for internal categorization
- those child modules stay private to the service domain
- refactors should move implementation behind the gate before changing caller imports

Examples of acceptable internal child modules:

- `module/services_example.py` (seed)
- `module/services_<domain>.py` (yours)

Those files do not represent new architecture layers. They are subdivisions inside the same service domain.

### `module/*Board`

Boards should:

- express capability boundaries
- call into `module.services`
- enforce gate and dependency rules
- provide intentional fallback behavior when the board is closed

Boards should not:

- duplicate orchestration already implemented in services
- import atoms directly when the same capability can be exposed through `module.services`
- import upward into routers

### `tools/`

Operational scripts should:

- stay thin
- prefer board or service entrypoints
- perform execution-oriented wrapping only
- avoid becoming a second architecture tree

When a capability already belongs to a board, a tool should call that board rather than recreate its own parallel orchestration flow.

### `module/atoms/*`

Atoms should:

- stay focused
- stay small
- avoid business policy
- avoid upward dependencies

Atoms must not import from:

- `api_app`
- `sdk`
- boards

If an atom starts making policy decisions, it no longer belongs in atoms.

## Dependency Law

This repo should respect this direction:

```text
api_app
  -> sdk
  -> module.services
  -> module.atoms
```

Boards live alongside `module.services`, not above `api_app`.

Allowed:

- `api_app -> sdk`
- `sdk -> module.services`
- `module.services -> module.atoms`
- boards -> `module.services`
- tools -> boards or `module.services`
- private `module/services_*.py` children inside the service domain

Disallowed:

- atoms importing SDK or API layers
- atoms importing service or board layers
- boards importing atoms directly for runtime capabilities that belong behind `module.services`
- routers importing atoms directly for business flows
- external layers importing private `module/services_*.py` children instead of `module/services.py`
- random cross-layer shortcuts that bypass the intended surface

The scanner enforces every rule above at import time.

## Naming Protocol

Names should communicate layer and responsibility before a contributor opens the file.

Rules:

- board files use noun-style capability names such as `storage.py`, `tooling.py`, `management.py`
- board classes end with `Board`
- board classes should normally match the file stem in CamelCase plus `Board`, unless the protocol explicitly blesses an exception
- private service subdivisions use `module/services_<domain>.py`
- atoms use concrete IO or primitive names such as `db.py`, `sheets.py`, `auth_io.py`
- avoid vague names for broad surfaces unless the boundary is genuinely broad

Exceptions to the noun-stem rule are registered in `module/_scanner.py::_BOARD_CLASS_NAME_OVERRIDES` with a comment explaining why.

## Board Protocol

When adding a new board:

1. The board must represent a real capability boundary.
2. The board must inherit from `BoardBase`.
3. The board must define whether closed-gate fallback behavior exists.
4. The board should delegate orchestration to `module.services`.
5. The board should declare dependencies explicitly through `deps`.
6. Add the board's module path to `_BOARD_MODULE_PREFIXES` in the scanner so atom import-law catches violations against it.

When removing a board:

1. Confirm the capability boundary is being removed, not merely renamed.
2. Confirm another board or service layer is not relying on its gate semantics.
3. Remove imports from `module/__init__.py`.
4. Remove its entry from `_BOARD_MODULE_PREFIXES` in the scanner.

When modifying a board:

1. Preserve gate behavior.
2. Preserve dependency assertions.
3. Do not sneak orchestration into routers or atoms just because a board feels inconvenient.

## Atom Protocol

When adding an atom:

1. Confirm the logic is leaf-level.
2. Confirm it does not belong in `module.services`.
3. Keep inputs and outputs explicit.
4. Avoid hidden config lookups when a value can be passed in.

When removing an atom:

1. Confirm the capability is actually dead.
2. If it is merely being combined into a bigger orchestration, move that orchestration to services instead.

When modifying an atom:

1. Keep it dependency-light.
2. Avoid embedding runtime values.
3. Avoid turning it into a policy engine.

## Chain Protocol

Use a chain when the workflow benefits from structured execution history.

Use plain function calls when the flow is trivial.

Chain rules:

- start with `ChainResult.of(...)`
- use named step functions
- prefer `.pipe(...)` over anonymous inline complexity
- finish with `.collect()`
- use `.require()` only when raising is the correct caller contract

Do not:

- build chains dynamically inside control flow
- hide multiple unrelated concerns inside one chain step
- duplicate the same logical step name in one chain

## Configuration Protocol

The configuration standard is:

- `config/_cfg.json`
- `config/_cfg.json.example`

Deprecated for framework configuration:

- `.env`
- `.env.example`

Rules:

- runtime endpoints belong in `_cfg.json`
- public hostnames belong in `_cfg.json`
- sheet/storage runtime config belongs in `_cfg.json`
- app-facing flags belong in `_cfg.json`

If a contributor hardcodes a runtime URL, deployment ID, bucket, host, spreadsheet ID, or config-like default into active code, that is considered a protocol violation. The scanner is expected to catch this class of mistake.

`api_app/config.py` (pydantic-settings) is reserved for app-level boot
config (CORS origins, API title, etc.). Runtime/domain config goes through
`config/_cfg.json`.

## Scanner Protocol

Importing `module` runs `module/_scanner.py`.

The scanner is not optional decoration. It is part of the framework contract.

Current duties:

- validate chain shape
- reject dynamic chain construction
- reject duplicate chain step names
- reject hardcoded runtime literals in active runtime code
- reject config-like default arguments that embed environment-specific values
- reject direct board-to-atom shortcuts outside the service layer
- reject board/service file naming drift inside `module/`
- reject board surface growth that starts turning one board into a god-surface

When extending the scanner:

- optimize for long-term correctness
- avoid noisy rules that punish normal refactors
- prefer catching environment coupling over style trivia

Skip-file additions to `_HARD_CODED_SCAN_SKIP_FILES` must include a comment justifying the exemption.

## Add / Remove / Modify Protocol

### Add

Before adding code, ask:

1. Is this transport, SDK, orchestration, board capability, tool execution, or atom logic?
2. What is the narrowest correct layer?
3. Does the change introduce new config?
4. Does the change need chain semantics?
5. Does the change violate dependency direction?

### Remove

Before removing code, ask:

1. Is it active runtime code or archive/reference code?
2. Is a board, chain, atom, SDK, or tool contract relying on it?
3. Does removal create a hidden shortcut elsewhere?

### Modify

Before modifying code, ask:

1. Am I preserving the architecture boundary?
2. Am I moving logic to the wrong layer just because it is faster?
3. Am I embedding a runtime value that belongs in `_cfg.json`?
4. Am I weakening gate behavior, fallback behavior, or dependency clarity?

## What Must Stay True

These are non-negotiable framework truths unless the protocol is deliberately rewritten:

- atoms remain leaf-level
- orchestration lives in `module.services`
- `module/services.py` remains the stable service gate
- child service modules remain internal subdivisions of the same domain
- boards remain real capability boundaries
- tools remain thin execution surfaces
- chain workflows stay explicit and scanner-friendly
- `_cfg.json` remains the main framework config contract

## Anti-Patterns

These are considered framework regressions:

- hardcoding production or staging URLs in active code
- adding config-like defaults directly into function signatures
- putting business orchestration in routers
- putting policy logic in atoms
- bypassing `module.services` from SDK-facing flows
- importing private `module/services_*.py` modules from outside the service domain
- turning boards into empty decorative wrappers
- turning tools into shadow service layers
- letting `module/services.py` regrow into a godfile instead of pushing implementation into child service modules
- bypassing chain semantics for complex workflows that need execution history

## Practical Decision Table

If you are adding:

- HTTP behavior: use `api_app`
- object-facing behavior: use `sdk`
- orchestration/workflow: use `module.services`
- bounded capability surface: use a board
- execution surface: use `tools/`
- low-level helper or adapter: use atoms
- runtime config: use `config/_cfg.json`

## Final Rule

The architecture should be understandable before reading most files.

That is the real purpose of this protocol.

If a future change makes the framework harder to explain from this document, the change should be treated as suspect until proven otherwise.
