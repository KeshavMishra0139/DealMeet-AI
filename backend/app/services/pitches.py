"""AI Pitch Builder and the Brand Fan Inbox.

A pitch is written from the creator's own facts (each with its source), their Fan
Proof and the brand's public info. The model writes only the words, through
`ai/llm.generate` with a strict schema, the copy rules and a check that every number
comes from the facts; the template takes over otherwise. The suggested price range
always comes from the fair-price engine, never from the model.

The creator edits before sending. A brand on the platform gets it in its Fan Inbox;
for a brand that isn't, the creator gets an unguessable, revocable share link to send
themselves. Five sent pitches per creator per week.
"""
from __future__ import annotations

import re
import secrets
import time
import uuid

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError, field_validator

from ..ai.llm import breaks_copy_rules, generate, numbers_grounded
from ..config import now_iso
from ..db import get_db
from ..engines import metrics
from ..engines.common import short
from ..engines.fair_price import fair_price
from ..engines.matching import audience_fit
from ..seed.catalog import LANGS, NICHES
from . import auth as au
from . import consent as cs
from . import fan_proof, offers
from .views import source_of

PER_WEEK = 5
WEEK_S = 7 * 24 * 3600
MAX_WORDS = 150
OPEN = ("sent",)  # awaiting the brand's answer


class PitchCopy(BaseModel):
    subject: str = Field(min_length=3, max_length=90)
    pitch: str = Field(min_length=20, max_length=1200)
    content_ideas: list[str] = Field(min_length=3, max_length=3)

    @field_validator("pitch")
    @classmethod
    def _words(cls, v: str) -> str:
        if len(v.split()) > MAX_WORDS:
            raise ValueError(f"The pitch is over {MAX_WORDS} words")
        return v

    @field_validator("content_ideas")
    @classmethod
    def _ideas(cls, v: list[str]) -> list[str]:
        if any(not 3 <= len(x.strip()) <= 160 for x in v):
            raise ValueError("Each content idea is 3 to 160 characters")
        return [x.strip() for x in v]


# ------------------------------------------------------------------ facts
def facts_for(c: dict, b: dict) -> tuple[list[dict], dict | None]:
    """The creator's numbers a pitch may use, each with its source, and their Fan Proof."""
    facts: list[dict] = []

    def add(key: str, label: str, value: str, source: str):
        facts.append({"key": key, "label": label, "value": value, "source": source})

    add("niche", "Niche", NICHES[c["niche"]]["label"], "manual")
    add("languages", "Languages", ", ".join(LANGS[x]["label"] for x in c.get("languages") or [] if x in LANGS), "manual")
    if c.get("followers"):
        add("followers", "Followers", short(c["followers"]), source_of(c, "followers"))
    if metrics.has_reels(c):
        add("median_views", f"Median views, last {len(metrics.recent(c))} posts", short(metrics.median_views(c)), source_of(c, "reels.0.views"))
        if metrics.ss_known(c):
            add("engagement", "Saves + shares per view", f"{metrics.ss_rate(c) * 100:.1f}%", source_of(c, "reels.0.saves"))
    elif (c.get("manual") or {}).get("avg_views"):
        add("median_views", "Average views (self-reported)", short(c["manual"]["avg_views"]), "manual")
    a = c.get("audience") or {}
    if a.get("age"):
        age, share = max(a["age"].items(), key=lambda kv: kv[1])
        add("age", "Largest audience age group", f"{age} ({round(share * 100)}%)", source_of(c, "audience"))
    if a.get("cities"):
        add("cities", "Top audience cities", ", ".join(x["name"] for x in a["cities"][:3]), source_of(c, "audience"))
    fp = fan_proof.summary(c["_id"], b["_id"])
    return facts, fp


