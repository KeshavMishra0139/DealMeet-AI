"""The API has to run on Windows, macOS and Linux.

strftime directives such as '%-d' (glibc and BSD only) or '%#d' (Windows only)
raise or misbehave on the other platforms, so dates are formatted with
engines.common.day_month instead.
"""
import ast
from pathlib import Path

import pytest

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


@pytest.mark.parametrize(
    "encoding,bom",
    [("utf-16", b""), ("utf-8", b"\xef\xbb\xbf"), ("utf-8", b"")],
)
def test_env_file_saved_by_windows_tools_still_loads(tmp_path, monkeypatch, encoding, bom):
    """PowerShell 5.1's `>` writes UTF-16 and old Notepad adds a UTF-8 BOM."""
    from app import config

    env = tmp_path / ".env"
    env.write_bytes(bom + "# keys\r\nJD_TEST_KEY=abc123\r\n".encode(encoding))
    monkeypatch.delenv("JD_TEST_KEY", raising=False)
    config._load_dotenv(env)
    import os

    assert os.environ["JD_TEST_KEY"] == "abc123"
    monkeypatch.delenv("JD_TEST_KEY")


def test_unreadable_env_file_gives_a_clear_message(tmp_path):
    from app import config

    env = tmp_path / ".env"
    env.write_bytes(b"KEY=\xff\xfa\xfb")
    with pytest.raises(RuntimeError, match="save it as UTF-8"):
        config._load_dotenv(env)
