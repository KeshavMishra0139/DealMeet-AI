"""The media kit: a live view built from current data (English or Hindi), and saved
versions that never change.

The live view is rebuilt on every request, so it always shows today's numbers, each
with its data source. A saved version freezes the content the creator chose (edited
headline and bio, which sections show) together with its own PDF. The public page
shows the version the creator picks, or the live view; either way it only shows what
their sharing settings allow at that moment.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from ..ai.llm import breaks_copy_rules, generate
from ..config import now_iso, today
from ..db import get_db
from ..engines import brand_safety, metrics
from ..engines.common import inr_range, safe_median, short
from ..engines.fair_price import fair_price
from ..engines.hindi import LANGS as LANGS_HI
from ..engines.trust import trust_score
from ..seed.catalog import LANGS, NICHES
from . import pdf, rates
from .creator_ctx import best_fit_brand
from .views import source_of

Lang = Literal["en", "hi"]
SECTIONS = ("stats", "formats", "audience", "rates", "trust")
MAX_VERSIONS = 20

NICHES_HI = {
    "anime_edits": "एनिमे एडिट्स", "gaming": "गेमिंग", "food": "खाना और कुकिंग", "finance": "पर्सनल फ़ाइनेंस",
    "tech": "टेक और कोडिंग", "fitness": "फ़िटनेस और योग", "fashion": "फ़ैशन", "beauty": "ब्यूटी और स्किनकेयर",
    "comedy": "कॉमेडी", "education": "एजुकेशन", "travel": "ट्रैवल", "parenting": "पेरेंटिंग",
}
MONTHS_HI = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]

TEXT = {
    "en": {
        "followers": "Followers",
        "median": "Median views, last 6",
        "reach": "Reach vs followers",
        "ss": "Saves + shares / view",
        "yt_subs": "YouTube subscribers",
        "yt_median": "Median views, recent videos",
        "reel": "1 reel",
        "reel_stories": "1 reel + 2 stories",
        "bundle": "2-reel bundle",
        "audience": "Mostly {age} ({age_pct}%), {women}% women, top cities {cities}.",
        "safe": "Brand safety: no concerns found.",
        "unsafe": "Brand safety: {label}; {fix}",
    },
    "hi": {
        "followers": "फ़ॉलोअर्स",
        "median": "पिछली 6 रील्स के मीडियन व्यूज़",
        "reach": "फ़ॉलोअर्स के मुकाबले पहुँच",
        "ss": "सेव + शेयर / व्यू",
        "yt_subs": "YouTube सब्सक्राइबर्स",
        "yt_median": "हाल के वीडियो के मीडियन व्यूज़",
        "reel": "1 रील",
        "reel_stories": "1 रील + 2 स्टोरी",
        "bundle": "2 रील्स का बंडल",
        "audience": "ज़्यादातर {age} ({age_pct}%), {women}% महिलाएँ, टॉप शहर {cities}।",
        "safe": "ब्रैंड सेफ़्टी: कोई चिंता नहीं मिली।",
        "unsafe": "ब्रैंड सेफ़्टी: ध्यान दें, {label}।",
    },
}


class KitCopy(BaseModel):
    headline: str = Field(max_length=120)
    bio: str = Field(max_length=420)


def public_scopes(c: dict) -> dict:
    p = c.get("public_scopes")
    if p is None:
        d = c.get("consent_defaults") or {}
        p = {"stats": d.get("stats", True), "demographics": d.get("demographics", False), "rates": True}
    return {"collabs": True, **p}


def _date(lang: Lang) -> str:
    d = today()
    return f"{d.day} {MONTHS_HI[d.month - 1]} {d.year}" if lang == "hi" else d.strftime("%d %b %Y")


def _niche(c: dict, lang: Lang) -> str:
    return NICHES_HI[c["niche"]] if lang == "hi" else NICHES[c["niche"]]["label"]


def _langs(c: dict, lang: Lang) -> list[str]:
    codes = [x for x in c.get("languages") or [] if x in LANGS]
    return [LANGS_HI.get(x, LANGS[x]["label"]) for x in codes] if lang == "hi" else [LANGS[x]["label"] for x in codes]


def _copy(c: dict, pub: dict, lang: Lang) -> tuple[KitCopy, str]:
    """Headline and bio. They quote reach numbers only when the creator shows stats publicly."""
    niche_en = NICHES[c["niche"]]["label"]
    langs_en = " and ".join(LANGS[x]["label"] for x in c.get("languages") or [] if x in LANGS)
    has = pub["stats"] and metrics.has_reels(c)
    ratio = metrics.reach_ratio(c) if has else 0
    # Only cite the best format when its label is real data, not simulated.
    best = metrics.by_topic(c)[0]["topic"] if has and metrics.by_topic(c) and metrics.prov(c, "reels.0.topic") != "simulated" else None
    facts = (
        f"Niche: {niche_en}. Languages: {langs_en}. "
        + (f"Followers: {short(c.get('followers', 0))}. " if pub["stats"] else "")
        + (f"Median views of last 6 reels: {short(metrics.median_views(c))}. Reach ratio: about {ratio:.0f}x followers. Best format: {best}. " if has else "")
        + (f"City: {c.get('city')}." if c.get("city") else f"Region: {c.get('region')}.")
    )

    if lang == "hi":
        niche, langs = _niche(c, "hi"), " और ".join(_langs(c, "hi"))

        def fallback() -> KitCopy:
            head = f"{langs} में {niche}"
            if has and ratio >= 2:
                head += f", फ़ॉलोअर्स से करीब {ratio:.0f} गुना पहुँच"
            bio = f"{langs} में {niche} रील्स।"
            if has:
                bio += f" हाल की रील्स के मीडियन व्यूज़ {short(metrics.median_views(c))} हैं।"
            if best:
                bio += f" दर्शकों को सबसे ज़्यादा {best} पसंद आता है।"
            bio += " ब्रैंड रील्स, कलेक्टिव्स और लंबी पार्टनरशिप के लिए DealMeet एस्क्रो के ज़रिए उपलब्ध।"
            return KitCopy(headline=head, bio=bio)

        prompt = (
            f"{facts}\nWrite a media-kit headline (under 12 words) and a 2-sentence bio in Hindi (Devanagari script; "
            "keep product and format names in English), in the third person, describing the content and audience for brands. "
            "Do not quote the creator or invent opinions, numbers or past brand names."
        )
        return generate("media_kit_copy_hi", prompt, KitCopy, fallback, facts=facts, max_tokens=500)

    noun = niche_en if niche_en.lower().endswith("edits") else f"{niche_en} reels"

    def fallback_en() -> KitCopy:
        head = f"{niche_en} in {langs_en}"
        if has and ratio >= 2:
            head += f", reaching about {ratio:.0f}x the follower count"
        bio = f"{noun} in {langs_en}."
        if has:
            bio += f" Recent reels have a median of {short(metrics.median_views(c))} views."
        if best:
            bio += f" {best} is the format audiences respond to most."
        bio += " Available for brand reels, collectives and long-term partnerships through DealMeet escrow."
        return KitCopy(headline=head, bio=bio)

    prompt = (
        f"{facts}\nWrite a media-kit headline (under 12 words) and a 2-sentence bio in the third person, "
        "describing the content and audience for brands. Do not quote the creator or invent opinions, numbers or past brand names."
    )
    return generate("media_kit_copy", prompt, KitCopy, fallback_en, facts=facts, max_tokens=400)


def _youtube_stats(c: dict, tx: dict) -> list[dict]:
    yt = (c.get("channels") or {}).get("youtube")
    if not yt:
        return []
    out = []
    if not yt.get("subscribers_hidden"):
        out.append({"label": tx["yt_subs"], "value": short(yt.get("subscribers") or 0), "simulated": False, "source": "youtube_api"})
    views = [p["views"] for p in get_db().posts.find({"creator_id": c["_id"], "platform": "youtube"}, {"views": 1}).sort("published_at", -1).limit(6)]
    if len(views) >= 3:
        out.append({"label": tx["yt_median"], "value": short(safe_median(views)), "simulated": False, "source": "youtube_api"})
    return out


def build_kit(c: dict, lang: Lang = "en") -> dict:
    """The live media kit, as the public sees it under the creator's sharing settings."""
    tx = TEXT[lang]
    pub = public_scopes(c)
    copy, copy_source = _copy(c, pub, lang)
    stats = None
    if pub["stats"]:
        rows = []
        if metrics.has_reels(c):
            views_src, saves_src = source_of(c, "reels.0.views"), source_of(c, "reels.0.saves")
            rows = [
                {"label": tx["followers"], "value": short(c.get("followers", 0)), "source": source_of(c, "followers")},
                {"label": tx["median"], "value": short(metrics.median_views(c)), "source": views_src},
                {"label": tx["reach"], "value": f"{metrics.reach_ratio(c):.1f}x", "source": views_src},
                {"label": tx["ss"], "value": f"{metrics.ss_rate(c) * 100:.1f}%", "source": saves_src},
            ]
        rows += _youtube_stats(c, tx)
        stats = [{**r, "simulated": r["source"] == "synthetic"} for r in rows] or None
    formats = None
    if pub["stats"] and metrics.has_reels(c):
        src = source_of(c, "reels.0.topic")
        formats = [{"topic": t["topic"], "views": short(t["median_views"]), "simulated": src == "synthetic", "source": src} for t in metrics.by_topic(c) if t["count"] >= 2][:3] or None
    audience = None
    if pub["demographics"] and c.get("audience"):
        a = c["audience"]
        top_age = max(a["age"].items(), key=lambda kv: kv[1])
        cities = ", ".join(x["name"] for x in a.get("cities", [])[:3])
        src = source_of(c, "audience")
        audience = {
            "line": tx["audience"].format(age=top_age[0], age_pct=round(top_age[1] * 100), women=round(a["gender"].get("female", 0) * 100), cities=cities),
            "simulated": src == "synthetic",
            "source": src,
        }
    rate_rows, rates_kind, from_rate = None, None, None
    if pub["rates"]:
        saved = rates.kit_rates(c, lang)
        if saved:
            rate_rows, rates_kind = [{k: r[k] for k in ("label", "value", "kind")} for r in saved], "your_rate"
            from_rate = min(r["amount"] for r in saved)
        else:
            brand = best_fit_brand(c)
            packages = [
                ("reel", None),
                ("reel_stories", {"deliverables": [{"kind": "reel", "count": 1}, {"kind": "story", "count": 2}]}),
                ("bundle", {"deliverables": [{"kind": "reel", "count": 2}]}),
            ]
            rate_rows = []
            for key, terms in packages:
                fp = fair_price(c, brand, terms, with_model=False)
                if from_rate is None:
                    from_rate = fp["range"]["low"]
                rate_rows.append({"label": tx[key], "value": inr_range(fp["range"]["low"], fp["range"]["high"]), "kind": "estimate"})
            rates_kind = "estimate"
    safety = brand_safety.assess(c)
    t = trust_score(c)
    has_sim = any(x.get("simulated") for x in (stats or []) + (formats or [])) or bool(audience and audience["simulated"])
    flag = safety["flags"][0] if safety["flags"] else None
    return {
        "creator_id": c["_id"],
        "lang": lang,
        "name": c["name"],
        "handle": c["handle"],
        "avatar_hue": c.get("avatar_hue", 260),
        "is_reference": c.get("is_reference", False),
        "reference_note": c.get("reference_note") if c.get("is_reference") else None,
        "niche": _niche(c, lang),
        "languages": _langs(c, lang),
        "location": c.get("city") or c.get("region"),
        "copy": copy.model_dump(),
        "copy_source": copy_source,
        "stats": stats,
        "formats": formats,
        "audience": audience,
        "rates": rate_rows,
        "rates_kind": rates_kind,
        "from_rate": from_rate,
        "trust": {"score": t["score"], "level": t["level"], "reasons": t["reasons"], "simulated": t.get("simulated", []),
                  "source": source_of(c, "follower_history")} if t else None,
        "safety_note": (tx["unsafe"].format(label=flag["label"].lower(), fix=flag["fix"].lower()) if flag else tx["safe"]),
        "public": pub,
        "sections": {s: True for s in SECTIONS},
        "link": f"dealmeet.ai/c/{c['handle']}",
        "path": f"/c/{c['handle']}",
        "generated_on": _date(lang),
        "has_simulated": has_sim,
        "version": None,
    }


