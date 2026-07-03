# Changelog

All notable changes to this framework are recorded here. Versions follow
[Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH` where MAJOR
breaks contract, MINOR adds doctrine or atoms, PATCH fixes scanner /
example code.

## [0.5.0] — 2026-07-03

The scanner-scans-itself release. Two new rule families born from a real
field failure (a sibling project's scanner rule found silently dead for the
project's entire life), plus the framework's principle written down.

### Added
- **Rule 0 — scanner integrity** (`_scan_scanner_integrity`): every
  configured scan target must exist or be declared in `_DECLARED_ABSENT`
  with a justification; stale absence declarations fail; stale skip-list
  entries fail; an active dir yielding zero scanned files is a vacuity
  violation. "Cannot check" is a violation, not a skip. Runs before every
  other rule.
- **Console-safety rule** (`_scan_file_for_console_safety`): string
  literals in `print()` calls must encode to cp1252 — a box-drawing char or
  emoji in a diagnostic crashes the scanner on a Windows console instead of
  reporting the violation. Applies to all active code including the
  skip-listed scanner itself.
- Coverage attestation: the scanner's pass line now reports
  `N file(s) across M dir(s)` so a vacuous pass is visible at a glance.
- `docs/PRINCIPLE.md`: the framework's principle (move correctness from
  discipline into mechanism, at the moment of authorship), the four
  load-bearing choices, Rule 0's doctrine, and why the framework works
  best with an LLM as the driver.
- 6 new scanner tests (12 total).

### Changed
- PROTOCOL.md Scanner Protocol: Rule 0 section + the rule-author
  corollary (never degrade to warn-and-skip; the missing precondition IS
  the finding) + console-safety duty.
- What Must Stay True: added "no scanner rule may pass vacuously".
- Seed template: removed the empty untracked `tools/` dir; declared it in
  `_DECLARED_ABSENT` (adding tools later forces the declaration out, which
  turns its rules on — the mechanism working as designed).

## [0.4.0] — 2026-05-21

Doctrine release. No code/API changes to the framework core; one new
USE_CASES pattern distilled from extending the same production deployment (the
Shopee analytics dashboard) — this time *building on top of* a settled
chainboard app rather than bootstrapping or correcting one.

### Added

- **USE_CASES.md §10 — Adding a feature: the four-step layer walk.** The
  day-to-day pattern the earlier entries didn't name: every read-shaped feature
  is the same walk down the layers — **atom → builder → board method → route** —
  in that order, every time. Covers the reverse walk for "where does this number
  come from?", the **service-gate function cap** as the rule that bites a fast
  contributor (and the alias-not-wrapper fix), and the **honest-empty-state**
  discipline (an unbacked widget is the visible report of a missing atom — never
  fabricate the number to fill a layout). Pattern Index updated.
- Evidence behind the entry: a cold contributor added **four endpoints and five
  UI screens** in one session; two screens needed zero new backend (the figures
  already lived in one formula module, §6), and the *only* friction across the
  whole build was a framework rule firing at import time — the architecture
  working as designed, not a production bug.

### Doctrine

- §10 is a **template**, consistent with the v0.2.0+ stance: the framework
  ships no new code; the four-step walk is enforced entirely by rules that
  already exist (import laws, layer caps, the §6 variable/formula split).

### Compatibility

No breaking changes. No code changes to `module/`. `v0.3.0` consumers upgrade by
changing the version pin; everything new is documentation/contract.

## [0.3.0] — 2026-05-21

Doctrine + discoverability release. No code/API changes to the framework core;
all additions are contract (PROTOCOL.md), patterns (USE_CASES.md), and README.
Distilled from a second production deployment (a Shopee analytics dashboard)
that exercised the framework hard and surfaced where a cold contributor — human
or LLM — handed only the repo would still go wrong.

### Added

- **PROTOCOL.md — the atom-vs-composition rule.** The `### Atom` section now
  states the load-bearing distinction up front: *an atom is a variable or a
  primitive; a calculated figure is a formula, not an atom, and lives in one
  formula module every consumer imports.* The old "atoms exist for … pure
  calculations" line (which invited shipping derived figures as atoms, the #1
  cause of scattered business logic) is corrected.
- **PROTOCOL.md — Atom Creation Protocol.** Replaces the thin "Atom Protocol"
  with an 8-step add-an-atom checklist (name the one thing → leaf → not a
  duplicate → variable-or-composition → single source → docstring-as-spec →
  test → consider a scanner rule) and an explicit atom anti-patterns list
  (the "utils" junk drawer; a calculated figure as an atom; the same variable
  produced twice).
