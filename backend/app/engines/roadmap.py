"""Growth roadmap: content gaps, what's working, top-3 skills, topic ideas in
the creator's own language, reference twins and a 30-day plan."""
from __future__ import annotations

from pydantic import BaseModel

from ..ai.llm import generate
from ..db import get_db
from ..seed.catalog import LANGS, NICHES
from ..seed.twins import GENERIC, TWINS
from . import brand_safety, metrics
from .common import count_range, inp, percentile, short, why

LANG_NAMES = {k: v["label"] for k, v in LANGS.items()}


class TopicIdea(BaseModel):
    native: str
    english: str
    why: str


class TopicIdeas(BaseModel):
    ideas: list[TopicIdea]


TOPIC_TEMPLATES: dict[tuple[str, str], list[tuple[str, str, str]]] = {
    ("anime_edits", "hi"): [
        ("फाइट सीन ब्रेकडाउन, हिंदी कमेंट्री के साथ", "Fight-scene breakdown with Hindi commentary", "Your own voice makes the edit original and lowers copyright risk."),
        ("30 सेकंड में किरदार की कहानी", "A character's story in 30 seconds", "Recaps get saved and shared more than pure edits."),
        ("हफ़्ते के टॉप 5 एडिट, मेरी राय के साथ", "Top 5 edits of the week, with my take", "A weekly series gives people a reason to come back."),
    ],
    ("anime_edits", "hinglish"): [
        ("Is fight scene mein kya khaas hai: Hindi commentary", "What makes this fight scene special: Hindi commentary", "Commentary turns a clip into your own work."),
        ("30 second mein character ki kahani", "A character's story in 30 seconds", "Recaps get saved and shared."),
        ("Hafte ke top 5 edits, meri raay ke saath", "Top 5 edits of the week, with my take", "A weekly series builds habit."),
    ],
    ("food", "ta"): [
        ("10 நிமிட காலை டிபன்", "10-minute breakfasts", "Your most-saved topic, and few Tamil creators cover it."),
        ("ஒரே மாவில் 3 டிபன்", "Three tiffins from one batter", "Practical for working families, so people save it."),
        ("லஞ்ச் பாக்ஸ் டிபன் ஐடியாக்கள்", "Lunchbox tiffin ideas", "Pairs naturally with masala and kitchenware brands."),
    ],
    ("food", "te"): [
        ("10 నిమిషాల ఉదయం టిఫిన్", "10-minute breakfasts", "Quick, practical recipes get saved."),
        ("ఒకే పిండితో 3 టిఫిన్లు", "Three tiffins from one batter", "Useful for busy weekday mornings."),
        ("లంచ్ బాక్స్ ఐడియాలు", "Lunchbox ideas", "Fits kitchenware and masala brands."),
    ],
    ("food", "hi"): [
        ("10 मिनट का नाश्ता", "10-minute breakfasts", "Quick, practical recipes get saved."),
        ("एक आटे से 3 नाश्ते", "Three breakfasts from one dough", "Useful for busy weekday mornings."),
        ("टिफ़िन बॉक्स आइडिया", "Tiffin box ideas", "Fits kitchenware and masala brands."),
    ],
    ("finance", "hi"): [
        ("पहली सैलरी का बजट", "Budget for your first salary", "First-time earners search for this every month."),
        ("टैक्स बचाने के 3 सही तरीके", "Three legitimate ways to save tax", "Seasonal demand peaks before filing deadlines."),
        ("इमरजेंसी फंड कितना हो", "How big should an emergency fund be", "Simple, save-worthy explainers."),
    ],
    ("fitness", "hi"): [
        ("10 मिनट सुबह योग", "10-minute morning yoga", "Short routines fit busy mornings."),
        ("घर पर बिना सामान वर्कआउट", "No-equipment home workout", "Removes the gym barrier."),
        ("ऑफिस के बाद स्ट्रेचिंग", "Stretching after office hours", "Relatable for desk workers."),
    ],
}
GENERIC_TOPICS = {
    "anime_edits": [("Commentary edits", "Commentary edits", "Original voice lowers copyright risk.")],
    "food": [("Quick breakfasts", "Quick breakfasts", "Practical recipes get saved.")],
}


