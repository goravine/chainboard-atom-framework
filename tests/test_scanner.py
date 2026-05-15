"""Smoke test: importing module runs the scanner without error.

If you ship a violation, this test will fail with ScannerError — which is the
correct behavior. The test confirms the seed template passes.
"""


def test_module_imports_cleanly():
    # The actual assertion is "this import does not raise."
    import module  # noqa: F401


def test_example_workflow_returns_uppercase():
    from module.services import run_example_workflow

    result = run_example_workflow("hello")
    assert result.ok is True
    assert result.value == "HELLO"
