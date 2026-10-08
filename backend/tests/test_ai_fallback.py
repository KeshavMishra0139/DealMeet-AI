"""The AI layer must never break the demo: no key, errors, refusals, invalid or
rule-breaking output all fall back to deterministic templates."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.ai import llm
from app.ai.regional import CaptionTag, CaptionTags, tag_captions
from app.config import get_settings


def test_no_key_uses_templates():
    out = tag_captions(["10 நிமிடத்தில் ரவா உப்புமா", "SIP vs FD, simple samjho"])
    assert out["source"] == "template"
    assert [t["language"] for t in out["tags"]] == ["ta", "hinglish"]
    assert [t["niche"] for t in out["tags"]] == ["food", "finance"]


@pytest.fixture()
def fake_ai(monkeypatch, db):
    settings = replace(get_settings(), ai_api_key="test-key", ai_model="test-model")
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    calls = {"n": 0, "output": None, "stop": "end_turn", "raise": None}

    class Messages:
        def parse(self, **kw):
            calls["n"] += 1
            if calls["raise"]:
                raise calls["raise"]
            return SimpleNamespace(stop_reason=calls["stop"], parsed_output=calls["output"])

    monkeypatch.setattr(llm, "_get_client", lambda: SimpleNamespace(messages=Messages()))
    return calls


def _tag(lang="ta"):
    return CaptionTags(tags=[CaptionTag(language=lang, script="Tamil", niche="food", tone="warm", brand_safety_flags=[], confidence="high")])


def test_live_output_is_used_and_cached(fake_ai):
    fake_ai["output"] = _tag()
    out, src = llm.generate("t1", "prompt-a", CaptionTags, lambda: _tag("en"))
    assert src == "ai" and out.tags[0].language == "ta"
    out, src = llm.generate("t1", "prompt-a", CaptionTags, lambda: _tag("en"))
    assert src == "cache" and fake_ai["n"] == 1


def test_refusal_falls_back(fake_ai):
    fake_ai["stop"], fake_ai["output"] = "refusal", None
    out, src = llm.generate("t2", "prompt-b", CaptionTags, lambda: _tag("en"))
    assert src == "template" and out.tags[0].language == "en"


def test_errors_fall_back(fake_ai):
    fake_ai["raise"] = RuntimeError("network down")
    _, src = llm.generate("t3", "prompt-c", CaptionTags, lambda: _tag("en"))
    assert src == "template"


def test_promises_in_ai_output_are_rejected(fake_ai):
    from app.engines.roadmap import TopicIdea, TopicIdeas

    fake_ai["output"] = TopicIdeas(ideas=[TopicIdea(native="x", english="x", why="This is guaranteed to work")])
    _, src = llm.generate("t4", "prompt-d", TopicIdeas, lambda: TopicIdeas(ideas=[]))
    assert src == "template"


def test_invented_numbers_are_rejected(fake_ai):
    from app.engines.roadmap import TopicIdea, TopicIdeas

    fake_ai["output"] = TopicIdeas(ideas=[TopicIdea(native="x", english="x", why="Gets 45000 views")])
    _, src = llm.generate("t5", "prompt-e", TopicIdeas, lambda: TopicIdeas(ideas=[]), facts="Median views 129500")
    assert src == "template"
