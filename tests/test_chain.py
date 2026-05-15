"""Smoke tests for ChainResult.

Run with:
    pytest tests/
"""

from module._chain import ChainResult


def _add_one(x: int) -> int:
    return x + 1


def _double(x: int) -> int:
    return x * 2


def _explode(_x):
    raise RuntimeError("boom")


def test_chain_basic_flow():
    result = (
        ChainResult.of(1)
        .pipe(_add_one)
        .pipe(_double)
        .collect()
    )
    assert result.ok is True
    assert result.value == 4
    assert len(result.steps) == 3  # of + 2 pipes


def test_chain_short_circuits_on_error():
    result = (
        ChainResult.of(1)
        .pipe(_add_one)
        .pipe(_explode)
        .pipe(_double)  # should be skipped
        .collect()
    )
    assert result.ok is False
    assert len(result.errors) == 1
    assert result.errors[0]["name"] == "_explode"
    skipped = [s for s in result.steps if s["skipped"]]
    assert len(skipped) == 1
    assert skipped[0]["name"] == "_double"


def test_chain_where_predicate_skips():
    result = (
        ChainResult.of(1)
        .pipe(_add_one)
        .where(lambda v: v > 100)
        .pipe(_double)  # should be skipped
        .collect()
    )
    assert result.ok is True
    skipped = [s for s in result.steps if s["skipped"]]
    assert len(skipped) == 2  # where itself + the downstream pipe


def test_chain_observer_fires():
    seen = []
    (
        ChainResult.of(1)
        .on("*", lambda step: seen.append(step["name"]))
        .pipe(_add_one)
        .pipe(_double)
        .collect()
    )
    assert "of" in seen
    assert "_add_one" in seen
    assert "_double" in seen
