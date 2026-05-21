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

The scanner here catches *render-site* violations. The producer side — a naive
`datetime.now()` leaking local time into storage — is closed by the
**naive-datetime scanner rule in §8**, which bans tz-naive datetime
construction in the application package outside the timezone atom. With both
rules in place the double-shift class is fully guarded, not left to a
code-review reflex.

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

## 6. Atom vs Composition — the variable/formula split

### Shape of the problem

A contributor needs a derived figure — a fee total, a profit number, a
score. The obvious move is to compute it where it's first needed, inline, in
a service. Three weeks later a second surface needs the same figure and
computes it again, slightly differently. Both look correct. They disagree by
a rounding rule, or one gets a bug fix the other misses, and now the same
"number" means two things depending on which screen you're on.

This is the most common way business logic rots, and nothing in a layered
architecture stops it on its own — both copies are in the "right" layer.

### Pattern

Separate **variables** from **compositions**, and give compositions exactly
one home.

- An **atom is a variable or a primitive**: an irreducible value from one
  source (a raw API field, a config value), or one focused transform (a
  timezone conversion, a signature). Treat it like a variable.
- A **composition is a formula over variables** — a fee total, a profit. It is
  *not* an atom. It lives in a single **formula module** that composes other
  atoms' outputs, and every consumer imports that module. One definition,
  imported in N places — never N inline re-derivations.

Litmus: *if the value is calculated from other values, it is a formula, not a
variable.* `commission_fee` (raw from the API) is a variable. `total_fee =
commission + shipping + service` is a formula.

### Layout

```
module/atoms/<source>_read.py   # extracts raw variables from a payload/table
module/atoms/<domain>_formula.py # the ONLY place derived figures are computed
module/services_<domain>.py      # orchestrates; calls the formula module,
                                 # never re-derives the math
```

The formula module is still an atom by the leaf rule — pure functions, no IO,
no upward imports — it just happens to compose other atoms' values rather than
read a source. Each function takes a dict of the day's/row's variables and
returns one figure.

### Boundary rules

- A derived figure is computed in exactly one function, in the formula module.
- Two services that both show the figure both import it. If you find the same
  arithmetic in two services, that is the bug — collapse it.
- The formula module does no IO. Variables are extracted by a read atom (or the
  query layer) and handed in. Keeps the formula pure and unit-testable.

### Scanner rule

Optional but recommended once the formula module exists: a rule that flags the
formula's constituent arithmetic appearing *outside* the formula module (e.g.
the literal fee-sum pattern in a service). Harder to express than an import
rule — at minimum, code-review for "is this re-deriving a figure the formula
module owns?" and pin the figure with a test so a divergent copy fails.

### Why this is the highest-leverage pattern here

Layering tells you *which file* logic goes in. It does not tell you that a
calculation must have one definition. That gap is where "the dashboard says X,
the report says Y" bugs live. The variable/formula split closes it.

---

## 7. Single-Writer File Pipe (staged import, never `os.replace`)

### Shape of the problem

A file (a SQLite DB, a cache) is read by many processes and written by one. An
admin endpoint needs to *replace* the whole file with an uploaded copy. The
textbook move is atomic-rename: write a temp file, `os.replace` it over the
live one. It looks correct — `os.replace` is atomic at the filesystem level.

It is a trap. If another process has the file **open** when you replace it,
that process's handle now points at the old (unlinked) inode. For SQLite the
`-wal`/`-shm` sidecars desync; the open process writes into a stale
write-ahead log that no one else sees. Symptom: the writer reports success,
the file on disk never changes, and live data silently stops updating. (We
spent a debugging session on "0 new rows since the upload" before finding
this.)

### Pattern

One file, one writer — enforced by routing every write through a single owner
process. A bulk replace does NOT swap the file:

1. The admin endpoint (in a *different* process from the writer) **stages** the
   uploaded bytes to a separate file, e.g. `<name>.upload.staged`. It never
   opens the live file.
2. The single writer process, on its normal work cycle, checks
   `is_staged_upload_present()`. If so it **imports** the staged file's rows
   into the live file through its own open connection (e.g. `ATTACH` + `INSERT
   OR REPLACE`), then deletes the staging file.
3. The live file is only ever written by that one owner, through one
   connection. Nothing is ever `os.replace`d under a live handle.

### Boundary rules

