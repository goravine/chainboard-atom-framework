# chainboard — architecture enforcement for Python, at import time

**Keep a Python codebase's architecture from rotting — including when AI/LLM
agents are writing most of the code.** chainboard is a small application
framework (hexagonal / clean-architecture lineage) with one unusual property:
the architecture rules are executable, and **the code refuses to import when a
boundary is violated.** Not a CI check you can skip, not a linter you can
silence — an import error at the moment the rule is broken.

> If you've ever watched "just put it here for now" turn into an unmaintainable
> tangle — or watched an LLM confidently scatter the same logic across five
> files — this is the guardrail. The architecture becomes *unmaintainable to
> violate.*

Built on three primitives + an import-time scanner:

- **Atom** — a leaf: one variable, one primitive IO, or one pure transform. Not a junk drawer.
- **Chain** — a fail-fast, straight-line multi-step workflow with execution history.
- **Board** — a bounded capability surface with a gate and explicit dependencies.
- **Scanner** — runs on `import`; enforces layer boundaries, the no-hardcoded-config rule, chain shape, and project-specific bug-class rules. A violation is an `ImportError`.

**Keywords:** Python architecture enforcement · import-time architecture linter
· prevent architectural drift · hexagonal / ports-and-adapters / clean
architecture template · dependency boundary enforcement · LLM-safe / AI-agent-safe
codebase · single-source-of-truth business logic · bug-class-to-scanner-rule.

---

## Why

Most application frameworks decay because:

- code drifts into the wrong layer ("just put it here for now")
- runtime values leak into source ("just hardcode the URL until we deploy")
- the same calculation gets re-derived in two places and they silently diverge
- abstractions decorate without enforcing ("the linter doesn't catch this")

And LLM-assisted contributions make all four worse, faster: an agent will
cheerfully put logic in the wrong layer, hardcode a URL, or duplicate a formula
— because each looks locally reasonable. A style linter won't stop it; a human
reviewer often won't either.

chainboard's bet: **the architecture lives in `PROTOCOL.md`, and the scanner
refuses to import the code when the architecture is violated.** No CI, no review
queue, no "fix it later" — the violation is the import error. Every time a bug
*class* is found, it becomes a new scanner rule, so the codebase gets *harder*
to break over time instead of accumulating the same regressions.

---

## Architecture in one diagram

```text
api_app          (transport: FastAPI routers, schemas, middleware)
   |
   v
sdk              (stable object-facing surface)
   |
   v
module.services  (stable service gate; private children in module/services_*.py)
   |
   +----> module.atoms.*       (leaf IO and primitives)
   |
   +----> module.*Board        (capability surfaces with gates + deps)
   |
   +----> module._chain        (ChainResult workflow primitive)
```

Read [PROTOCOL.md](PROTOCOL.md) once. It's the canonical contract.

---

## Quick start

```bash
# 1. Clone (or install via pip — see below)
git clone https://github.com/goravine/chainboard-atom-framework.git
cd chainboard-atom-framework

# 2. Install
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Smoke test (scanner self-validates)
python -c "import module"
#   [SCANNER] Validating hardcoding policies...
#   [OK] hardcoding policies validated | 0 errors
#   [SCANNER] Validating module chains...
#     [OK] services_example.py:25 - 2 step(s)
#   [OK] 1 chain(s) validated | 0 errors | boot OK

# 4. Run the example API
uvicorn api_app.main:app --reload
# Then:
#   GET http://localhost:8000/health
#   GET http://localhost:8000/api/example/echo/hello
```

### Install as a package (no PyPI yet — pin to a tag)

```bash
pip install git+https://github.com/goravine/chainboard-atom-framework.git@v0.1.0
```

Once your project depends on it, the `module/` framework core is importable
under the package name `chainboard`. PyPI publish is intentionally deferred —
see "What this framework is NOT" below.

---

## What's in the template

