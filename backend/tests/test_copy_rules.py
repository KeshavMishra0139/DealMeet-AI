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
    bad = ["Guaranteed income", "you will go viral", "Overnight growth", "100% sure", "a viral hit", "100 % pakka", "गारंटी के साथ", "रातों-रात फ़ेमस"]
    good = ["Estimate, not a promise", "Rs 14K to 19K a month if you post 3 reels a week"]
    for s in bad:
        assert any(rx.search(s) for rx, _ in PATTERNS), s
    for s in good:
        assert not any(rx.search(s) for rx, _ in PATTERNS), s


def test_api_responses_have_no_promises(client, login, db):
    """Runtime copy (engine output, English and Hindi) is checked too, not just source strings."""
    creators = ["cr_a", "cr_b", "cr_n01", "cr_t01", "cr_f08", "cr_g09"] + [c["_id"] for c in db.creators.find({}, {"_id": 1})][::9]
    paths = [(None, "/api/meta"), (None, "/api/auth/personas"), (None, "/api/demo/compare")]
    for cid in dict.fromkeys(creators):
        paths += [(cid, f"/api/creators/{cid}{s}") for s in ("", "/home", "/money", "/roadmap", "/opportunities", "/kit")]
    for bid in ("br_senpai", "br_thalam"):
        paths += [(bid, f"/api/brands/{bid}/console"), (bid, f"/api/brands/{bid}/campaigns")]
    paths += [("br_senpai", "/api/listings/lst_senpai_hoodie/matches"), ("br_thalam", "/api/listings/lst_thalam_collective/matches")]
    actors = {}
    for who, p in paths:
        if who and who not in actors:
            actors[who] = login(who)
        r = (actors[who] if who else client).get(p)
        assert r.status_code == 200, p
        for rx, why in PATTERNS:
            m = rx.search(r.text)
            assert not m, f"{p}: {why} ({r.text[max(0, m.start() - 60):m.end() + 20]!r})"