- **USE_CASES.md §6 — Atom vs Composition (variable/formula split).** The
  highest-leverage pattern: why layering alone doesn't stop a calculation from
  having two definitions, and the one-formula-module cure.
- **USE_CASES.md §7 — Single-Writer File Pipe.** `os.replace` on a file another
  process holds open is never safe, however atomic the rename (it desyncs the
  open handle's SQLite `-wal`/`-shm`; writes silently vanish). Replace via a
  staged file imported by the one writer process instead.
- **USE_CASES.md §8 — Bug class → scanner rule.** Codifies the discipline that
  every fixed bug class becomes a scanner rule, and documents the
  **naive-datetime rule** — which closes the producer-side gap §2 had
  explicitly left open (a tz-naive `datetime.now()` leaking host-local time
  into storage). §2's "What this doesn't cover" is updated to point at §8.
- **USE_CASES.md §9 — Runtime Preflight.** The scanner validates code at import
  time; preflight validates the *environment* (config, datastores + schema,
  seeds, credentials) on demand. Same report shape, runs off the import path
  because it reads/mutates state.
- **README rewrite for discoverability.** Problem-first headline, an explicit
  keyword line (architecture enforcement, import-time linter, hexagonal/clean
  template, LLM-safe codebase, single-source-of-truth), and an LLM-contributions
  framing — the audience most likely to need this and least likely to find it
  by the old "framework built on three primitives" opener. File-tour table and
  scanner-catches list updated for §6–§9 and project-specific bug-class rules.

### Doctrine

- The new patterns are **templates**, consistent with the v0.2.0 stance: the
  framework still ships only the base scanner rules; projects add the
  bug-class rules (§8) inline. The scanner remains one immune system, not a
  plugin host.
- "Atom = variable, composition = formula" is now first-class contract, not
  folklore — the distinction that keeps business logic from scattering.

### Compatibility

No breaking changes. No code changes to `module/`. `v0.2.0` consumers upgrade
by changing the version pin; everything new is documentation/contract.

## [0.2.0] — 2026-05-20

### Added

- **`docs/USE_CASES.md`** — five reusable patterns validated against real
  deployments, each describing the failure shape, the pattern that
  resolves it, and the scanner / doctrine touch points that keep it
  honest:
  1. Sharded catalog DB with a read-side gate (and the
     write-target deadlock that the read-vs-write helper split avoids).
  2. User-facing timezone discipline — storage is UTC, renders pin the
     display TZ — plus the browser-side scanner rule shape.
  3. Deploy from committed git state via `git show <ref>:<path>`, never
     from working tree.
  4. Idempotent external-side-effect hooks keyed on natural identity,
     and why status-based / attempt-count gating fails under retry.
  5. Scanner skip list as a locked invariant — the governance mechanism
     itself is scanner-enforced.
- **`module/atoms/datetime_tz.py`** — `format_in_tz(value, tz_name, *, fmt,
  suffix)` and `utc_now_iso()`. The renderer accepts UTC ISO with offset,
  `Z` suffix, naive strings (assumed UTC), and `datetime` objects;
  unparseable input passes through unchanged so malformed cells remain
  visible. The `utc_now_iso` companion exists so producer code has a
  drop-in replacement for `datetime.now()` without leaking naive local
  time into storage.
- **`module/atoms/idempotent_hook.py`** — `fire_once(identity, store_path,
  action)` wrapping the persistent-seen-set pattern. Process-wide locking
  per store path; on-disk persistence via temp-file + atomic rename so a
  crash mid-write leaves the previous state intact; all failures (storage
  I/O, action exceptions) are swallowed so the surrounding pipeline never
  breaks because a side effect couldn't fire.
- **README.md** — the file-tour table now links the new atoms to their
  use-case sections, and lists `docs/USE_CASES.md` alongside `PROTOCOL.md`.

### Doctrine

- The two new atoms keep the framework's leaf-only contract: no config
  lookup, no project-specific defaults, explicit inputs/outputs, no upward
  imports. Project code wraps them with its own configured constants.
- `USE_CASES.md` patterns are **templates**, not features. The framework
  does not ship the scanner rules described in the doc; each project adds
  the rule inline next to existing scanner rules. The scanner remains a
  single immune system, not a plugin host.

### Compatibility

No breaking changes. `v0.1.0` consumers can upgrade by changing the
version pin; existing imports continue to resolve.

## [0.1.0] — Initial release

Bootstrap framework template: `module/_chain` ChainResult primitive,
`BoardBase`, example board + atom + service, FastAPI shell, scanner with
chain-shape / import-law / hardcoding / file-shape rules, `PROTOCOL.md`
contract.