| Path | Purpose |
|---|---|
| `module/_base.py` | `BoardBase` — gate + deps contract |
| `module/_chain.py` | `ChainResult` — multi-step workflow primitive |
| `module/_scanner.py` | Import-time architecture enforcement |
| `module/__init__.py` | Runs the scanner on import |
| `module/services.py` | Stable service gate (max 350 lines / 20 funcs) |
| `module/services_example.py` | Private child of the gate (replace with your domain) |
| `module/example.py` | Seed `ExampleBoard` (replace with your boards) |
| `module/atoms/example_io.py` | Seed atom (replace with real IO leaves) |
| `module/atoms/datetime_tz.py` | UTC ↔ local-TZ display helpers ([use case](docs/USE_CASES.md#2-user-facing-timezone-discipline)) |
| `module/atoms/idempotent_hook.py` | Fire-once external-side-effect wrapper ([use case](docs/USE_CASES.md#4-idempotent-external-side-effect-hooks)) |
| `docs/USE_CASES.md` §6 | **Atom vs composition** — variable/formula split (the highest-leverage pattern; stops scattered business logic) |
| `docs/USE_CASES.md` §7 | Single-writer file pipe — staged import, never `os.replace` under a live handle |
| `docs/USE_CASES.md` §8 | Bug class → scanner rule discipline + the naive-datetime rule |
| `docs/USE_CASES.md` §9 | Runtime preflight — the scanner's environment-readiness sibling |
| `docs/USE_CASES.md` §10 | Adding a feature — the atom→builder→board→route layer walk |
| `sdk/exceptions.py` | Framework exception hierarchy |
| `api_app/main.py` | FastAPI app boot |
| `api_app/routers/example.py` | Example router showing layer flow |
| `api_app/services/example_service.py` | API-side thin service wrapper |
| `config/_cfg.json.example` | Configuration template (copy to `_cfg.json`) |
| `tests/test_chain.py` | ChainResult smoke tests |
| `PROTOCOL.md` | The framework contract |
| `docs/USE_CASES.md` | Reusable patterns validated in real deployments |
| `CHANGELOG.md` | Per-version changes (Semantic Versioning) |

---

## Adding your first real Board

1. Decide the capability boundary. (One board = one bounded capability.)
2. Create `module/<noun>.py` with class `<Noun>Board(BoardBase)`.
3. Add the module path to `_BOARD_MODULE_PREFIXES` in `module/_scanner.py`.
4. Export it from `module/__init__.py`.
5. If the Board needs orchestration, add a `module/services_<domain>.py` child and re-export from `module/services.py`.
6. Wire HTTP at `api_app/routers/<noun>.py` via a thin service wrapper at `api_app/services/<noun>_service.py`.

`python -c "import module"` runs the scanner. If you skipped a step (wrong class name, atom imported from a Board, hardcoded URL, etc.), the import fails with a specific error.

---

## What the scanner catches

- Hardcoded runtime URLs in active code
- Config-shaped function defaults (`def fetch(url="https://prod...")` — instant fail)
- Atoms importing from `api_app`, `sdk`, services, or boards
- Higher layers reaching into atoms directly
- Imports of private `module/services_*.py` from outside the service domain
- Chains constructed inside `if`/`for`/`while`/`with` (must be straight-line)
- Duplicate chain step names
- Observers (`.on(...)`) registered after `.pipe(...)`
- Service gate growth past 350 lines / 20 functions
- Board file growth past 180 lines / 16 public methods
- Board class name not matching `<FileStem>Board` (unless explicitly excepted)

The base rules above ship with the template. **Project-specific bug-class
rules** (e.g. no hardcoded DB paths, no tz-naive `datetime`, render-site
timezone discipline) are added inline as your project hits the bug — see
[docs/USE_CASES.md §8](docs/USE_CASES.md). The scanner is meant to grow one
rule per bug class; that growth is the point, not scope creep.

---

## What this framework is NOT

- Not a web framework. It's a Python application architecture; FastAPI is bundled as a sensible default for the HTTP layer but easily replaceable.
- Not a microservices framework. It assumes a single deployable; nothing here splits services.
- Not an ORM / DB layer. Add your own atoms.
- Not opinionated about your domain. The example Board / atom / service are placeholders.

---

## Origin

Extracted from a production app that started as a pre-modular Streamlit project, was migrated to a FastAPI service, and grew the Chain/Board/Atom primitives + scanner to prevent architectural drift as the team and LLM-assisted contributions scaled.

The scanner-at-import-time decision came from watching architectural shortcuts land in PRs and CI-only checks fail to catch them. Import-time enforcement is unavoidable; the architecture became unmaintainable to violate.

---

## License

MIT. See [LICENSE](LICENSE).