def _primary_lang(c: dict) -> str:
    langs = c.get("languages") or ["en"]
    for lang in langs:
        if lang != "en":
            return lang
    return langs[0]


def _peers(c: dict) -> list[dict]:
    lang = _primary_lang(c)
    out = []
    for p in get_db().creators.find({"niche": c["niche"], "_id": {"$ne": c["_id"]}}, {"reels": 1, "languages": 1, "seed_low_trust": 1}):
        if lang in (p.get("languages") or []) or (lang in ("hi", "hinglish") and set(p.get("languages") or []) & {"hi", "hinglish"}):
            out.append(p)
    return out


def working(c: dict) -> list[dict]:
    topics = [t for t in metrics.by_topic(c) if t["count"] >= 2]
    sim = metrics.fields_simulated(c, "reels.topic")
    out = []
    for t in topics[:2]:
        saved = t["save_rate"] is not None  # YouTube videos don't report saves
        out.append(
            {
                "topic": t["topic"],
                "median_views": round(t["median_views"]),
                "count": t["count"],
                "save_rate": round(t["save_rate"], 4) if saved else None,
                "why": why(
                    [f"{t['count']} {metrics.post_word(t['topic'])} in this format, median {short(t['median_views'])} views."]
                    + ([f"{t['save_rate'] * 100:.1f}% of viewers saved them."] if saved else []),
                    [inp("Views", short(t["median_views"]), metrics.prov(c, "reels.0.views"))]
                    + ([inp("Saves per view", f"{t['save_rate'] * 100:.1f}%", metrics.prov(c, "reels.0.saves"))] if saved else []),
                    sim + (metrics.fields_simulated(c, "reels.saves") if saved else []),
                    title=f"Why keep {t['topic'].lower()}",
                ),
            }
        )
    return out


def content_gaps(c: dict) -> list[dict]:
    gaps = []
    lang = _primary_lang(c)
    lang_name = LANG_NAMES.get(lang, "")
    topics = metrics.by_topic(c)
    peers = _peers(c)
    reels = c.get("reels") or []
    for t in topics:
        if t["save_rate"] is None:
            continue  # gaps are found from saves, which YouTube videos don't report
        rest = [r for r in reels if r.get("topic") != t["topic"] and r.get("saves") is not None]
        rest_views = sum(r["views"] for r in rest) or 1
        rest_rate = sum(r["saves"] for r in rest) / rest_views
        lift = t["save_rate"] / rest_rate if rest_rate else 1
        posting = sum(1 for p in peers if any(r.get("topic") == t["topic"] for r in p.get("reels") or []))
        supply = posting / len(peers) if peers else 1
        if lift >= 1.5 and supply <= 0.34 and t["count"] >= 2:
            gaps.append(
                {
                    "id": f"topic:{t['topic']}",
                    "title": f"{lang_name} {metrics.topic_plural(t['topic'])}".strip(),
                    "kind": "topic",
                    "evidence": [
                        f"Your {t['count']} {metrics.topic_plural(t['topic'])} got {lift:.1f}x the saves of your other reels.",
                        f"Only {posting} of {len(peers)} {lang_name} {NICHES[c['niche']]['label'].lower()} creators here {'posts' if posting == 1 else 'post'} them.",
                    ],
                    "lift": round(lift, 2),
                    "supply": f"{posting} of {len(peers)}",
                    "why": why(
                        ["High demand from your own audience, low supply from peers in your language."],
                        [inp("Saves lift", f"{lift:.1f}x"), inp("Peers posting it", f"{posting} of {len(peers)}")],
                        metrics.fields_simulated(c, "reels.saves", "reels.topic"),
                        title="How we found this gap",
                        source="Peers: creators in the same niche who post in your language. Only consented insights are compared.",
                    ),
                }
            )
    if brand_safety.assess(c)["flags"] and any(f["id"] == "copyrighted_clips" for f in brand_safety.assess(c)["flags"]):
        original = sum(1 for p in peers if any(r.get("original_voiceover") for r in p.get("reels") or []))
        voice_lang = "Hindi" if lang in ("hi", "hinglish") else lang_name or "your own"
        gaps.append(
            {
                "id": "voiceover",
                "title": f"Edits with original {voice_lang} voiceover or commentary",
                "kind": "format",
                "evidence": [
                    "Your edits are built from show clips, which brands see as a copyright risk.",
                    f"Only {original} of {len(peers)} similar creators here {'adds' if original == 1 else 'add'} their own voice, so it would set you apart.",
                    "A creator in your niche is looking for a Hindi voiceover partner right now.",
                ],
                "why": why(
                    [
                        "Original voiceover or commentary makes the edit your own work.",
                        "It lowers copyright risk, which removes a brand-safety penalty from your price.",
                    ],
                    [inp("Brand-safety penalty today", "-6%")],
                    title="Why add your voice",
                ),
            }
        )
    return gaps