- Readers open the file read-only and are unaffected (SQLite WAL allows many
  readers + one writer).
- The staging step is a plain byte write — the staging process must not open
  the staged file as a database, only the importing owner does.
- The import is idempotent (`INSERT OR REPLACE` on the key) so a re-run merges
  rather than duplicates.
- If multiple threads inside the one writer process can write, serialize them
  with a single in-process lock. Cross-process is handled by there being only
  one writer process at all.

### What this doesn't cover

In-process concurrency between the writer's own threads still needs a lock.
And a bulk import of a large file blocks the writer's cycle while it runs —
acceptable for an occasional admin action, not for hot-path writes.

### Doctrine

`os.replace` on a file another process holds open is never safe, however
atomic the rename. "One writer, everyone else read-only, replace via staged
import" is the contract.

---

## 8. Bug Class → Scanner Rule (and the naive-datetime rule)

### Shape of the problem

A bug is found, root-caused, and fixed with a one-line patch. The fix is
correct. Six weeks later the *same class* of bug reappears in a different file,
because nothing stopped a contributor (or an LLM) from writing the same broken
shape again. The fix addressed an instance; the class was never closed.

### Pattern

**Every time you fix a bug class, add a scanner rule that forbids the broken
shape.** The fix removes the instance; the rule removes the class. This is the
discipline that makes the codebase get *harder* to break over time instead of
accumulating the same regressions.

Process:

1. Fix the instance.
2. Name the *shape* of the mistake (not the specific value — the pattern).
3. Add a scanner rule, inline with the existing rules, that fails the build on
   that shape. Negative-test it (prove it flags a synthetic bad case and
   ignores the good one).
4. The rule's error message names the right thing to do instead.

### Worked example: the naive-datetime rule (closes §2's producer gap)

§2 (timezone discipline) noted the scanner catches *render-site* violations but
**cannot** see a naive `datetime.now()` flowing through a producer — that was a
documented hole. Here is the rule that closes it.

The bug class: a tz-naive `datetime(...)` / `datetime.now()` /
`datetime.fromtimestamp(...)` / `datetime.combine(...)` is interpreted in the
*host machine's* timezone. A dev box in one TZ and a server in another then
produce different epochs for the same calendar instant — and if that epoch is a
storage key, you get duplicate rows that downstream code sums (we shipped
exactly this: an ad-spend figure double-counted because a WIB laptop and a UTC
server keyed the same day two ways).

