"""Regional-language AI: tags captions and transcripts in Hindi, Tamil, Telugu,
Bengali, Marathi, Kannada, Malayalam, Gujarati, Hinglish and English with
language, niche, tone and brand safety. Works offline with rules; refines with
the language model when one is configured."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from ..seed.catalog import LANGS, NICHES
from .llm import generate

SCRIPTS = [
    ("ta", "Tamil", 0x0B80, 0x0BFF),
    ("te", "Telugu", 0x0C00, 0x0C7F),
    ("kn", "Kannada", 0x0C80, 0x0CFF),
    ("ml", "Malayalam", 0x0D00, 0x0D7F),
    ("bn", "Bengali", 0x0980, 0x09FF),
    ("gu", "Gujarati", 0x0A80, 0x0AFF),
    ("deva", "Devanagari", 0x0900, 0x097F),
]
MARATHI_MARKERS = ["आहे", "मध्ये", "घरगुती", "टांत", "नाही", "करावी", "पाहून", "चा ", "ची ", "चे ", "सकाळचा", "घरी"]
HINDI_MARKERS = ["है", "में", "का ", "की ", "के ", "मिनट", "कैसे", "घर", "आसान"]
HINGLISH = {
    "hai", "kya", "ye", "yeh", "dekh", "dekho", "mein", "ke", "ka", "ki", "bhai", "yaar", "samjho", "kaise",
    "banaye", "banao", "bachane", "tareeke", "laga", "aa", "gaye", "sabse", "hafta", "pehli", "mummy", "jab",
    "nahi", "kar", "karo", "wala", "wali", "ko", "se", "aur",
}

NICHE_WORDS: dict[str, list[str]] = {
    "food": ["recipe", "breakfast", "tiffin", "dosa", "idli", "sambar", "chutney", "rasam", "poha", "paratha", "dal",
             "masala", "cook", "kitchen", "டிபன்", "தோசை", "சாம்பார்", "சட்னி", "குழம்பு", "ரசம்", "உப்புமா", "பாயசம்",
             "சாதம்", "வடை", "ఉప్మా", "పప్పు", "పచ్చడి", "టిఫిన్", "అన్నం", "ఉಪ್ಪಿಟ್ಟು", "ದೋಸೆ", "ಬಾತ್", "ಚಟ್ನಿ",
             "ഉപ്പുമാവ്", "സാമ്പാർ", "പുട്ട്", "പായസം", "पोहा", "रेसिपी", "दाल", "राजमा", "पराठा", "चाय", "पोहे",
             "मिसळ", "লুচি", "ঝোল", "কারি", "রান্না", "পায়েস"],
    "anime_edits": ["anime", "edit", "amv", "manga", "fight scene", "character", "slow-mo", "beat sync", "एडिट", "सीन"],
    "gaming": ["clutch", "rank", "stream", "gameplay", "aim", "fps", "speedrun", "क्लच", "ક્લચ", "ખેલાડી", "खिलाड़ी"],
    "finance": ["sip", "tax", "itr", "budget", "salary", "credit", "fund", "invest", "टैक्स", "बजट", "फंड", "क्रेडिट",
                "সঞ্চয়", "বেতন", "வரி", "சேமிப்பு"],
    "tech": ["code", "coding", "app", "dsa", "developer", "website", "ai tools", "కోడింగ్", "कोडिंग", "वेबसाइट"],
    "fitness": ["yoga", "workout", "gym", "fat loss", "diet", "fitness", "योग", "वर्कआउट", "व्यायाम", "யோக", "நமஸ்காரம்", "உடற்பயிற்சி"],
    "fashion": ["kurta", "saree", "look", "outfit", "wardrobe", "style", "புடவை", "லுக்"],
    "beauty": ["skincare", "makeup", "sunscreen", "skin", "ত্বক", "মেকআপ"],
    "comedy": ["be like", "jab", "skit", "meme", "ஆட்டோ", "அனுபவம்"],
    "education": ["maths", "exam", "upsc", "current affairs", "गणित", "ट्रिक", "പരീക്ഷ", "വാർത്ത"],
    "travel": ["trip", "trail", "homestay", "travel", "सफर", "होमस्टे", "पहाड़"],
    "parenting": ["toddler", "lunchbox", "kids", "screen time", "குழந்தை", "லஞ்ச்"],
}
TONE_WORDS = {
    "educational": ["how", "kaise", "tareeke", "tips", "explained", "guide", "எப்படி", "ఎలా", "कैसे", "ट्रिक", "simple", "steps", "எளிய", "सही"],
    "humorous": ["be like", "jab", "meme", "funny", "அனுபவம்", "vs"],
    "emotional": ["emotional", "goosebumps", "tribute", "दोस्ती", "इमोशनल", "slow-mo", "அம்மா", "అమ్మ", "মায়ের", "അമ്മ"],
    "energetic": ["clutch", "fight", "rank push", "1v3", "beat sync"],
}
SAFETY_WORDS = {
    "gambling": ["betting", "satta", "casino", "fantasy app"],
    "strong_language": ["bc", "mc", "wtf"],
    "health_claims": ["cure", "lose 10 kg", "permanent results"],
    "fee_scam": ["registration fee", "pay to join"],
}


class CaptionTag(BaseModel):
    language: str = Field(description="One of: hi, en, hinglish, ta, te, kn, ml, bn, mr, gu")
    script: str
    niche: str = Field(description="One of the niche ids provided")
    tone: Literal["educational", "humorous", "emotional", "energetic", "warm"]
    brand_safety_flags: list[str]
    confidence: Literal["low", "medium", "high"]


class CaptionTags(BaseModel):
    tags: list[CaptionTag]


def _script_lang(text: str) -> tuple[str | None, str]:
    counts: dict[str, int] = {}
    for ch in text:
        cp = ord(ch)
        for code, _, lo, hi in SCRIPTS:
            if lo <= cp <= hi:
                counts[code] = counts.get(code, 0) + 1
    if not counts:
        return None, "Latin"
    code = max(counts, key=counts.get)
    if code == "deva":
        mr = sum(text.count(m) for m in MARATHI_MARKERS)
        hi = sum(text.count(m) for m in HINDI_MARKERS)
        return ("mr" if mr > hi else "hi"), "Devanagari"
    name = next(s[1] for s in SCRIPTS if s[0] == code)
    return code, name


def tag_rules(text: str) -> CaptionTag:
    lang, script = _script_lang(text)
    low = text.lower()
    if lang is None:
        words = re.findall(r"[a-z]+", low)
        hits = len(set(words) & HINGLISH)
        lang = "hinglish" if hits >= 2 or (hits >= 1 and len(words) <= 8) else "en"
    scores = {n: sum(1 for w in ws if w.lower() in low) for n, ws in NICHE_WORDS.items()}
    niche = max(scores, key=scores.get) if max(scores.values()) > 0 else "unknown"
    tones = {t: sum(1 for w in ws if w.lower() in low) for t, ws in TONE_WORDS.items()}
    tone = max(tones, key=tones.get) if max(tones.values()) > 0 else "warm"
    flags = [f for f, ws in SAFETY_WORDS.items() if any(re.search(rf"\b{re.escape(w)}\b", low) for w in ws)]
    hits = scores.get(niche, 0)
    return CaptionTag(
        language=lang,
        script=script,
        niche=niche,
        tone=tone,  # type: ignore[arg-type]
        brand_safety_flags=flags,
        confidence="high" if hits >= 2 else "medium" if hits == 1 else "low",
    )


def tag_captions(captions: list[str]) -> dict:
    captions = [c.strip() for c in captions if c and c.strip()][:8]
    if not captions:
        return {"tags": [], "source": "template", "summary": None}

    def fallback() -> CaptionTags:
        return CaptionTags(tags=[tag_rules(c) for c in captions])

    prompt = (
        "Tag each caption below. Return one tag per caption, in order.\n"
        f"Niche ids: {', '.join(NICHES)}.\n"
        "language: hi, en, hinglish (romanised Hindi mixed with English), ta, te, kn, ml, bn, mr or gu.\n"
        "brand_safety_flags: any of gambling, strong_language, health_claims, fee_scam, copyrighted_clips; empty if none.\n\n"
        + "\n".join(f"{i + 1}. {c}" for i, c in enumerate(captions))
    )
    result, source = generate("regional_tag", prompt, CaptionTags, fallback, max_tokens=800)
    if len(result.tags) != len(captions):
        result, source = fallback(), "template"
    tags = []
    for cap, t in zip(captions, result.tags):
        d = t.model_dump()
        d["caption"] = cap
        d["language_label"] = LANGS.get(d["language"], {}).get("label", d["language"])
        d["niche_label"] = NICHES.get(d["niche"], {}).get("label", "Unclear")
        tags.append(d)
    langs = [t["language"] for t in tags]
    niches = [t["niche"] for t in tags if t["niche"] in NICHES]
    summary = {
        "language": max(set(langs), key=langs.count),
        "niche": max(set(niches), key=niches.count) if niches else None,
        "flags": sorted({f for t in tags for f in t["brand_safety_flags"]}),
    }
    summary["language_label"] = LANGS.get(summary["language"], {}).get("label", summary["language"])
    summary["niche_label"] = NICHES.get(summary["niche"] or "", {}).get("label")
    return {"tags": tags, "source": source, "summary": summary}