def skills(c: dict, stage_id: str, paths: list[dict]) -> list[dict]:
    out = []
    safety = brand_safety.assess(c)
    if any(f["id"] == "copyrighted_clips" for f in safety["flags"]):
        out.append(("Voiceover and scripting", "Write 3 lines of commentary per edit and record on your phone.", "Removes the copyright penalty and makes edits yours."))
    if stage_id == "underpriced":
        out.append(("Pricing and negotiation", "Quote from your price breakdown and hold your rate once.", "You're quoting well below what your reach supports."))
    if "Basic editing" in (c.get("skill_gaps") or []):
        out.append(("Basic editing: cuts, captions, a first-second hook", "Learn jump cuts and auto-captions in a free phone editor (2 hours).", f"Tighter {metrics.post_noun(c)}s keep people watching past the first second."))
    top3 = [p["type"] for p in paths[:3]]
    if "digital" in top3 and c["niche"] == "food":
        out.append(("Writing and pricing a recipe e-book", "Pick 10 recipes, photograph each, price at ₹199.",
                    "Your saves show people want to keep these recipes." if metrics.ss_known(c) else "Recipes are what people keep and come back to."))
    if c["niche"] == "food":
        out.append(("Phone food photography", "Shoot near a window at mid-morning; one overhead, one side angle.", "Better thumbnails lift saves and product sales."))
    if c.get("platforms") == ["instagram"] and metrics.has_reels(c) and metrics.reach_ratio(c) > 1:
        out.append(("Repurposing to YouTube Shorts", "Re-upload your top 5 reels as Shorts, one a day.", "Your content travels well; a second platform widens reach."))
    if c.get("followers", 0) < 1_000 and c.get("expertise"):
        out.append(("Short explainers from your expertise", f"Turn the 5 questions clients ask most into 30-second {'Shorts' if metrics.platform(c) == 'youtube' else 'reels'}.", "Expertise is your fastest route to trust."))
    out.append(("Hooks in the first second", "Open with the result, then show how.", "Most viewers decide in the first second."))
    seen, result = set(), []
    for title, action, reason in out:
        if title not in seen:
            seen.add(title)
            result.append({"rank": len(result) + 1, "title": title, "action": action, "reason": reason})
    return result[:3]


def twins(c: dict) -> list[dict]:
    lang = _primary_lang(c)
    key = f"{c['niche']}:{lang}"
    data = TWINS.get(key) or TWINS.get(c["niche"]) or GENERIC
    out = []
    for i, t in enumerate(data[:3]):
        followers = t["followers"] or int(max(c.get("followers", 1_000), 1_000) * (3 + i * 4))
        out.append(
            {
                "id": f"twin_{i + 1}",
                "name": t["name"],
                "followers": followers,
                "platform": t["platform"],
                "languages": [LANG_NAMES.get(x, x) for x in (t["languages"] or c.get("languages", []))],
                "steps": t["steps"],
                "lesson": t["lesson"],
                "label": "Mock public profile for illustration",
            }
        )
    return out


