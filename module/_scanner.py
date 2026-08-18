"""Scanner — the framework's import-time immune system.

Importing `module` runs `validate_chains()` (which also runs the hardcoding /
import-law / shape policies). The scanner is not optional decoration. It is
part of the framework contract.

Rules enforced:

  Chain shape (across all module/*.py except _private files and services*):
    - Chains must start with `.of(...)`
    - Step names must be unique within a chain
    - Observers (`.on(...)`) must be registered before any `.pipe(...)`
    - Chains must be straight-line: no construction inside `if`/`for`/`while`/`with`

  Hardcoding policies (across api_app, module, sdk, tools):
    - No hardcoded runtime URLs / hosts / domain literals
    - No config-like function-argument defaults (args named *_url, *_secret,
      *_token, *_bucket, *_key, etc., must not have non-trivial string defaults)

  Import law:
    - Atoms (module/atoms/*) must not import api_app, sdk, services_*, or boards
    - Higher layers (api_app, sdk, tools) must not import atoms directly
    - Boards must import `module.services` (the gate), not private `module/services_*` children
    - External callers must import `module.services` (the gate), not the children directly

  File shape:
    - `module/services.py` (the gate) must stay small: <= 350 lines, <= 20 functions
    - Board files must stay focused: <= 180 lines, <= 16 public methods
    - Board file naming: `<noun>.py` defines a single `<Noun>Board` class
      (CamelCase of the stem). Overrides are explicit, not silent.

  Console safety (across api_app, module, sdk, tools — scanner included):
    - String literals passed to print() must encode to cp1252. A box-drawing
      char or emoji in a diagnostic message CRASHES the scanner on a Windows
      console (UnicodeEncodeError) instead of reporting the violation — the
      immune system must not be killable by its own output.

  Rule 0 — the scanner scans itself (no vacuous rules):
    - Every scan target the scanner is configured to check must exist on
      disk, or be declared absent in _DECLARED_ABSENT with a justification.
      "Cannot check" is a violation, not a skip — a rule whose target moved
      passes vacuously forever, and a green scanner nobody doubts is where
      architecture rot hides.
    - Skip-list entries (_HARD_CODED_SCAN_SKIP_FILES) must point at files
      that exist. A stale skip silently exempts any future file that
      reappears under that name.
    - Absence declarations must stay true: a _DECLARED_ABSENT path that
      exists on disk is a stale declaration and fails the scan.
    - An active code dir that exists but yields zero scanned files is a
      vacuity violation — the rule ran against nothing.

If your project needs to relax any rule, edit this file with intent — never
add silent escape hatches. The skip list is _HARD_CODED_SCAN_SKIP_FILES; every
entry should be justified by a comment.

See PROTOCOL.md for the full framework contract.
"""

import ast
import re
from pathlib import Path


class ScannerError(Exception):
    pass


# === policy configuration ===

_ACTIVE_CODE_DIRS = ("api_app", "module", "sdk", "tools")

_HARD_CODED_SCAN_SKIP_FILES = {
    # The scanner mentions URLs/hosts inside its own pattern definitions.
    "module/_scanner.py",
}

# Literal prefixes that ARE allowed even in active code (test fixtures,
# RFC-reserved domains, official well-known endpoints used as constants).
_ALLOWED_LITERAL_PREFIXES = (
    "http://localhost:",
    "http://127.0.0.1:",
    "https://example.invalid",
    "http://example.invalid",
)

# Exact literals on the allowlist (one-off well-known constants).
_ALLOWED_LITERAL_EXACT = {
    "https://www.googleapis.com/auth/cloud-platform",
}

# Argument-name tokens that mark a param as "config-shaped" → no string default.
_CONFIGISH_ARG_TOKENS = (
    "url",
    "uri",
    "endpoint",
    "host",
    "bucket",
    "secret",
    "token",
    "key",
    "spreadsheet",
    "project",
    "domain",
    "origin",
)

