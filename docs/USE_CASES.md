# Use Cases

This document catalogues patterns the framework has been validated against in
real deployments. Each entry describes the shape of the problem, the pattern
that solves it, and the scanner / doctrine touch points that keep the pattern
honest as code evolves.

These are not features the framework provides out of the box. They are
*templates* — write the code in your own repo, but keep the shape described
here so future readers (and the scanner) recognize what they are looking at.

If a pattern below conflicts with `PROTOCOL.md`, the protocol wins. Patterns
are downstream of the contract.

---

## 1. Sharded Catalog DB with Read Gate

### Shape of the problem

Some part of your domain reads a large, mostly-static table (a catalog,
price book, mapping registry). You want to point different consumers — a
product line, a tenant, a market — at *their own copy* of that table without
forking the rest of the schema.

The naive approach is "one shared DB, one column to filter on." That works
until two teams diverge on what the table should contain. After that,
shipping a row for tenant A starts breaking tenant B.

### Pattern

Shard *only the catalog tables*. Everything else — the registry, config
caches, auth, anything that is not per-tenant by nature — stays on the shared
DB. Catalog reads route through a single resolve function (the "gate").

Two helpers, not one:

- `db_path_for(key)` — **write target**, unconditional. Always returns the
  per-key path. The sync / build flow uses this.
- `db_for(key)` — **read target**, readiness-gated. Returns the per-key path
  *only when that DB exists and the catalog table inside it has rows*.
  Otherwise returns the shared fallback DB.

The split matters. A read-side gate that doubles as a write-target picker
deadlocks: the gate sees an empty per-key DB, returns the shared fallback,
the sync writes into the shared DB, the per-key DB stays empty, repeat. The
write-side helper must never consult readiness.

### Layout

```
data/db/main.db            # shared: registry, config, fees, auth
data/db/catalog_<key>.db   # per-key catalog shard, gated
```

### Boundary rules

- Only **catalog-table reads** route through the gate. Registry, config,
  auth, and anything cross-tenant stays on the shared DB. Mixing the two
  collapses the whole point.
- The gate is called *once* per request at the service layer. Atoms receive
  a resolved `db_path` and never call the gate themselves.
- A blank or unknown key resolves to the shared DB. This is the fallback
  contract — it means the gate is safe to deploy before every per-key shard
  exists, and stays safe when a new key appears.

### Scanner rule

Add a rule that fails the build when any function querying a catalog table
references the shared-DB path constant directly. Catalog reads must come
from a `db_path` parameter the caller resolved through the gate.

Functions that legitimately read from *both* shards (e.g. config from
shared + catalog from per-key) are explicit exemptions, listed by name in
the rule. Exemptions are part of the contract; silent ones are not allowed.

### Surface to deploy

The per-key sync is triggered from outside — a button, a webhook, an
operator command. Authenticate it with the same shared secret used by the
rest of the runtime, accept the key as a query param, and run the sync in a
background thread (it will take minutes against a real source). Empty key =
re-sync the shared fallback.

---

## 2. User-Facing Timezone Discipline

### Shape of the problem

The database stores UTC. The team reads everything in their local time.
Somewhere in between, every project eventually grows a render that follows
the *visitor's* browser timezone instead of the team's. The team in
Region A sees Region B's wall clock by accident, mistakes a 10:00 timestamp
for 14:00, and acts on it.

This is not a bug you find in code review. It is a class of regression that
sneaks in every time someone writes `new Date(value).toLocaleString()`
without thinking about which clock that resolves against.

### Pattern

Two rules:

1. **Storage is UTC.** Every persisted timestamp is UTC ISO with the `Z`
   suffix. Server-side helpers that produce "now" return TZ-aware UTC. Naive
   `datetime.now()` is banned from anywhere a value might flow into the DB
   or out to a render path.
2. **Renders pin the display TZ.** Every user-facing render — sheet cells,
   browser DOM, notification messages — converts UTC → the team's local TZ
   at the render site. The TZ name is configured once per project; renders
   never inherit from `Date()` / browser locale / server local.

The dangerous failure mode is **double-shift**: a producer accidentally
emits the local wall clock as a naive string, a consumer assumes UTC and
adds the offset again, the user sees a value off by exactly the TZ offset.
The scanner can catch the consumer side; the producer side requires the
storage-is-UTC discipline.

### Helpers

A single atom (`module/atoms/datetime_tz.py`) provides the UTC → local
conversion:

```python
def format_in_tz(value, tz_name):
    """Convert a UTC ISO string to '<YYYY-MM-DD HH:MM:SS <abbrev>>' wall time.
    Naive input is assumed UTC (matches the storage rule)."""
```

Browser side, every `Intl.DateTimeFormat` / `.toLocaleString` /
`.toLocaleDateString` / `.toLocaleTimeString` call passes
`timeZone: "<configured-tz>"`. No exceptions for date-only renders — a
cross-TZ visitor still pulls the date into yesterday.

### Scanner rule

Walk the public web tree. Flag every match of `Intl.DateTimeFormat`,
`.toLocaleString`, `.toLocaleDateString`, `.toLocaleTimeString` whose
argument window doesn't include both `timeZone` and the configured TZ name.
An empty-argument `.toLocaleString()` is a violation by default — it
follows the visitor's locale and timezone, which is precisely what the
discipline forbids.