def _facts_text(c: dict, b: dict, facts: list[dict], fp: dict | None) -> str:
    lines = [f"Creator: {c['name']} (@{c['handle']})."] + [f"{f['label']}: {f['value']}." for f in facts]
    if fp:
        lines.append(f"Fan Proof: {fp['label']} (from posts synced through the official API).")
    lines.append(f"Brand: {b['name']}. Category: {b.get('category') or 'unknown'}. About: {b.get('description') or 'not given'}.")
    return "\n".join(lines)


def _template(c: dict, b: dict, facts: list[dict], fp: dict | None, lang: str) -> PitchCopy:
    f = {x["key"]: x["value"] for x in facts}
    niche = f["niche"].lower()
    if lang == "hi":
        pitch = f"नमस्ते {b['name']} टीम, मैं {c['name']} हूँ और {f['languages']} में {niche} कंटेंट बनाता/बनाती हूँ।"
        if "median_views" in f:
            pitch += f" मेरी हाल की पोस्ट्स के मीडियन व्यूज़ {f['median_views']} हैं।"
        if fp:
            pitch += f" मैं पहले से आपका फ़ैन हूँ: {fp['label']}।"
        pitch += f" मुझे {b['name']} के साथ ऐसा कंटेंट बनाना अच्छा लगेगा जो मेरी ऑडियंस को सच में काम का लगे। क्या हम बात कर सकते हैं?"
        return PitchCopy(
            subject=f"{b['name']} के लिए {niche} कोलैब का आइडिया",
            pitch=pitch,
            content_ideas=[
                f"{b['name']} को रोज़मर्रा की ज़िंदगी में दिखाती एक रील",
                "पीछे की कहानी: मैं इसे कैसे इस्तेमाल करता/करती हूँ",
                "ऑडियंस के सवालों के जवाब वाली स्टोरी सीरीज़",
            ],
        )
    pitch = f"Hi {b['name']} team, I'm {c['name']}, and I make {niche} content in {f['languages']}."
    if "median_views" in f:
        pitch += f" My recent posts have a median of {f['median_views']} views."
    if "age" in f:
        pitch += f" My largest audience group is {f['age']}."
    if fp:
        pitch += f" I'm already a fan: {fp['label'].lower()}."
    pitch += f" I'd love to make something with {b['name']} that my audience finds genuinely useful. Could we talk?"
    return PitchCopy(
        subject=f"A {niche} collab idea for {b['name']}",
        pitch=pitch,
        content_ideas=[
            f"A reel showing {b['name']} in an everyday routine",
            "Behind the scenes: how I actually use it",
            "A story series answering my audience's questions",
        ],
    )


def _price(c: dict, b: dict) -> dict:
    """From the fair-price engine only. Unclaimed brands have no audience target, so the
    estimate assumes a typical good fit."""
    fp = fair_price(c, b if b.get("target") else None, {"deliverables": [{"kind": "reel", "count": 1}]}, with_model=False)
    return {"range": fp["range"], "deliverables": fp["deliverables"], "data_label": fp["data_label"], "data_source": fp["data_source"], "estimate": True}


def write(c: dict, b: dict, lang: str) -> dict:
    facts, fp = facts_for(c, b)
    text = _facts_text(c, b, facts, fp)
    language = "Hindi (Devanagari; keep brand and format names in English)" if lang == "hi" else "English"
    prompt = (
        f"{text}\n\nWrite a short pitch from this creator to this brand in {language}, in the first person. "
        f"Return a subject line, a pitch of at most {MAX_WORDS} words, and exactly 3 content ideas. "
        "Use only the facts above; quote no number that isn't in them; don't mention prices or rates; "
        "no promises about results, reach or sales."
    )
    def fallback() -> PitchCopy:
        return _template(c, b, facts, fp, lang)

    copy, how = generate("pitch", prompt, PitchCopy, fallback, facts=text, max_tokens=700)
    try:
        # Checked again here (word limit, three ideas) whatever the model client validated.
        copy = PitchCopy.model_validate(copy.model_dump())
    except ValidationError:
        copy, how = fallback(), "template"
    return {"copy": copy.model_dump(), "written_by": "ai" if how in ("ai", "cache") else "template", "facts": facts, "fan_proof": fp,
            "facts_text": text, "suggested_price_range": _price(c, b)}