# Generic suspicious-literal pattern. Tune this regex per-project for
# environment-coupled domains you want the scanner to flag.
#
# Default catches any http(s) URL. Override or extend for project-specific
# domains: e.g. add `r"yourcompany\.com|some-internal-host"` to flag those
# too even without an http prefix.
_SUSPICIOUS_LITERAL_PATTERN = re.compile(
    r"(https?://)",
    re.IGNORECASE,
)

# Service gate + child convention.
_SERVICE_GATE_FILE = "module/services.py"
_SERVICE_CHILD_PREFIX = "module/services_"

# All public Board surface modules (per project), used to validate that
# atoms don't reach upward. Populate at scaffold time and grow as boards
# are added. Each entry is a module path WITHOUT the trailing `.py`.
_BOARD_MODULE_PREFIXES = (
    "module.example",  # the seed example board — replace as you add boards
)

# Shape budgets.
_MAX_SERVICE_GATE_LINES = 350
_MAX_SERVICE_GATE_FUNCTIONS = 20
_MAX_BOARD_SURFACE_LINES = 180
_MAX_BOARD_PUBLIC_METHODS = 16

# Naming-protocol exceptions: stem -> expected class name. Use sparingly —
# every override is a deliberate readability tradeoff.
_BOARD_CLASS_NAME_OVERRIDES = {
    # "tooling": "ToolBoard",   # example: when noun != stem
}

# Rule 0: paths the scanner is configured to check that are LEGITIMATELY
# absent in this project. Every entry needs a justification comment — an
# undeclared missing target is a violation (the rule would pass vacuously),
# and a declared path that EXISTS is a stale declaration (also a violation).
# Keys are repo-relative posix paths (dirs or files).
_DECLARED_ABSENT = {
    # The seed template ships no tools/ dir. When your project adds one,
    # the stale-declaration check forces you to delete this line — and the
    # hardcoding/import-law rules start running against it that instant.
    "tools": "seed template ships no dev tooling; populate per project",
}


def _snake_to_camel(name):
    parts = [part for part in str(name or "").split("_") if part]
    return "".join(part[:1].upper() + part[1:] for part in parts)


def _extract_chain_calls(node):
    calls = []
    current = node
    while isinstance(current, ast.Call):
        if isinstance(current.func, ast.Attribute):
            calls.append((current.func.attr, current))
            current = current.func.value
        else:
            break
    return list(reversed(calls))


def _get_step_name(call_node):
    if not call_node.args:
        return None
    arg = call_node.args[0]
    if isinstance(arg, ast.Name):
        return arg.id
    elif isinstance(arg, ast.Attribute):
        return arg.attr
    elif isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute):
        return arg.func.attr
    return None


def _scan_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [], [f"Syntax error in {filepath}: {e}"]

    chains = []
    parent_map = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.Return)):
            if isinstance(node.value, ast.Call):
                calls = _extract_chain_calls(node.value)
                if calls and calls[0][0] == "of":
                    if parent_map is None:
                        # Whole-FILE map: the straight-line walk must be able to
                        # leave the chain expression and reach the control flow
                        # that encloses it. A map built over the chain's own
                        # subtree cannot contain those ancestors, so the walk
                        # dies at the root and the rule never fires.
                        parent_map = _build_parent_map(tree)
                    chains.append({
                        "file": filepath,
                        "line": node.lineno,
                        "calls": calls,
                        "node": node.value,
                        "parent_map": parent_map,
                    })

    return chains, []


