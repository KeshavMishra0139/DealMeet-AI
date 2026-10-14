"""Setting a brand up from its name (and website) instead of a long form.

The language model suggests what the brand onboarding form asks (category, a one-line
description, the creator niches that fit, the audience's ages and gender, languages,
a monthly budget band and a goal) from the brand's name and website, using what it
already knows; the server never fetches the website. Every answer is checked against the
app's own lists, and the brand confirms or changes it before anything is saved. Without
AI, simple keyword rules and safe defaults fill what they can.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from ..seed.catalog import AGE_BUCKETS, LANGS, NICHES
from .llm import generate
from .regional import NICHE_WORDS

BUDGETS = [25_000, 50_000, 100_000, 150_000, 250_000, 500_000, 1_000_000]  # the form's slider steps
GOALS = ["Awareness", "Sales", "App installs", "Trial", "Sign-ups", "Festive sales"]
FREE_MAIL = {"gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "outlook.com", "hotmail.com", "live.com", "icloud.com",
             "me.com", "rediffmail.com", "proton.me", "protonmail.com", "aol.com", "zoho.com", "ymail.com", "msn.com"}


class BrandDraft(BaseModel):
    category: str = Field(description="What the brand sells, 2 to 5 words, for example 'Snacks and namkeen' or 'Budget earbuds'")
    description: str = Field(description="One plain sentence about the brand, at most 30 words. No claims you aren't sure of.")
    niches: list[str] = Field(description="1 to 3 creator niche ids from the list that fit the brand's products")
    ages: list[str] = Field(description="The audience age groups it sells to, from the list")
    gender: Literal["any", "female", "male"]
    languages: list[str] = Field(description="1 to 3 language ids its customers speak, from the list")
    budget_monthly: int = Field(description="A sensible starting monthly creator budget in rupees for a brand like this")
    goal: str = Field(description="One of the goals listed")
    known: bool = Field(description="True only if you recognise this specific brand; false if you are guessing from the name")


def hints(user: dict) -> dict:
    """What the account already tells us: the name, and a website from a company email."""
    email = (user.get("email") or "").lower()
    domain = email.split("@", 1)[1] if "@" in email else ""
    company = domain if domain and domain not in FREE_MAIL else None
    # A company email names the brand better than the account's name, which is often the person's.
    name = company.split(".")[0].replace("-", " ").title() if company else (user.get("name") or "")
    if "@" in name:
        name = ""
    return {"name": name[:60], "website": f"https://{company}" if company else None}


# Words in brand names and websites (creator-content words come from regional.NICHE_WORDS).
BRAND_WORDS = {
    "food": ["food", "foods", "snack", "masala", "spice", "kitchen", "tea", "chai", "coffee", "bakery", "dairy", "organic"],
    "beauty": ["beauty", "skin", "skincare", "cosmetic", "makeup", "salon", "hair", "glow"],
    "fashion": ["fashion", "wear", "apparel", "cloth", "saree", "kurta", "ethnic", "shoes", "footwear", "jewel"],
    "fitness": ["fit", "fitness", "gym", "protein", "nutrition", "sport", "yoga", "wellness", "health"],
    "tech": ["tech", "electronics", "audio", "mobile", "laptop", "gadget", "software", "app", "ai", "labs"],
    "gaming": ["game", "games", "gaming", "esports", "play"],
    "finance": ["finance", "fin", "bank", "pay", "invest", "loan", "insurance", "money", "capital", "wealth"],
    "education": ["edu", "learn", "academy", "school", "coaching", "classes", "tutor", "course"],
    "travel": ["travel", "trip", "trips", "hotel", "tour", "tours", "holiday", "stay", "stays"],
    "parenting": ["kids", "baby", "toy", "toys", "parent", "mom"],
}


def _snap(budget: int) -> int:
    return min(BUDGETS, key=lambda b: abs(b - budget))


def _rules(name: str, website: str | None) -> BrandDraft:
    text = f"{name} {website or ''}".lower()
    words = set(re.findall(r"[a-z]+", text))
    words |= {w[:-2] for w in words if w.endswith("es")} | {w[:-1] for w in words if w.endswith("s")}  # "snacks" -> "snack"
    # Short keywords ("ai", "pay") must be whole words; longer ones also count inside joined-up
    # names and domains ("thalamfoods").
    def hit(w: str) -> bool:
        return w in words or (len(w) >= 4 and any(w in t for t in words))

    scores = {n: sum(1 for w in BRAND_WORDS.get(n, []) if hit(w)) * 2 + sum(1 for w in ws if w.lower() in text)
              for n, ws in NICHE_WORDS.items()}
    best = [n for n, s in sorted(scores.items(), key=lambda x: -x[1]) if s > 0][:2]
    return BrandDraft(category="", description="", niches=best, ages=["18-24", "25-34"], gender="any",
                      languages=["hi", "en"], budget_monthly=100_000, goal="Awareness", known=False)


def suggest(name: str, website: str | None) -> dict:
    """A checked draft for the brand form, and whether the AI wrote it."""
    name = re.sub(r"\s+", " ", name).strip()[:60]
    prompt = (
        f"A brand is signing up to DealMeet to find Indian creators.\nBrand name: {name}\nWebsite: {website or 'not given'}\n\n"
        f"Creator niche ids: {', '.join(f'{k} ({v['label']})' for k, v in NICHES.items())}.\n"
        f"Age groups: {', '.join(AGE_BUCKETS)}.\nLanguage ids: {', '.join(f'{k} ({v['label']})' for k, v in LANGS.items())}.\n"
        f"Goals: {', '.join(GOALS)}.\n\n"
        "Suggest how this brand should fill in its profile. Use only ids from the lists. If you don't recognise the brand, "
        "infer from the name and say known=false. Keep the description factual and short."
    )
    out, source = generate("brand_setup", prompt, BrandDraft, lambda: _rules(name, website), max_tokens=500)
    niches = [n for n in out.niches if n in NICHES][:3]
    ages = [a for a in out.ages if a in AGE_BUCKETS] or ["18-24", "25-34"]
    langs = [x for x in out.languages if x in LANGS][:3] or ["hi", "en"]
    by_ai = source in ("ai", "cache")
    return {
        "name": name,
        "website": website,
        "category": out.category.strip()[:60],
        "description": out.description.strip()[:300],
        "niches": niches,
        "ages": ages,
        "gender": out.gender,
        "languages": langs,
        "budget_monthly": _snap(int(out.budget_monthly or 100_000)),
        "goal": out.goal if out.goal in GOALS else "Awareness",
        "by_ai": by_ai,
        "known": bool(out.known) if by_ai else False,
    }
