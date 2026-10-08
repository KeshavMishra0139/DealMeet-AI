"""The API has to run on Windows, macOS and Linux.

strftime directives such as '%-d' (glibc and BSD only) or '%#d' (Windows only)
raise or misbehave on the other platforms, so dates are formatted with
engines.common.day_month instead.
"""
import ast
from pathlib import Path

from app.engines.common import day_month

APP = Path(__file__).resolve().parents[1] / "app"


def _strftime_formats():
    for path in sorted(APP.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "strftime":
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        yield path.relative_to(APP.parent), node.lineno, arg.value


def test_strftime_formats_are_portable():
    bad = [f"{p}:{line}: {fmt!r}" for p, line, fmt in _strftime_formats() if "%-" in fmt or "%#" in fmt]
    assert not bad, "Platform-specific strftime directive (use day_month):\n" + "\n".join(bad)


def test_day_month_has_no_leading_zero():
    assert day_month("2026-10-03") == "3 Oct"
    assert day_month("2026-12-25") == "25 Dec"
