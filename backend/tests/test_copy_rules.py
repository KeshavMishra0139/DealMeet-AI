"""Fails the build if any user-facing string in the API promises results.

Scans every string constant in backend/app (engine reasons, templates, seed copy).
The web app runs the same rules in frontend/scripts/check-copy.mjs.
"""
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES = json.loads((ROOT / "shared" / "copy-rules.json").read_text(encoding="utf-8"))["banned"]
PATTERNS = [(re.compile(r["pattern"], re.IGNORECASE), r["why"]) for r in RULES]


def _strings(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value


def test_no_promises_in_api_copy():
    problems = []
    for path in sorted((ROOT / "backend" / "app").rglob("*.py")):
        for line, text in _strings(path):
            for rx, why in PATTERNS:
                if rx.search(text):
                    problems.append(f"{path.relative_to(ROOT)}:{line}: {text[:80]!r} ({why})")
    assert not problems, "Banned copy found:\n" + "\n".join(problems)


def test_rules_catch_examples():
    bad = ["Guaranteed income", "you will go viral", "Overnight growth", "100% sure", "a viral hit"]
    good = ["Estimate, not a promise", "Rs 14K to 19K a month if you post 3 reels a week"]
    for s in bad:
        assert any(rx.search(s) for rx, _ in PATTERNS), s
    for s in good:
        assert not any(rx.search(s) for rx, _ in PATTERNS), s


def test_api_responses_have_no_promises(client, db):
    """Runtime copy (engine output) is checked too, not just source strings."""
    paths = ["/api/creators/cr_a", "/api/creators/cr_b", "/api/meta", "/api/auth/personas"]
    for p in paths:
        body = client.get(p).text
        for rx, why in PATTERNS:
            assert not rx.search(body), f"{p}: {why}"
