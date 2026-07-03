# The Principle

> **Move correctness from discipline into mechanism, at the moment of
> authorship.**

Everything in chainboard is one application of that sentence. This document
states the principle once, names the four load-bearing choices that implement
it, and explains why the framework works *best* — not merely acceptably —
when an LLM is the one writing most of the code.

---

## 1. The principle, unpacked

Architecture usually lives in three places, and dies in all of them:

| Where it lives | How it dies |
|---|---|
| Documentation | nobody re-reads it at the moment of writing code |
| Review | reviewers get tired, agents don't get reviewed line-by-line |
| CI / linters | warnings get silenced, checks get skipped "just this once" |

What these have in common: the rule is checked **after** authorship, by a
process that can be argued with. chainboard's answer is to make the rule
checked **at** authorship, by a process that cannot be argued with — the
import. Code that violates the architecture does not produce a warning, a
ticket, or a review comment. It produces an `ImportError`, immediately, on
the machine of whoever wrote it. **The architecture becomes unmaintainable
to violate.**

This is not a novel goal — it is the same instinct as static typing, as
`NOT NULL` constraints, as making illegal states unrepresentable. chainboard
applies it one level up, to the *shape of the codebase itself*: which layer
may import which, where orchestration lives, how big a surface may grow,
what a workflow must look like.

## 2. The four load-bearing choices

**Import-time death.** The scanner runs when `module` is imported. Not in
CI (skippable), not in a pre-commit hook (bypassable), not in a linter
(silenceable). There is no way to run code that violates the contract,
which means there is no "fix it later" — later never comes cheaper.

**The bug-class ratchet.** Every bug found in production becomes a new
scanner rule, permanently. The codebase does not merely get fixed; it gets
*harder to break in that way again*. Over time the scanner becomes a
compressed history of everything that ever went wrong — enforced. This is
the framework's growth mechanism, and it is deliberately the opposite of
scope creep: rules only enter through the door of a real bug.

**Crude caps.** A board is at most 180 lines and 16 public methods; the
service gate at most 350 lines and 20 functions. These numbers are crude,
and crude is the point: "keep boards focused" enforces nothing, `<= 16`
enforces itself. The cap does not know what good decomposition is — it only
knows when you have stopped doing it, and it forces the conversation at
that moment instead of three months later.

**Straight-line chains.** A workflow must be a flat, named, fail-fast
sequence — the scanner rejects chains built inside `if`/`for`/`while`.
This trades expressiveness for total legibility: anyone (human or model)
can read a chain and know the entire control flow without tracing anything.

## 3. Rule 0 — the scanner scans itself

The scanner is the one component with nothing above it, which makes its
failure mode uniquely dangerous: **a rule whose target has moved does not
fail — it silently checks nothing, forever, behind a green scanner that
everyone has learned to trust.**

This is not hypothetical. In a sibling project (2026-07-03), a rule that
verified every emitted stream channel had a client-side handler had been
dead for the project's *entire life* — the file it checked had moved one
directory down, the rule degraded to warn-and-skip, and every scan passed.
The rot was found only when someone questioned why the scanner had never
once complained about that rule.

Rule 0 makes "cannot check" a violation:

- a configured scan target that is missing must be **declared** absent,
  with a justification — undeclared absence fails the import
- a declaration for a path that *does* exist is stale and fails the import
  (honesty is enforced in both directions)
- a skip-list entry pointing at a deleted file fails the import
- an active directory that yields zero scanned files fails the import —
  a rule that ran against nothing did not pass

The corollary for anyone writing a rule: **never degrade to warn-and-skip
when a precondition is missing. The missing precondition is the finding.**

## 4. Why this works best with an LLM as the driver

chainboard was built explicitly for the LLM era — "keep a codebase's
architecture from rotting, including when AI agents write most of the
code." That phrasing undersells it. The framework is not merely
LLM-*tolerant*; its mechanisms are matched to how LLMs actually fail and
how they actually learn, in ways that human-oriented tooling is not.
Written from the LLM's side of the keyboard:

**LLMs follow local gradients; the repo must carry the global constraints.**
An agent writing a function sees the file, not the architecture. Each
locally-reasonable step — put the helper here, hardcode the URL for now,
copy the formula — is exactly how architecture dies, and the agent commits
these sins *faster* than a human because it writes faster. A constraint
that lives in documentation is invisible at the moment of authorship. A
constraint that lives in the import is unavoidable at the moment of
authorship. The repo itself becomes the senior engineer.

**An ImportError is in-context feedback; a lint warning is not.** When the
code an agent just wrote refuses to import, the error message arrives
inside the same working context, on the same turn — and the agent fixes it
immediately, the way it fixes any traceback. This is the only feedback
channel that reliably works: an LLM will route around a warning every time
(so will a tired human), but it cannot route around a crash. The scanner's
error messages are, in effect, prompts — each one teaches the rule at the
exact moment the rule is relevant.

**Scanner rules are memory that survives the context window.** An agent's
session ends; its lessons evaporate. A rule added to the scanner is the
lesson made permanent — the next session (or the next agent, or the next
model) does not need to be told, because the codebase itself refuses the
regression. The bug-class ratchet is how a solo developer's estate learns
faster than any individual session forgets.

**Straight-line chains are legible without execution.** A model reading a
chain knows the whole workflow from the source text alone — no tracing, no
mental interpreter, no "what does this branch do." That drops the cost of
every future modification, and LLMs make many small modifications. The
same goes for the caps: a board that fits in 180 lines fits in a context
window with room to think.

**Determinism makes the agent auditable.** Because the scanner is a pure
function of the source tree, "the scanner passes" means the same thing on
every machine, every session, every model. There is no judgment call to
disagree with, which means an agent's work can be accepted or rejected by
mechanism rather than by re-review — the precondition for actually
delegating authorship.

The inversion worth stating plainly: most tooling assumes a careful author
and adds convenience. chainboard assumes a *fast, forgetful, locally-
reasoning* author and adds walls. Humans benefit from the walls; LLMs
require them — and with the walls in place, an LLM's speed stops being a
risk and becomes the whole point.

## 5. What the framework is not

- **Not a library.** Repos copy the pattern; they do not depend on the
  package. Each copy grows its own project-specific rules (that is the
  ratchet working) and sheds organs it does not need. Divergence between
  copies is health, not drift — the seed is the contract, PROTOCOL.md is
  the genome.
- **Not a style guide.** The scanner deliberately ignores style trivia.
  Every rule earns its place by a bug class, not by taste.
- **Not a guarantee.** The scanner catches the failure modes that have
  been fed to it. Rule 0 exists precisely because the scanner itself is
  code and rots like code. Trust the mechanism, not the green checkmark —
  and when the green checkmark surprises you by never complaining, treat
  the silence as a finding.