The rule: in the application package, ban tz-naive datetime construction.
Require a `tz=`/`tzinfo=` keyword on `datetime(...)` and
`datetime.fromtimestamp(...)`; treat `datetime.utcnow()` as always a violation.
Exempt the one atom that legitimately defines the timezone (the
timezone-conversion atom — §2's `datetime_tz`). All day/epoch math routes
through that atom; everywhere else calling a bare `datetime` constructor fails
the build.

This is the producer-side guard §2 said required a "code-review reflex." It
no longer does — the scanner catches it.

### Doctrine

A scanner that only ever had its founding rules is a scanner that is slowly
falling behind the bugs. The rule set is meant to *grow*, one bug class at a
time. A new rule is the most durable possible fix.

---

## 9. Runtime Preflight (the scanner's runtime sibling)

### Shape of the problem

The scanner validates the *code* at import time. But a correct codebase still
fails at runtime if the *environment* is wrong: config file absent, a database
missing its schema, a seed not applied, a credential blank. These don't surface
until the first request 500s — often after a fresh deploy, exactly when you
have least time to debug.

### Pattern

A **preflight** check — a runtime-readiness validator, sibling to the scanner.
The scanner answers "is the code shaped right?"; preflight answers "is this
environment ready to serve?". Same `[OK]/[FAIL]/[WARN]` report shape, run on
demand (before a deploy or a big rework), not on every boot.

It checks, and optionally auto-fixes:

- config present and parseable, required sections present;
- every datastore exists with its expected schema (with `--fix` to create a
  missing one);
- seeds applied; required secrets/credentials present (warn, don't necessarily
  fail);
- the code scanner itself passes (preflight subsumes it).

Failure modes: fail loud. A `--strict` flag turns warnings into a nonzero exit
so CI can gate on it. Critical misses (no config at all) are hard fails;
auto-fixable ones (missing empty DB) are fixed and reported.

### Why separate from the scanner

The scanner must run on every import — it has to be cheap and environment-free
(it reads source, not state). Preflight reads *state* (files, DBs, env) and may
mutate (`--fix`), so it cannot live on the import path. Two tools, two
questions, one report style.

---

## 10. Adding a Feature — the four-step layer walk

### Shape of the problem

Patterns 1–9 are mostly about *getting the architecture right* — bootstrapping
it, correcting drift, codifying bug classes. But the day-to-day question is
quieter: **a new feature needs a new piece of data on the screen. Where does
each part go, and how do I not break the layering doing it?**

Without a contract this is where drift starts. A new endpoint "just needs one
query," so the query lands in the router. The next one lands in a service. A
third re-derives a number a formula module already owns. Six months later the
business logic is scattered across three layers and two of them disagree.

### Pattern

Every read-shaped feature is the **same four-step walk down the layers**, and
it is always the same four steps in the same order:

1. **Atom** — if the feature needs data not yet extracted, add *one* leaf:
   either a new primitive IO (a query/read) **or**, if the figure is
   *calculated*, a function in the existing formula module (§6 — a derived
   number is never a new atom). Do not skip to a service with an inline query.
2. **Builder** (private service child, `services_<domain>.py`) — assemble the
   atom outputs into the feature's payload shape. This is where composition
   lives; it imports atoms, never the reverse.
3. **Board method** — expose the builder through the capability surface, behind
   the gate. One thin gated method per capability.
4. **Route** — the transport wrapper (`api_app/...`) calls the board method and
   maps errors to status codes. No domain logic here.

The same walk works in reverse for "where is this number coming from?": route →
board → builder → atom, and the atom is the single definition.

In one real session a cold contributor added **four endpoints and five UI
screens** this way. Two screens needed *zero* new backend — the figures already
lived in one formula module, so the builder already returned them. The new fee
breakdown "just worked" because it was arithmetic over variables that already
existed (§6 again). Each genuinely-new read was the identical four-step move;
there was never a question of *where* code went, only *what* it computed.

### What keeps it honest

The layer caps and import laws the scanner already enforces (§5, PROTOCOL.md):

- An atom that tries to import a service or board fails at import.
- A higher layer reaching past the gate into an atom fails at import.
- The **service-gate function cap** is the one that bites a fast contributor:
  add one wrapper `def` too many and the gate refuses to import. The fix is
  itself doctrine — a pure pass-through read needs no wrapper, so **re-export
  the builder under the public gate name as an alias** rather than wrapping it
  in a counted `def`. The cap turns "the gate is bloating" into a hard stop at
  the moment it happens, not a code-review comment three weeks later.

That last point is the tell that the system is working: across a large feature
build, the *only* friction was a framework rule firing at import time — not a
domain bug discovered in production.

### Honest empty states

A feature's design will often ask for data the backend can't yet produce (a
field not synced, a dimension not mapped). The discipline that pairs with the
four-step walk: **render the unbacked widget as a graceful empty state, never
fabricate the number to fill the layout.** The walk makes it obvious where the
gap is — there is no builder field for it, so there is no atom for it, so the
data genuinely does not exist yet. The empty state is the honest report of a
missing atom, and it names the follow-up work precisely.

---

## Pattern Index

| Pattern                                | Add a scanner rule? | Add an atom? |
|----------------------------------------|---------------------|--------------|
| 1. Sharded catalog DB                  | Yes                 | No (project-specific resolver) |
| 2. User-facing timezone discipline     | Yes                 | Yes (`datetime_tz`) |
| 3. Deploy from committed state         | No                  | No (deploy script change) |
| 4. Idempotent side-effect hooks        | No                  | Yes (`idempotent_hook`) |
| 5. Scanner skip list locked            | Yes (self-rule)     | No |
| 6. Atom vs composition (variable/formula) | Optional         | Yes (a formula module) |
| 7. Single-writer file pipe             | No                  | Yes (a staging/import atom) |
| 8. Bug class → scanner rule (+ naive datetime) | Yes (the point) | No |
| 9. Runtime preflight                   | No (it *runs* the scanner) | No (a script) |
| 10. Adding a feature (four-step walk)  | No (existing rules guard it) | Maybe (a new leaf or formula fn) |

Each pattern that mentions a scanner rule should be added inline next to the
existing rules in `module/_scanner.py`, not extracted into a separate file.
The scanner is a single immune system, not a plugin host.