def apply_sections(kit: dict, sections: dict) -> dict:
    """Hide the sections that are switched off. Trust covers the badge and brand-safety note."""
    k = dict(kit)
    for s in ("stats", "formats", "audience", "rates"):
        if not sections.get(s, True):
            k[s] = None
    if not sections.get("rates", True):
        k["from_rate"], k["rates_kind"] = None, None
    if not sections.get("trust", True):
        k["trust"], k["safety_note"] = None, None
    k["sections"] = {s: bool(sections.get(s, True)) for s in SECTIONS}
    k["has_simulated"] = any(x.get("simulated") for x in (k["stats"] or []) + (k["formats"] or [])) or bool(k["audience"] and k["audience"]["simulated"])
    return k


def respect_scopes(kit: dict, pub: dict) -> dict:
    """What the sharing settings allow right now, applied over any kit (live or saved)."""
    allowed = dict(kit.get("sections") or {s: True for s in SECTIONS})
    if not pub.get("stats"):
        allowed["stats"] = allowed["formats"] = False
    if not pub.get("demographics"):
        allowed["audience"] = False
    if not pub.get("rates"):
        allowed["rates"] = False
    return apply_sections(kit, allowed)


# ------------------------------------------------------------------ PDF
def render_pdf(kit: dict, host: str | None = None) -> bytes:
    if kit.get("lang") == "hi" and not pdf.can_shape():
        raise HTTPException(503, "Hindi PDFs need text shaping (the uharfbuzz package), which isn't installed on this server. The English PDF works.")
    k = dict(kit)
    if host:
        k["link"] = host + k["path"]  # the address this app is served from
    return pdf.media_kit_pdf(k)