The configured TZ name is a single project-wide constant. Hardcode it once;
the scanner reads it from the same constant. Changing the project's display
TZ is a single-line edit + a scanner re-run.

### What this doesn't cover

The scanner catches *render-site* violations. It cannot see naive
`datetime.now()` flowing through a producer. The double-shift case requires
the storage-is-UTC discipline — make it a code-review reflex and the
scanner catches the rest.

---

## 3. Deploy from Committed State, Not Working Tree

### Shape of the problem

A deploy script that ships "everything currently in the working tree" is a
landmine. Half-finished edits, unstaged debugging code, a file you intended
to revert — all of it goes live the moment someone runs the script. The
script's intent ("ship what's ready") and its behavior ("ship what's on
disk") diverge silently.

### Pattern

The deploy script takes a git ref or range as input. Files to ship are
materialized from `git show <ref>:<path>` — i.e. read the *committed* bytes
at that ref, write them to a temp directory, and `scp`/`rsync` from there.
Never `scp` from the working tree.

A `--commit <range>` flag is enough. The script computes the file list from
`git diff --name-only <range>`, materializes each file from
`git show <range_end>:<path>`, and ships the staging copy. The working tree
is ignored entirely.

This composes with the staged-deploy pattern (`git diff --cached` for
"deploy what's about to be committed"): both modes use the same
materialize-from-git step. They just differ on where the ref comes from.

### Why this matters

Without it, two failure modes that look identical from outside but are
caused by different things:

- The deploy tool's diff says "X is ready to ship," but the script ships
  X-plus-unstaged-debugging-code.
- A commit looks correct in the PR but reaches prod with the wrong
  contents because the staging hop pulled from disk, not git.

Both go away when the script reads from git history.

### Doctrine

The deploy script's job is to **realize a git ref on a target host**. That's
the entire contract. If working-tree state ever influences the output, the
contract is broken.

---

## 4. Idempotent External-Side-Effect Hooks

### Shape of the problem

A pipeline writes a row, succeeds, fires a notification. Later, a retry
worker re-runs the pipeline on the same row (because it had stale "needs
sync" state, or someone clicked the button twice, or a recovery script
re-pushed a batch). The pipeline succeeds again. The notification fires
again. The team sees the same alert twice.

The pipeline is correct. The retry is correct. The notification is the
problem — it's a side effect that doesn't know about identity.

### Pattern

Notifications, webhooks, "tell the outside world this happened" calls — any
external side-effect with no transactional relationship to the row — must
be **idempotent by content identity**, not by row state.

Two anti-patterns to avoid:

- **Status-based gating.** "Only notify if status != 'success' before this
  call." Fragile: any retry path that resets status (`retrying`, `pending`,
  `failed`) bypasses the gate.
- **Attempt-count gating.** "Only notify if attempt_count == 0." Fragile:
  schema changes, attempt-count resets, double-create races all break it.

Reliable pattern: a **persistent set of already-notified identities**. The
side-effect site reads the set, fires only when the identity is absent,
adds it on success. The set is the source of truth for "have we told the
outside world about this thing yet."

An atom (`module/atoms/idempotent_hook.py`) wraps the shape:

```python
def fire_once(identity, store_path, action):
    """Call `action()` iff `identity` is not in the on-disk set at
    `store_path`. Adds it on success. Process-locked, fail-safe."""
```

Storage can be anything durable: a JSON file, a dedicated table, an
external KV. The shape is the same.

### Locking

If multiple processes can hit the same identity concurrently (a retry
worker plus a fresh submit), the set update needs locking. A process-local
lock plus a `O_CREAT | O_EXCL` write-then-rename gets you safe-enough
without bringing in a queue.

### What identity to use

Use the natural primary key of the thing being notified about — a
request id, an order id, a job id. Don't use a timestamp, a hash of
contents, or anything derived; those drift when the row is reprocessed
and break the dedup.

---

## 5. Scanner Skip List as a Locked Invariant

### Shape of the problem

The scanner's skip list grows. Every "this one rule doesn't fit here" gets
appended. Six months in, the skip list is half the codebase and the
scanner enforces nothing.

### Pattern

The skip list is itself scanner-enforced: there is exactly one rule that
says "the skip list must equal exactly this set." Adding a file to the skip
list is a deliberate edit to that set, justified by a comment, never a
side-effect of writing code.

In practice the skip list contains exactly one entry: the scanner's own
source file (which would otherwise self-match on its rule patterns). Every
other file is in-scope.

### Why this works

Skip lists are governance. Letting the governance mechanism itself drift is
how scanners die. The "locked invariant" pattern makes "weakening the
scanner" a visible, reviewable act rather than an accidental one.

---

## Pattern Index

| Pattern                                | Add a scanner rule? | Add an atom? |
|----------------------------------------|---------------------|--------------|
| 1. Sharded catalog DB                  | Yes                 | No (project-specific resolver) |
| 2. User-facing timezone discipline     | Yes                 | Yes (`datetime_tz`) |
| 3. Deploy from committed state         | No                  | No (deploy script change) |
| 4. Idempotent side-effect hooks        | No                  | Yes (`idempotent_hook`) |
| 5. Scanner skip list locked            | Yes (self-rule)     | No |

Each pattern that mentions a scanner rule should be added inline next to the
existing rules in `module/_scanner.py`, not extracted into a separate file.
The scanner is a single immune system, not a plugin host.