# ------------------------------------------------------------------ creator side
def _brand(brand_id: str) -> dict:
    b = get_db().brands.find_one({"_id": brand_id, "removed": {"$ne": True}, "guest": {"$ne": True}})
    if not b or brand_id.startswith("xx_"):
        raise HTTPException(404, "Brand not found")
    return b


def view(p: dict, for_brand: bool = False) -> dict:
    d = {k: p.get(k) for k in ("subject", "pitch", "content_ideas", "lang", "status", "written_by", "suggested_price_range", "fan_proof", "facts",
                               "created_at", "sent_at", "answered_at", "deal_id", "brand_id", "brand_name", "brand_slug", "decline_note")}
    d["id"] = p["_id"]
    if not for_brand:
        d["share"] = {"slug": p["share_slug"], "revoked": bool(p.get("share_revoked"))} if p.get("share_slug") else None
        d["on_platform"] = p.get("on_platform")
    return d


def sent_this_week(creator_id: str) -> int:
    return get_db().pitches.count_documents({"creator_id": creator_id, "sent_ts": {"$gte": time.time() - WEEK_S}})


def create(c: dict, brand_id: str, lang: str, user: dict) -> dict:
    db = get_db()
    b = _brand(brand_id)
    if db.pitches.count_documents({"creator_id": c["_id"], "status": "draft"}) >= 20:
        raise HTTPException(409, "You have 20 draft pitches. Send or delete some first.")
    w = write(c, b, lang)
    pid = f"pt_{uuid.uuid4().hex[:10]}"
    doc = {
        "_id": pid,
        "creator_id": c["_id"],
        "brand_id": b["_id"],
        "brand_name": b["name"],
        "brand_slug": b.get("slug"),
        "on_platform": b.get("claimed", True),
        "lang": lang,
        **w["copy"],
        "written_by": w["written_by"],
        "facts": w["facts"],
        "facts_text": w["facts_text"],
        "fan_proof": w["fan_proof"],
        "suggested_price_range": w["suggested_price_range"],
        "status": "draft",
        "created_at": now_iso(),
    }
    db.pitches.insert_one(doc)
    au.audit("pitch_drafted", user["_id"], "creator", pitch_id=pid, brand_id=b["_id"])
    return view(doc)


def own(pitch_id: str, creator_id: str) -> dict:
    p = get_db().pitches.find_one({"_id": pitch_id})
    if not p or p["creator_id"] != creator_id:
        raise HTTPException(404, "Pitch not found")
    return p


_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def edit(p: dict, changes: dict) -> dict:
    if p["status"] != "draft":
        raise HTTPException(409, "This pitch was already sent.")
    merged = PitchCopy(**{k: changes.get(k, p[k]) for k in ("subject", "pitch", "content_ideas")})
    text = " ".join([merged.subject, merged.pitch, *merged.content_ideas])
    if breaks_copy_rules(text):
        raise HTTPException(422, "Pitches can't promise results. Describe your content and audience instead.")
    # Small counts are fine ("2 reels"); any other number must come from your data.
    unknown = [n for n in _NUM.findall(text) if not numbers_grounded(n, p["facts_text"]) and not (n.isdigit() and int(n) <= 10)]
    if unknown:
        raise HTTPException(422, f"These numbers aren't in your data: {', '.join(dict.fromkeys(unknown))}. Remove them, or connect the account they come from.")
    get_db().pitches.update_one({"_id": p["_id"]}, {"$set": {**merged.model_dump(), "edited": True}})
    return view(get_db().pitches.find_one({"_id": p["_id"]}))