# ------------------------------------------------------------------ saved versions
class VersionIn(BaseModel):
    headline: str = Field(min_length=3, max_length=120)
    bio: str = Field(default="", max_length=420)
    sections: dict[Literal["stats", "formats", "audience", "rates", "trust"], bool] = {s: True for s in SECTIONS}
    lang: Lang = "en"


def _summary(v: dict, published: str | None) -> dict:
    return {
        "id": v["_id"],
        "number": v["number"],
        "lang": v["lang"],
        "headline": v["content"]["copy"]["headline"],
        "sections": v["content"]["sections"],
        "created_at": v["created_at"],
        "pdf_bytes": v["pdf_size"],
        "pdf_sha256": v["pdf_sha256"],
        "published": v["_id"] == published,
    }


def list_versions(c: dict) -> list[dict]:
    rows = get_db().kit_versions.find({"creator_id": c["_id"]}, {"pdf": 0}).sort("number", -1)
    return [_summary(v, c.get("kit_public_version")) for v in rows]


def create_version(c: dict, body: VersionIn, host: str | None = None) -> tuple[dict, bool]:
    """Save the current kit with the creator's edits as a new, unchangeable version.
    Returns (summary, created). Saving identical content again returns the existing one."""
    headline, bio = body.headline.strip(), body.bio.strip()
    for text in (headline, bio):
        if breaks_copy_rules(text):
            raise HTTPException(422, "Kit text can't promise results to brands. Describe your content and audience instead.")
    db = get_db()
    live = build_kit(c, body.lang)
    content = apply_sections({**live, "copy": {"headline": headline, "bio": bio}, "copy_source": "creator"}, body.sections)
    stable = {k: v for k, v in content.items() if k not in ("generated_on", "version", "public")}
    digest = hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    same = db.kit_versions.find_one({"creator_id": c["_id"], "content_sha256": digest})
    if same:
        return _summary(same, c.get("kit_public_version")), False
    if db.kit_versions.count_documents({"creator_id": c["_id"]}) >= MAX_VERSIONS:
        raise HTTPException(409, f"You have {MAX_VERSIONS} saved versions. Delete one to save another.")
    content.pop("public", None)
    for attempt in range(3):
        last = db.kit_versions.find_one({"creator_id": c["_id"]}, {"number": 1}, sort=[("number", -1)])
        number = (last["number"] if last else 0) + 1
        at = now_iso()
        content["version"] = {"number": number, "saved_on": content["generated_on"]}
        data = render_pdf(content, host)
        doc = {
            "_id": f"kv_{uuid.uuid4().hex[:10]}",
            "creator_id": c["_id"],
            "number": number,
            "lang": body.lang,
            "content": content,
            "content_sha256": digest,
            "pdf": data,
            "pdf_sha256": hashlib.sha256(data).hexdigest(),
            "pdf_size": len(data),
            "created_at": at,
        }
        try:
            db.kit_versions.insert_one(doc)
            return _summary(doc, c.get("kit_public_version")), True
        except DuplicateKeyError:
            same = db.kit_versions.find_one({"creator_id": c["_id"], "content_sha256": digest})
            if same:  # a repeated request saved it first
                return _summary(same, c.get("kit_public_version")), False
    raise HTTPException(409, "Another save happened at the same time. Try again.")


def get_version(c: dict, version_id: str) -> dict:
    v = get_db().kit_versions.find_one({"_id": version_id, "creator_id": c["_id"]})
    if not v:
        raise HTTPException(404, "Version not found")
    return v


def delete_version(c: dict, version_id: str) -> None:
    get_version(c, version_id)
    if c.get("kit_public_version") == version_id:
        raise HTTPException(409, "Your public page shows this version. Pick another version or the live view first.")
    get_db().kit_versions.delete_one({"_id": version_id, "creator_id": c["_id"]})


def set_public_version(c: dict, version_id: str | None) -> None:
    if version_id is not None:
        get_version(c, version_id)
    get_db().creators.update_one({"_id": c["_id"]}, {"$set": {"kit_public_version": version_id}})


def public_kit(c: dict, lang: Lang | None = None) -> dict:
    """The public page: the chosen version (in its own language) or the live view,
    with today's sharing settings applied."""
    pub = public_scopes(c)
    vid = c.get("kit_public_version")
    v = get_db().kit_versions.find_one({"_id": vid, "creator_id": c["_id"]}) if vid else None
    kit = dict(v["content"]) if v else build_kit(c, lang or "en")
    kit = respect_scopes(kit, pub)
    kit.pop("public", None)
    return kit