def topic_ideas(c: dict, gaps: list[dict]) -> dict:
    lang = _primary_lang(c)
    key = (c["niche"], lang)
    template = TOPIC_TEMPLATES.get(key) or TOPIC_TEMPLATES.get((c["niche"], "hi" if lang == "hinglish" else lang))
    if not template:
        reason = "Matches what your audience saves." if metrics.ss_known(c) else "Matches what your audience watches most."
        base = GENERIC_TOPICS.get(c["niche"], [(f"{t}", t, reason) for t in (x["topic"] for x in metrics.by_topic(c)[:3])])
        template = base or [("Your best format, weekly", "Your best format, weekly", "Consistency builds habit.")]

    def fallback() -> TopicIdeas:
        return TopicIdeas(ideas=[TopicIdea(native=n, english=e, why=w) for n, e, w in template])

    facts = (
        f"Niche: {NICHES[c['niche']]['label']}. Writes in: {LANG_NAMES.get(lang, lang)}. "
        f"Best formats: {', '.join(t['topic'] for t in metrics.by_topic(c)[:2]) or 'unknown'}. "
        f"Gaps: {'; '.join(g['title'] for g in gaps) or 'none found'}."
    )
    prompt = (
        f"{facts}\nSuggest 3 short reel topic ideas this creator could post next. Write `native` in "
        f"{LANG_NAMES.get(lang, lang)} using its native script (romanised Hindi if the language is Hinglish), "
        "`english` as a plain translation, and `why` as one short sentence grounded only in the facts."
    )
    result, source = generate("topic_ideas", prompt, TopicIdeas, fallback, facts=facts, max_tokens=700)
    return {"language": LANG_NAMES.get(lang, lang), "ideas": [i.model_dump() for i in result.ideas[:3]], "source": source}


def thirty_day_plan(c: dict, moves: list[dict], gaps: list[dict], skill_list: list[dict], paths: list[dict]) -> list[dict]:
    weeks = [
        {"week": 1, "title": "This week's moves", "items": [{"kind": m["category"], "title": m["title"]} for m in moves]},
        {"week": 2, "title": "Close a content gap", "items": []},
        {"week": 3, "title": "Add an income stream", "items": []},
        {"week": 4, "title": "Review and lock in", "items": []},
    ]
    if gaps:
        g = gaps[0] if gaps[0]["kind"] != "voiceover" or len(gaps) == 1 else gaps[0]
        weeks[1]["items"].append({"kind": "content", "title": f"Post 2 more {g['title']}" if g["kind"] == "topic" else f"Make your first {g['title'][0].lower() + g['title'][1:]}"})
    if skill_list:
        weeks[1]["items"].append({"kind": "skill", "title": f"Practise: {skill_list[0]['title'].lower()}"})
    for p in paths[:3]:
        if p["type"] not in ("brand",):
            weeks[2]["items"].append({"kind": "money", "title": p["first_step"]})
            break
    if len(skill_list) > 1:
        weeks[2]["items"].append({"kind": "skill", "title": f"Practise: {skill_list[1]['title'].lower()}"})
    weeks[3]["items"] += [
        {"kind": "review", "title": "Compare saves on new reels against your usual ones" if metrics.ss_known(c) else f"Compare views on new {metrics.post_noun(c)}s against your usual ones"},
        {"kind": "money", "title": "Update your rate card from your latest price breakdown"},
    ]
    return weeks


def build(c: dict, stage_id: str, moves: list[dict], paths: list[dict]) -> dict:
    gaps = content_gaps(c)
    skill_list = skills(c, stage_id, paths)
    work = working(c)
    return {
        "working": work,
        "gaps": gaps,
        "skills": skill_list,
        "twins": twins(c),
        "topics": topic_ideas(c, gaps),
        "plan": thirty_day_plan(c, moves, gaps, skill_list, paths),
        "views_range": count_range(percentile([r["views"] for r in metrics.recent(c)], 0.25), percentile([r["views"] for r in metrics.recent(c)], 0.75)) if metrics.has_reels(c) else None,
    }