def _validate_chain(chain):
    errors = []
    calls = chain["calls"]

    first_pipe_idx = None
    last_on_idx = None
    for i, (method, _) in enumerate(calls):
        if method == "pipe" and first_pipe_idx is None:
            first_pipe_idx = i
        elif method == "on":
            last_on_idx = i

    if (
        first_pipe_idx is not None
        and last_on_idx is not None
        and last_on_idx > first_pipe_idx
    ):
        errors.append(
            f"Observer .on() registered after .pipe() at {chain['file']}:{chain['line']}"
        )

    step_names = {}
    for method, call_node in calls:
        if method == "pipe":
            step_name = _get_step_name(call_node)
            if step_name:
                if step_name in step_names:
                    errors.append(
                        f"Duplicate step name '{step_name}' in chain at {chain['file']}: "
                        f"line {step_names[step_name]} and line {call_node.lineno}"
                    )
                else:
                    step_names[step_name] = call_node.lineno

    parent_map = chain["parent_map"]

    node = chain["node"]
    while node:
        if node in parent_map:
            parent = parent_map[node]
            if isinstance(parent, (ast.If, ast.For, ast.While, ast.With)):
                errors.append(
                    f"Dynamic chain construction at {chain['file']}:{parent.lineno} — chains must be straight-line"
                )
                break
            node = parent
        else:
            break

    return errors


def _build_parent_map(tree):
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def _is_docstring_constant(node, parent_map):
    parent = parent_map.get(node)
    if not isinstance(parent, ast.Expr):
        return False
    grandparent = parent_map.get(parent)
    return isinstance(grandparent, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))


def _is_allowed_literal(text):
    value = str(text or "").strip()
    if not value:
        return True
    if value in _ALLOWED_LITERAL_EXACT:
        return True
    return any(value.startswith(prefix) for prefix in _ALLOWED_LITERAL_PREFIXES)


def _scan_file_for_hardcoded_runtime_literals(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"Syntax error in {filepath}: {exc}"]

    parent_map = _build_parent_map(tree)
    errors = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if _is_docstring_constant(node, parent_map):
            continue
        literal = node.value.strip()
        if not literal or _is_allowed_literal(literal):
            continue
        if not _SUSPICIOUS_LITERAL_PATTERN.search(literal):
            continue
        preview = literal if len(literal) <= 120 else f"{literal[:117]}..."
        errors.append(
            f"Hardcoded runtime literal at {filepath}:{node.lineno} — {preview!r}"
        )
    return errors


def _scan_file_for_configish_defaults(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"Syntax error in {filepath}: {exc}"]

    errors = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        positional = list(node.args.args or [])
        positional_defaults = list(node.args.defaults or [])
        start = len(positional) - len(positional_defaults)
        for arg_node, default_node in zip(positional[start:], positional_defaults):
            arg_name = str(arg_node.arg or "").lower()
            if not any(token in arg_name for token in _CONFIGISH_ARG_TOKENS):
                continue
            if isinstance(default_node, ast.Constant) and isinstance(default_node.value, str):
                value = default_node.value.strip()
                if value and not _is_allowed_literal(value):
                    errors.append(
                        f"Config-like arg default at {filepath}:{default_node.lineno} — "
                        f"{arg_node.arg}={value!r}"
                    )
    return errors


def _iter_print_string_parts(call_node):
    for arg in call_node.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            yield arg.value, arg.lineno
        elif isinstance(arg, ast.JoinedStr):
            for part in arg.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    yield part.value, arg.lineno


