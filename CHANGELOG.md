# Changelog

All notable changes to this framework are recorded here. Versions follow
[Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH` where MAJOR
breaks contract, MINOR adds doctrine or atoms, PATCH fixes scanner /
example code.

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