def send(p: dict, user: dict) -> dict:
    """Sends a draft: to the brand's inbox, or as a share link if the brand isn't here."""
    db = get_db()
    if p["status"] != "draft":
        return {**view(p), "duplicate": True}
    if sent_this_week(p["creator_id"]) >= PER_WEEK:
        raise HTTPException(429, f"You've sent {PER_WEEK} pitches in the last 7 days. Pitches you send later this week will go through then.")
    b = _brand(p["brand_id"])
    on_platform = b.get("claimed", True)
    if on_platform and db.pitches.find_one({"creator_id": p["creator_id"], "brand_id": b["_id"], "status": {"$in": list(OPEN)}}):
        raise HTTPException(409, f"Your last pitch to {b['name']} is still waiting for an answer.")
    at = now_iso()
    update = {"sent_at": at, "sent_ts": time.time(), "on_platform": on_platform}
    if on_platform:
        update["status"] = "sent"
    else:
        update.update({"status": "shared", "share_slug": secrets.token_urlsafe(12), "share_revoked": False})
    res = db.pitches.update_one({"_id": p["_id"], "status": "draft"}, {"$set": update})
    if not res.modified_count:  # a repeated request got there first
        return {**view(db.pitches.find_one({"_id": p["_id"]})), "duplicate": True}
    au.audit("pitch_sent", user["_id"], "creator", pitch_id=p["_id"], brand_id=b["_id"], on_platform=on_platform)
    return {**view(db.pitches.find_one({"_id": p["_id"]})), "duplicate": False, "left_this_week": PER_WEEK - sent_this_week(p["creator_id"])}


def revoke(p: dict) -> dict:
    if not p.get("share_slug"):
        raise HTTPException(409, "This pitch has no share link.")
    get_db().pitches.update_one({"_id": p["_id"]}, {"$set": {"share_revoked": True}})
    return view(get_db().pitches.find_one({"_id": p["_id"]}))


def public(slug: str) -> dict:
    """The share link: the pitch and the creator's public basics, nothing private."""
    db = get_db()
    p = db.pitches.find_one({"share_slug": slug})
    if not p or p.get("share_revoked"):
        raise HTTPException(404, "This link isn't active")
    c = db.creators.find_one({"_id": p["creator_id"]}, {"name": 1, "handle": 1, "niche": 1, "languages": 1, "avatar_hue": 1, "public_page": 1})
    if not c:
        raise HTTPException(404, "This link isn't active")
    return {
        "subject": p["subject"],
        "pitch": p["pitch"],
        "content_ideas": p["content_ideas"],
        "lang": p["lang"],
        "brand_name": p["brand_name"],
        "sent_at": p["sent_at"],
        "fan_proof": p.get("fan_proof"),
        "suggested_price_range": p.get("suggested_price_range"),
        "creator": {
            "name": c["name"],
            "handle": c["handle"],
            "niche": NICHES[c["niche"]]["label"],
            "languages": [LANGS[x]["label"] for x in c.get("languages") or [] if x in LANGS],
            "avatar_hue": c.get("avatar_hue", 260),
            "page": f"/c/{c['handle']}" if c.get("public_page") is not False else None,
        },
    }


# ------------------------------------------------------------------ the Brand Fan Inbox
def _connected(creator_id: str) -> bool:
    db = get_db()
    return bool(db.connections.count_documents({"creator_id": creator_id, "platform": "instagram", "status": "connected"})
                or db.creators.count_documents({"_id": creator_id, "channels.youtube.analytics_connected": True}))