def _scan_file_for_console_safety(filepath):
    """String literals printed to the console must survive cp1252.

    The scanner reports violations by printing; if a diagnostic string
    contains a char outside cp1252 (box-drawing, arrows, emoji), a Windows
    console kills the process with UnicodeEncodeError before the report
    lands. This rule applies to ALL active code including the scanner —
    the immune system must not be killable by its own output.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"Syntax error in {filepath}: {exc}"]

    errors = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "print"):
            continue
        for text, lineno in _iter_print_string_parts(node):
            try:
                text.encode("cp1252")
            except UnicodeEncodeError:
                preview = text if len(text) <= 60 else f"{text[:57]}..."
                errors.append(
                    f"Console-safety violation at {filepath}:{lineno} — "
                    f"print() literal {preview!r} does not survive cp1252; "
                    f"use ASCII markers ([OK]/[FAIL]) in console output"
                )
    return errors


def _extract_imported_modules(tree):
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append((str(alias.name or ""), node.lineno))
        elif isinstance(node, ast.ImportFrom):
            module_name = str(node.module or "").strip()
            if module_name:
                modules.append((module_name, node.lineno))
    return modules


def _scan_file_for_import_law(filepath, repo_root):
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"Syntax error in {filepath}: {exc}"]

    relative_path = Path(filepath).resolve().relative_to(repo_root).as_posix()
    errors = []
    imported_modules = _extract_imported_modules(tree)

    for module_name, lineno in imported_modules:
        # Atom import-law: atoms cannot reach upward.
        if relative_path.startswith("module/atoms/"):
            if module_name.startswith("api_app") or module_name.startswith("sdk"):
                errors.append(
                    f"Atom import-law violation at {filepath}:{lineno} — "
                    f"atoms must not import {module_name}"
                )
            if module_name == "module.services" or module_name.startswith("module.services_"):
                errors.append(
                    f"Atom import-law violation at {filepath}:{lineno} — "
                    f"atoms must not import service layers"
                )
            if any(
                module_name == board_prefix or module_name.startswith(f"{board_prefix}.")
                for board_prefix in _BOARD_MODULE_PREFIXES
            ):
                errors.append(
                    f"Atom import-law violation at {filepath}:{lineno} — "
                    f"atoms must not import board layers"
                )

        # Higher layers cannot reach into atoms directly.
        if relative_path.startswith(("api_app/", "sdk/", "tools/")):
            if module_name.startswith("module.atoms"):
                errors.append(
                    f"Architecture import-law violation at {filepath}:{lineno} — "
                    f"higher layers must not import atoms directly"
                )

        # Boards and module surface files must go through the service gate,
        # not directly into atoms.
        if relative_path.startswith("module/") and not relative_path.startswith(
            ("module/atoms/", "module/services", "module/_")
        ):
            if module_name.startswith("module.atoms"):
                errors.append(
                    f"Board/module import-law violation at {filepath}:{lineno} — "
                    f"boards must import module.services instead of atoms directly"
                )

        # Service-gate boundary: external callers must hit `module.services`,
        # not the private children (`module.services_*`).
        if module_name.startswith("module.services_"):
            if relative_path != _SERVICE_GATE_FILE and not relative_path.startswith(
                _SERVICE_CHILD_PREFIX
            ):
                errors.append(
                    f"Service-gate violation at {filepath}:{lineno} — "
                    f"import module.services instead of private child services"
                )

    return errors


def _scan_service_gate_shape(repo_root):
    filepath = repo_root / "module" / "services.py"
    if not filepath.exists():
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"Syntax error in {filepath}: {exc}"]

    errors = []
    line_count = len(source.splitlines())
    function_count = sum(
        1 for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    if line_count > _MAX_SERVICE_GATE_LINES:
        errors.append(
            f"Service gate too large at {filepath} — {line_count} lines exceeds {_MAX_SERVICE_GATE_LINES}"
        )
    if function_count > _MAX_SERVICE_GATE_FUNCTIONS:
        errors.append(
            f"Service gate too large at {filepath} — {function_count} functions exceeds {_MAX_SERVICE_GATE_FUNCTIONS}"
        )
    return errors


def _scan_module_naming_protocol(repo_root):
    module_root = repo_root / "module"
    errors = []

    for py_file in module_root.glob("*.py"):
        relative_path = py_file.relative_to(repo_root).as_posix()
        name = py_file.name
        stem = py_file.stem

        if name in {"__init__.py"} or name.startswith("_"):
            continue

        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            errors.append(f"Syntax error in {py_file}: {exc}")
            continue

        class_names = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        ]
        board_class_names = [name for name in class_names if name.endswith("Board")]

        if stem == "services" or stem.startswith("services_"):
            if board_class_names:
                errors.append(
                    f"Naming protocol violation at {relative_path} — "
                    f"service files must not define Board classes"
                )
            continue

        expected_board_name = _BOARD_CLASS_NAME_OVERRIDES.get(
            stem, f"{_snake_to_camel(stem)}Board"
        )
        if not board_class_names:
            errors.append(
                f"Naming protocol violation at {relative_path} — "
                f"board surface files must define {expected_board_name}"
            )
            continue
        if len(board_class_names) != 1:
            errors.append(
                f"Naming protocol violation at {relative_path} — "
                f"board surface files must define exactly one Board class"
            )
            continue
        if board_class_names[0] != expected_board_name:
            errors.append(
                f"Naming protocol violation at {relative_path} — "
                f"expected board class {expected_board_name}, found {board_class_names[0]}"
            )

    return errors


def _scan_board_surface_shape(repo_root):
    module_root = repo_root / "module"
    errors = []

    for py_file in module_root.glob("*.py"):
        name = py_file.name
        stem = py_file.stem
        relative_path = py_file.relative_to(repo_root).as_posix()

        if (
            name == "__init__.py"
            or name.startswith("_")
            or stem == "services"
            or stem.startswith("services_")
        ):
            continue

        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            errors.append(f"Syntax error in {py_file}: {exc}")
            continue

        board_classes = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name.endswith("Board")
        ]
        if len(board_classes) != 1:
            continue

        board_class = board_classes[0]
        public_methods = [
            item.name
            for item in board_class.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not item.name.startswith("_")
        ]
        line_count = len(source.splitlines())

        if line_count > _MAX_BOARD_SURFACE_LINES:
            errors.append(
                f"Board surface too large at {relative_path} — "
                f"{line_count} lines exceeds {_MAX_BOARD_SURFACE_LINES}"
            )
        if len(public_methods) > _MAX_BOARD_PUBLIC_METHODS:
            errors.append(
                f"Board surface too large at {relative_path} — "
                f"{len(public_methods)} public methods exceeds {_MAX_BOARD_PUBLIC_METHODS}"
            )

    return errors


def _scan_scanner_integrity(repo_root):
    """Rule 0: the scanner scans itself — no rule may be vacuous.

    A rule whose target is missing does not fail; it silently checks
    nothing, forever, behind a green scanner everyone trusts. This rule
    makes "cannot check" a violation: every configured scan target must
    exist or be declared absent with a justification, skip-list entries
    must be live, and absence declarations must stay true.
    """
    errors = []

    # Configured scan targets: active dirs + the service gate file.
    expected_targets = list(_ACTIVE_CODE_DIRS) + [_SERVICE_GATE_FILE]
    for target in expected_targets:
        path = repo_root / target
        if path.exists():
            continue
        if target in _DECLARED_ABSENT:
            continue
        errors.append(
            f"Scanner integrity violation — configured scan target "
            f"'{target}' is missing and not declared in _DECLARED_ABSENT; "
            f"its rules would pass vacuously"
        )

    # Absence declarations must stay true.
    for target, justification in _DECLARED_ABSENT.items():
        if (repo_root / target).exists():
            errors.append(
                f"Scanner integrity violation — '{target}' is declared "
                f"absent ({justification!r}) but exists on disk; remove the "
                f"stale declaration so its rules run"
            )

    # Skip-list entries must point at live files.
    for skip in _HARD_CODED_SCAN_SKIP_FILES:
        if not (repo_root / skip).exists():
            errors.append(
                f"Scanner integrity violation — skip-list entry '{skip}' "
                f"does not exist; a stale skip silently exempts any future "
                f"file that reappears under that name"
            )

    return errors


def validate_hardcoding_policies():
    repo_root = Path(__file__).resolve().parent.parent
    fail_mark = "[FAIL]"
    ok_mark = "[OK]"
    print("[SCANNER] Validating scanner integrity (rule 0)...")

    integrity_errors = _scan_scanner_integrity(repo_root)
    if integrity_errors:
        for err in integrity_errors:
            print(f"  {fail_mark} {err}")
        raise ScannerError(
            f"Scanner integrity validation failed ({len(integrity_errors)} error(s))"
        )
    print(f"{ok_mark} scanner integrity validated | 0 errors")

    print("[SCANNER] Validating hardcoding policies...")

    errors = []
    scanned_counts = {}
    for relative_root in _ACTIVE_CODE_DIRS:
        root = repo_root / relative_root
        if not root.exists():
            # Rule 0 already verified this absence is declared.
            continue
        scanned_counts[relative_root] = 0
        for py_file in root.rglob("*.py"):
            relative_path = py_file.relative_to(repo_root).as_posix()
            # Console safety applies to every file — including the skip-listed
            # scanner itself; that is where the crash bites hardest.
            errors.extend(_scan_file_for_console_safety(str(py_file)))
            if relative_path in _HARD_CODED_SCAN_SKIP_FILES:
                continue
            scanned_counts[relative_root] += 1
            errors.extend(_scan_file_for_hardcoded_runtime_literals(str(py_file)))
            errors.extend(_scan_file_for_configish_defaults(str(py_file)))
            errors.extend(_scan_file_for_import_law(str(py_file), repo_root))

    # Vacuity guard: an existing active dir that yielded zero scanned files
    # means the rules ran against nothing — that is not a pass.
    for relative_root, count in scanned_counts.items():
        if count == 0:
            errors.append(
                f"Scanner vacuity violation — active dir '{relative_root}' "
                f"exists but zero python files were scanned; if it is "
                f"intentionally empty, declare it in _DECLARED_ABSENT"
            )

    errors.extend(_scan_service_gate_shape(repo_root))
    errors.extend(_scan_module_naming_protocol(repo_root))
    errors.extend(_scan_board_surface_shape(repo_root))

    if errors:
        for err in errors:
            print(f"  {fail_mark} {err}")
        raise ScannerError(
            f"Hardcoding policy validation failed ({len(errors)} error(s))"
        )

    total_scanned = sum(scanned_counts.values())
    print(
        f"{ok_mark} hardcoding policies validated | 0 errors | "
        f"{total_scanned} file(s) across {len(scanned_counts)} dir(s)"
    )


def validate_chains():
    validate_hardcoding_policies()

    module_dir = Path(__file__).parent
    ok_mark = "[OK]"
    fail_mark = "[FAIL]"
    print("[SCANNER] Validating module chains...")

    all_chains = []
    all_errors = []

    for py_file in module_dir.glob("*.py"):
        if py_file.name.startswith("_") or py_file.name.startswith("services"):
            continue
        chains, errors = _scan_file(str(py_file))
        all_chains.extend(chains)
        all_errors.extend(errors)

    for py_file in module_dir.glob("services*.py"):
        chains, errors = _scan_file(str(py_file))
        all_chains.extend(chains)
        all_errors.extend(errors)

    if all_errors:
        for err in all_errors:
            print(f"  {fail_mark} {err}")
        raise ScannerError(f"Chain scanning failed: {len(all_errors)} error(s)")

    validation_errors = []
    for chain in all_chains:
        errors = _validate_chain(chain)
        if errors:
            validation_errors.extend(errors)
        else:
            step_count = sum(1 for method, _ in chain["calls"] if method == "pipe")
            print(
                f"  {ok_mark} {Path(chain['file']).name}:{chain['line']} — {step_count} step(s)"
            )

    if validation_errors:
        for err in validation_errors:
            print(f"  {fail_mark} {err}")
        raise ScannerError(
            f"Chain validation failed ({len(validation_errors)} error(s))"
        )

    print(f"{ok_mark} {len(all_chains)} chain(s) validated | 0 errors | boot OK")
