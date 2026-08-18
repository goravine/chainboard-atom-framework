"""Scanner tests — the straight-line clause gets a firing test AND a quiet test.

The firing test exists because this clause was dead code from birth: the parent
map was built over the chain expression's own subtree, so the upward walk died
at the subtree root and a chain constructed inside a `for`/`if` body passed the
scan. A rule with no witnessed rejection is a rule whose liveness is unproven.
"""

import os
import tempfile
import unittest

from module._scanner import _scan_file, _validate_chain


def _scan_source(source):
    fd, path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(source)
        chains, errors = _scan_file(path)
        assert errors == []
        return chains
    finally:
        os.unlink(path)


class TestStraightLineClause(unittest.TestCase):
    def test_chain_inside_for_fires(self):
        chains = _scan_source(
            "def f(items):\n"
            "    for item in items:\n"
            "        result = ChainResult.of(item).pipe(step_one)\n"
        )
        self.assertEqual(len(chains), 1)
        errors = _validate_chain(chains[0])
        self.assertTrue(any("straight-line" in e for e in errors), errors)

    def test_chain_inside_if_fires(self):
        chains = _scan_source(
            "def f(cond, x):\n"
            "    if cond:\n"
            "        result = ChainResult.of(x).pipe(step_one)\n"
        )
        self.assertEqual(len(chains), 1)
        errors = _validate_chain(chains[0])
        self.assertTrue(any("straight-line" in e for e in errors), errors)

    def test_chain_at_function_level_stays_quiet(self):
        chains = _scan_source(
            "def f(x):\n"
            "    result = ChainResult.of(x).pipe(step_one).collect()\n"
            "    return result\n"
        )
        self.assertEqual(len(chains), 1)
        self.assertEqual(_validate_chain(chains[0]), [])

    def test_chain_at_module_level_stays_quiet(self):
        chains = _scan_source("result = ChainResult.of(1).pipe(step_one).collect()\n")
        self.assertEqual(len(chains), 1)
        self.assertEqual(_validate_chain(chains[0]), [])


class TestExistingClausesStillFire(unittest.TestCase):
    def test_duplicate_step_name_fires(self):
        chains = _scan_source("result = ChainResult.of(1).pipe(step_one).pipe(step_one)\n")
        errors = _validate_chain(chains[0])
        self.assertTrue(any("Duplicate step name" in e for e in errors), errors)

    def test_observer_after_pipe_fires(self):
        chains = _scan_source('result = ChainResult.of(1).pipe(step_one).on("err", handle)\n')
        errors = _validate_chain(chains[0])
        self.assertTrue(any(".on()" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
