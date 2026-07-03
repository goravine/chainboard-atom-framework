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


# === Rule 0: the scanner scans itself ===

def _repo_root():
    from pathlib import Path
    import module._scanner as scanner
    return Path(scanner.__file__).resolve().parent.parent


def test_scanner_integrity_passes_on_seed():
    from module._scanner import _scan_scanner_integrity

    assert _scan_scanner_integrity(_repo_root()) == []


def test_missing_scan_target_is_a_violation(monkeypatch):
    import module._scanner as scanner

    monkeypatch.setattr(
        scanner, "_ACTIVE_CODE_DIRS", ("api_app", "no_such_dir_xyz")
    )
    errors = scanner._scan_scanner_integrity(_repo_root())
    assert any("no_such_dir_xyz" in e and "vacuously" in e for e in errors)


def test_declared_absence_silences_missing_target(monkeypatch):
    import module._scanner as scanner

    monkeypatch.setattr(
        scanner, "_ACTIVE_CODE_DIRS", ("api_app", "no_such_dir_xyz")
    )
    monkeypatch.setattr(
        scanner, "_DECLARED_ABSENT",
        {**scanner._DECLARED_ABSENT, "no_such_dir_xyz": "test declaration"},
    )
    errors = scanner._scan_scanner_integrity(_repo_root())
    assert not any("no_such_dir_xyz" in e for e in errors)


def test_stale_absence_declaration_is_a_violation(monkeypatch):
    import module._scanner as scanner

    monkeypatch.setattr(
        scanner, "_DECLARED_ABSENT",
        {**scanner._DECLARED_ABSENT, "module": "stale — module exists"},
    )
    errors = scanner._scan_scanner_integrity(_repo_root())
    assert any("stale declaration" in e for e in errors)


def test_stale_skip_list_entry_is_a_violation(monkeypatch):
    import module._scanner as scanner

    monkeypatch.setattr(
        scanner, "_HARD_CODED_SCAN_SKIP_FILES",
        set(scanner._HARD_CODED_SCAN_SKIP_FILES) | {"module/gone_forever.py"},
    )
    errors = scanner._scan_scanner_integrity(_repo_root())
    assert any("gone_forever" in e and "stale skip" in e for e in errors)


def test_console_safety_flags_non_cp1252_print(tmp_path):
    from module._scanner import _scan_file_for_console_safety

    bad = tmp_path / "bad.py"
    bad.write_text('print("\u2550\u2550 header")\n', encoding="utf-8")
    errors = _scan_file_for_console_safety(str(bad))
    assert any("Console-safety violation" in e for e in errors)

    good = tmp_path / "good.py"
    good.write_text('print("== header — [OK]")\n', encoding="utf-8")
    assert _scan_file_for_console_safety(str(good)) == []