def inbox(brand: dict, connected_only: bool) -> dict:
    db = get_db()
    rows = []
    for p in db.pitches.find({"brand_id": brand["_id"], "status": {"$in": ["sent", "accepted", "declined"]}}):
        c = db.creators.find_one({"_id": p["creator_id"]})
        if not c:
            continue
        connected = _connected(c["_id"])
        if connected_only and not connected:
            continue
        fit = audience_fit(c, brand)["score"] if brand.get("target") else None
        fp = fan_proof.summary(c["_id"], brand["_id"])
        rows.append({
            **view(p, for_brand=True),
            "creator": {"id": c["_id"], "name": c["name"], "handle": c["handle"], "avatar_hue": c.get("avatar_hue", 260),
                        "is_reference": c.get("is_reference", False), "niche": NICHES[c["niche"]]["label"]},
            "fit": fit,
            "fan_proof": fp,
            "connected": connected,
        })
    rows.sort(key=lambda r: (r["status"] != "sent", -(r["fit"] or 0), -((r["fan_proof"] or {}).get("count") or 0)))
    return {"items": rows, "open": sum(1 for r in rows if r["status"] == "sent")}


def own_received(pitch_id: str, user: dict) -> tuple[dict, dict]:
    au.require_role(user, "brand")
    p = get_db().pitches.find_one({"_id": pitch_id})
    if not p or p["brand_id"] != user.get("brand_id") or p["status"] not in ("sent", "accepted", "declined"):
        raise HTTPException(404, "Pitch not found")
    return p, get_db().brands.find_one({"_id": p["brand_id"]})


def accept(p: dict, brand: dict, amount: int | None, user: dict) -> dict:
    """Accepting turns the pitch into an offer in the usual deal flow."""
    db = get_db()
    if p["status"] == "accepted":
        return {**view(p, for_brand=True), "duplicate": True}
    if p["status"] != "sent":
        raise HTTPException(409, f"This pitch was already {p['status']}.")
    c = db.creators.find_one({"_id": p["creator_id"]})
    if not c or cs.scopes_for(c, brand["_id"]) is None:
        raise HTTPException(409, "This creator isn't sharing with you right now.")
    rng = (p.get("suggested_price_range") or {}).get("range") or {}
    amt = amount or int(round(((rng.get("low") or 0) + (rng.get("high") or 0)) / 2)) or 5_000
    res = db.pitches.update_one({"_id": p["_id"], "status": "sent"}, {"$set": {"status": "accepting"}})
    if not res.modified_count:
        return {**view(db.pitches.find_one({"_id": p["_id"]}), for_brand=True), "duplicate": True}
    try:
        made = offers.create_offer(brand, c, None, amt, f"Re: your pitch, “{p['subject']}”", user["_id"])
    except Exception:
        db.pitches.update_one({"_id": p["_id"]}, {"$set": {"status": "sent"}})
        raise
    db.pitches.update_one({"_id": p["_id"]}, {"$set": {"status": "accepted", "deal_id": made["id"], "answered_at": now_iso()}})
    au.audit("pitch_accepted", user["_id"], "brand", pitch_id=p["_id"], deal_id=made["id"])
    return {**view(db.pitches.find_one({"_id": p["_id"]}), for_brand=True), "duplicate": False}


def decline(p: dict, brand: dict, note: str | None, user: dict) -> dict:
    db = get_db()
    if p["status"] == "declined":
        return {**view(p, for_brand=True), "duplicate": True}
    if p["status"] != "sent":
        raise HTTPException(409, f"This pitch was already {p['status']}.")
    db.pitches.update_one({"_id": p["_id"]}, {"$set": {"status": "declined", "answered_at": now_iso(), "decline_note": note}})
    db.notifications.insert_one({
        "_id": f"nt_{uuid.uuid4().hex[:10]}",
        "to": p["creator_id"],
        "kind": "pitch_declined",
        "brand_id": brand["_id"],
        "pitch_id": p["_id"],
        "text": f"Thanks for your pitch to {brand['name']}. They're not taking it forward right now. Your pitch helps them get to know you, and you can pitch them again later.",
        "at": now_iso(),
        "read": False,
    })
    au.audit("pitch_declined", user["_id"], "brand", pitch_id=p["_id"])
    return {**view(db.pitches.find_one({"_id": p["_id"]}), for_brand=True), "duplicate": False}
