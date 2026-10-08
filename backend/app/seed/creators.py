"""Seeded creators. All except Creator A are fictional demo profiles."""
from __future__ import annotations

import random
from datetime import date, timedelta

from .catalog import CAPTIONS, CITIES, LANG_CITIES, NICHES, TOPICS

FICTIONAL = "Fictional demo profile."

# id, name, handle, niche, languages, city, followers, following, extras
# extras: low_trust kind, expertise, reach (median views / followers), flags
ROSTER: list[tuple] = [
    # Food: Tamil
    ("cr_f01", "Priya Natarajan", "priyas.tiffin.box", "food", ["ta"], "Chennai", 14_200, 410, {}),
    ("cr_f02", "Arun Kumar S", "arun.samaikiraan", "food", ["ta"], "Coimbatore", 6_800, 520, {}),
    ("cr_f03", "Revathi Senthil", "revathi.veetu.samayal", "food", ["ta"], "Tiruchirappalli", 3_100, 280, {}),
    ("cr_f04", "Karthik Sundaram", "madras.meals.ks", "food", ["ta", "en"], "Chennai", 48_500, 620, {}),
    ("cr_f05", "Divya Shankar", "divyas.kitchen.diaries", "food", ["ta"], "Madurai", 9_400, 300, {}),
    ("cr_f06", "Selvi Ganesan", "selvi.paati.recipes", "food", ["ta"], "Salem", 22_000, 150, {}),
    ("cr_f07", "Nithya R", "nithya.millet.meals", "food", ["ta"], "Coimbatore", 4_300, 390, {}),
    ("cr_f08", "Gowtham V", "gowtham.street.eats", "food", ["ta"], "Chennai", 31_000, 880, {"low_trust": "spike"}),
    ("cr_f09", "Anitha Joseph", "anitha.chettinad", "food", ["ta"], "Madurai", 1_600, 240, {}),
    ("cr_f10", "Bala Murugan", "bala.biryani.house", "food", ["ta"], "Tiruchirappalli", 11_800, 460, {}),
    # Food: Telugu
    ("cr_f11", "Sravani Reddy", "sravani.vantillu", "food", ["te"], "Hyderabad", 18_600, 530, {}),
    ("cr_f12", "Ravi Kondapalli", "ravi.ruchulu", "food", ["te"], "Vijayawada", 7_200, 610, {}),
    ("cr_f13", "Lavanya P", "lavanya.pachadi", "food", ["te"], "Visakhapatnam", 3_900, 350, {}),
    ("cr_f14", "Mahesh N", "mahesh.tiffins", "food", ["te"], "Hyderabad", 26_400, 1_900, {"low_trust": "pod"}),
    ("cr_f15", "Swathi Rao", "swathi.amma.vanta", "food", ["te"], "Hyderabad", 5_100, 260, {}),
    ("cr_f16", "Kiran Varma", "kiran.andhra.spice", "food", ["te"], "Vijayawada", 12_300, 700, {}),
    # Food: Kannada
    ("cr_f17", "Deepa Hegde", "deepa.oota", "food", ["kn"], "Bengaluru", 8_700, 330, {}),
    ("cr_f18", "Manjunath G", "manju.mysuru.bites", "food", ["kn"], "Mysuru", 4_800, 410, {}),
    ("cr_f19", "Shwetha K", "shwetha.ragi.kitchen", "food", ["kn"], "Bengaluru", 15_900, 380, {}),
    # Food: Malayalam
    ("cr_f20", "Anju Thomas", "anju.naadan.ruchi", "food", ["ml"], "Kochi", 10_400, 450, {}),
    ("cr_f21", "Fathima N", "fathima.malabar.kitchen", "food", ["ml"], "Kozhikode", 6_300, 290, {}),
    ("cr_f22", "Vishnu Prasad", "vishnu.sadya.stories", "food", ["ml"], "Thiruvananthapuram", 3_400, 220, {}),
    # Food: Hindi, Bengali
    ("cr_f23", "Neha Agarwal", "neha.ghar.ka.khana", "food", ["hi"], "Lucknow", 38_000, 510, {}),
    ("cr_f24", "Rohan Bhatia", "rohan.dhaba.style", "food", ["hi"], "Delhi", 7_700, 640, {}),
    ("cr_f25", "Moumita Das", "moumita.ranna.ghar", "food", ["bn"], "Kolkata", 9_900, 370, {}),
    # Anime and gaming
    ("cr_g01", "Aditya Singh", "aditya.otaku.edits", "anime_edits", ["hinglish"], "Delhi", 34_500, 210, {"copyright": True}),
    ("cr_g02", "Sneha Kulkarni", "sneha.amv.edits", "anime_edits", ["mr", "en"], "Pune", 12_700, 340, {"copyright": True}),
    ("cr_g03", "Harsh Tripathi", "harsh.clutch.plays", "gaming", ["hinglish"], "Patna", 56_000, 420, {}),
    ("cr_g04", "Ishaan Mehta", "ishaan.frame.by.frame", "anime_edits", ["en"], "Mumbai", 8_900, 260, {"copyright": True}),
    ("cr_g05", "Rehan Ali", "rehan.respawn", "gaming", ["hi"], "Lucknow", 142_000, 380, {}),
    ("cr_g06", "Tanvi Joshi", "tanvi.cosplay.craft", "anime_edits", ["en", "hi"], "Mumbai", 19_800, 640, {}),
    ("cr_g07", "Arjun Nair", "arjun.speedrun", "gaming", ["en"], "Kochi", 4_200, 190, {}),
    ("cr_g08", "Kabir Malhotra", "kabir.anime.recaps", "anime_edits", ["hinglish"], "Delhi", 27_600, 300, {"copyright": True, "twin_of": "cr_g01"}),
    ("cr_g09", "Yash Patel", "yash.gg.clips", "gaming", ["gu", "hi"], "Ahmedabad", 41_000, 7_600, {"low_trust": "f4f"}),
    ("cr_g10", "Pooja Verma", "pooja.manga.panels", "anime_edits", ["hi"], "Jaipur", 6_400, 280, {"copyright": True}),
    ("cr_g11", "Sahil Qureshi", "sahil.lofi.edits", "anime_edits", ["hinglish"], "Indore", 15_300, 330, {"copyright": True}),
    # Finance
    ("cr_n01", "Meera Iyer", "meera.taxes.simply", "finance", ["en", "ta"], "Chennai", 240, 180, {"expertise": "Chartered Accountant"}),
    ("cr_n02", "Vikram Choudhary", "vikram.paisa.talks", "finance", ["hinglish"], "Jaipur", 64_000, 410, {}),
    ("cr_n03", "Ritu Saxena", "ritu.money.basics", "finance", ["hi"], "Bhopal", 9_200, 350, {}),
    ("cr_n04", "Sourav Ghosh", "sourav.taka.talks", "finance", ["bn"], "Kolkata", 3_600, 270, {}),
    # Tech
    ("cr_t01", "Aman Tiwari", "aman.codes.daily", "tech", ["hinglish"], "Noida", 780, 300, {"expertise": "Full-stack developer"}),
    ("cr_t02", "Sai Prasanna", "prasanna.builds", "tech", ["te", "en"], "Hyderabad", 23_400, 520, {}),
    ("cr_t03", "Nikhil Deshmukh", "nikhil.dev.marathi", "tech", ["mr"], "Pune", 5_600, 240, {}),
    ("cr_t04", "Zara Sheikh", "zara.ai.explains", "tech", ["en"], "Bengaluru", 112_000, 600, {}),
    # Fitness and yoga
    ("cr_y01", "Kavita Rawat", "kavita.yogshala", "fitness", ["hi"], "Chandigarh", 610, 140, {"expertise": "Certified yoga teacher"}),
    ("cr_y02", "Prakash Subramanian", "prakash.fit.after.40", "fitness", ["ta", "en"], "Chennai", 17_300, 300, {}),
    ("cr_y03", "Simran Kaur", "simran.lifts", "fitness", ["hinglish"], "Chandigarh", 46_000, 950, {"low_trust": "spike"}),
    ("cr_y04", "Rahul Pawar", "rahul.desi.fitness", "fitness", ["mr", "hi"], "Nagpur", 7_900, 420, {}),
    # Fashion and beauty
    ("cr_s01", "Ananya Iyer", "ananya.saree.stories", "fashion", ["ta", "en"], "Chennai", 29_000, 480, {}),
    ("cr_s02", "Mehak Arora", "mehak.budget.styles", "fashion", ["hinglish"], "Delhi", 88_000, 720, {}),
    ("cr_s03", "Shreya Banerjee", "shreya.skin.notes", "beauty", ["bn", "en"], "Kolkata", 13_500, 390, {}),
    ("cr_s04", "Riya Sood", "riya.glow.lab", "beauty", ["en"], "Mumbai", 52_000, 2_400, {"low_trust": "pod"}),
    # Comedy, education, travel, parenting
    ("cr_c01", "Mohit Yadav", "mohit.office.skits", "comedy", ["hinglish"], "Gurugram", 74_000, 510, {"strong_language": True}),
    ("cr_c02", "Sundar Raman", "sundar.madras.memes", "comedy", ["ta"], "Chennai", 21_000, 430, {}),
    ("cr_e01", "Pallavi Mishra", "pallavi.maths.tricks", "education", ["hi"], "Patna", 33_000, 260, {}),
    ("cr_e02", "Joseph Mathew", "joseph.upsc.daily", "education", ["en", "ml"], "Thiruvananthapuram", 2_900, 310, {}),
    ("cr_v01", "Tenzin Dorje", "tenzin.hill.trails", "travel", ["en", "hi"], "Guwahati", 16_200, 520, {}),
    ("cr_p01", "Bhavana Krishnan", "bhavana.little.lunchbox", "parenting", ["ta", "en"], "Coimbatore", 8_100, 340, {}),
]

# Typical audience age profile by niche.
AGE_PROFILES = {
    "anime_edits": [0.15, 0.55, 0.22, 0.06, 0.02],
    "gaming": [0.18, 0.52, 0.22, 0.06, 0.02],
    "food": [0.02, 0.17, 0.41, 0.27, 0.13],
    "finance": [0.01, 0.34, 0.43, 0.15, 0.07],
    "tech": [0.04, 0.52, 0.33, 0.08, 0.03],
    "fitness": [0.03, 0.33, 0.39, 0.18, 0.07],
    "fashion": [0.06, 0.45, 0.35, 0.10, 0.04],
    "beauty": [0.07, 0.46, 0.33, 0.10, 0.04],
    "comedy": [0.10, 0.44, 0.31, 0.11, 0.04],
    "education": [0.20, 0.50, 0.20, 0.07, 0.03],
    "travel": [0.03, 0.40, 0.40, 0.12, 0.05],
    "parenting": [0.01, 0.10, 0.52, 0.30, 0.07],
}
FEMALE_SHARE = {
    "anime_edits": 0.28, "gaming": 0.18, "food": 0.68, "finance": 0.36, "tech": 0.30,
    "fitness": 0.46, "fashion": 0.78, "beauty": 0.84, "comedy": 0.42, "education": 0.48,
    "travel": 0.44, "parenting": 0.82,
}
SAVE_RATE = {
    "anime_edits": 0.012, "gaming": 0.008, "food": 0.028, "finance": 0.032, "tech": 0.028,
    "fitness": 0.022, "fashion": 0.012, "beauty": 0.016, "comedy": 0.005, "education": 0.036,
    "travel": 0.022, "parenting": 0.026,
}
SHARE_RATE = {
    "anime_edits": 0.010, "gaming": 0.008, "food": 0.010, "finance": 0.012, "tech": 0.009,
    "fitness": 0.008, "fashion": 0.007, "beauty": 0.008, "comedy": 0.018, "education": 0.011,
    "travel": 0.010, "parenting": 0.010,
}

FIRST_NAMES_FOR_DEALS = {
    "food": ["A spice brand", "A kitchenware store", "A dairy brand", "A snacks brand"],
    "anime_edits": ["A merch store", "A gaming accessories brand", "A streaming app"],
    "gaming": ["A gaming accessories brand", "A mobile game studio", "An energy drink brand"],
    "finance": ["A fintech app", "An insurance aggregator", "A stock-learning app"],
    "tech": ["An online course platform", "A laptop brand", "A coding bootcamp"],
    "fitness": ["A nutrition brand", "A sportswear label", "A fitness app"],
    "fashion": ["An ethnic wear label", "A footwear brand", "A jewellery store"],
    "beauty": ["A skincare brand", "A haircare brand", "A cosmetics store"],
    "comedy": ["A food delivery app", "A soft drink brand", "A streaming app"],
    "education": ["An edtech app", "A book publisher", "A test-prep brand"],
    "travel": ["A homestay network", "A luggage brand", "A travel app"],
    "parenting": ["A baby care brand", "A kids nutrition brand", "A toy store"],
}

LAST_DATE = date(2026, 10, 6)


def _stage_reach(followers: int, rng: random.Random) -> float:
    """Median views as a share of followers: smaller accounts often out-reach."""
    if followers < 1_000:
        return rng.uniform(0.9, 2.2)
    if followers < 10_000:
        return rng.uniform(0.6, 1.6)
    if followers < 100_000:
        return rng.uniform(0.35, 1.1)
    return rng.uniform(0.2, 0.6)


def _audience(niche: str, langs: list[str], city: str, rng: random.Random) -> dict:
    base = AGE_PROFILES[niche]
    jitter = [max(0.0, b + rng.uniform(-0.03, 0.03)) for b in base]
    total = sum(jitter)
    ages = {k: round(v / total, 2) for k, v in zip(["13-17", "18-24", "25-34", "35-44", "45+"], jitter)}
    female = min(0.95, max(0.05, FEMALE_SHARE[niche] + rng.uniform(-0.06, 0.06)))
    pool = [city] + [c for c in LANG_CITIES.get(langs[0], []) if c != city]
    shares = [0.24, 0.16, 0.10, 0.07, 0.05, 0.04][: len(pool)]
    cities = [{"name": c, "share": round(s + rng.uniform(-0.02, 0.02), 2)} for c, s in zip(pool, shares)]
    lang_mix = {langs[0]: 0.8 if len(langs) == 1 else 0.62}
    if len(langs) > 1:
        lang_mix[langs[1]] = 0.3
    other = round(1 - sum(lang_mix.values()), 2)
    if other > 0:
        lang_mix["en" if "en" not in lang_mix else "hi"] = other
    return {
        "age": ages,
        "gender": {"male": round(1 - female, 2), "female": round(female, 2)},
        "cities": cities,
        "languages": lang_mix,
    }


def _caption(niche: str, langs: list[str], i: int) -> tuple[str | None, str | None]:
    for lang in langs:
        bank = CAPTIONS.get((niche, lang))
        if bank:
            return bank[i % len(bank)], lang
    return None, None


def _reels(cid: str, niche: str, langs: list[str], followers: int, extras: dict, rng: random.Random) -> list[dict]:
    median = max(120, followers * _stage_reach(followers, rng))
    if followers == 0:
        median = 0
    like_rate = rng.uniform(0.035, 0.075)
    save_rate = SAVE_RATE[niche] * rng.uniform(0.7, 1.35)
    share_rate = SHARE_RATE[niche] * rng.uniform(0.7, 1.35)
    low = extras.get("low_trust")
    if low == "spike":
        median *= 0.18  # bought followers do not watch
        like_rate *= 0.45
    if low == "f4f":
        median *= 0.25
        like_rate *= 0.6
    topics = TOPICS[niche]
    reels = []
    d = LAST_DATE
    n = 12
    for i in range(n):
        views = int(median * rng.lognormvariate(0, 0.45))
        topic = topics[i % len(topics)]
        boost = 1.0
        if niche == "food" and topic == "Quick breakfast":
            boost = 1.35
        views = int(views * boost)
        likes = int(views * like_rate * rng.uniform(0.85, 1.15))
        comment_ratio = rng.uniform(0.012, 0.03)
        if low == "pod":
            comment_ratio = rng.uniform(0.11, 0.16)
        caption, lang = _caption(niche, langs, i)
        reels.append(
            {
                "id": f"{cid}_r{i:02d}",
                "date": d.isoformat(),
                "views": views,
                "likes": likes,
                "saves": int(views * save_rate * rng.uniform(0.8, 1.2) * (1.4 if boost > 1 else 1)),
                "shares": int(views * share_rate * rng.uniform(0.8, 1.2)),
                "comments": max(0, int(likes * comment_ratio)),
                "format": "reels",
                "topic": topic,
                "caption": caption,
                "lang": lang,
                "copyrighted_clips": bool(extras.get("copyright")),
                "original_voiceover": not extras.get("copyright"),
                "is_recent": i < 6,
            }
        )
        d -= timedelta(days=rng.choice([2, 3, 3, 4, 5]))
    return reels


def _follower_history(followers: int, extras: dict, rng: random.Random) -> list[int]:
    weekly_growth = rng.uniform(0.004, 0.03)
    hist = [followers]
    for _ in range(11):
        hist.append(int(hist[-1] / (1 + weekly_growth * rng.uniform(0.6, 1.4))))
    hist = list(reversed(hist))
    if extras.get("low_trust") == "spike":
        # Flat growth, then a one-week jump that organic growth does not explain.
        jump_at = 7
        pre = [int(followers * 0.55 * (1 + 0.01 * k)) for k in range(jump_at)]
        post = [int(followers * (0.97 + 0.005 * k)) for k in range(12 - jump_at)]
        hist = pre + post
        hist[-1] = followers
    return hist


def _income(cid: str, niche: str, followers: int, extras: dict, rng: random.Random) -> tuple[list[dict], list[dict], int | None]:
    months = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
    history: list[dict] = []
    deals: list[dict] = []
    if followers < 1_000 and not extras.get("expertise"):
        return history, deals, None
    rate = None
    if followers >= 3_000:
        rate = int(round(followers * rng.uniform(0.25, 0.45), -2))
    for m in months:
        if extras.get("expertise") and followers < 1_000:
            if rng.random() < 0.7:
                history.append({"month": m, "source": "services", "amount": int(round(rng.uniform(3_000, 12_000), -2)), "recurring": True, "paid_on_time": True, "days_late": 0})
            continue
        if rate and rng.random() < (0.35 if followers < 10_000 else 0.6):
            amt = int(rate * rng.uniform(0.8, 1.25))
            late = rng.random() < 0.3
            history.append({"month": m, "source": "brand", "amount": amt, "recurring": False, "paid_on_time": not late, "days_late": rng.randint(8, 30) if late else 0})
            deals.append({"with": rng.choice(FIRST_NAMES_FOR_DEALS[niche]), "amount": amt, "date": f"{m}-{rng.randint(3, 26):02d}", "deliverables": "1 reel", "basis": "Brand's offer"})
        if followers >= 5_000 and rng.random() < 0.45:
            history.append({"month": m, "source": "affiliate", "amount": int(round(rng.uniform(600, 4_000), -1)), "recurring": True, "paid_on_time": True, "days_late": 0})
        if niche in ("finance", "tech", "fitness", "education") and rng.random() < 0.4:
            history.append({"month": m, "source": "digital", "amount": int(round(rng.uniform(1_000, 9_000), -1)), "recurring": True, "paid_on_time": True, "days_late": 0})
    return history, deals, rate


def build_creator_b() -> dict:
    """Creator B: fictional Tamil home-cooking beginner (2K followers)."""
    rows = [
        # date, views, topic, caption, saves, shares
        ("2026-10-05", 4_800, "Quick breakfast", "10 நிமிடத்தில் ரவா உப்புமா", 372, 96),
        ("2026-10-02", 1_400, "Gravy and curry", "மதுரை ஸ்டைல் காரக் குழம்பு", 31, 12),
        ("2026-09-29", 1_100, "Gravy and curry", "தக்காளி ரசம் எளிய முறை", 22, 9),
        ("2026-09-25", 5_200, "Quick breakfast", "ராகி தோசை - காலை டிபன்", 418, 120),
        ("2026-09-21", 2_300, "Sweets", "சேமியா பாயசம்", 48, 21),
        ("2026-09-17", 900, "Chutney and sides", "வீட்டிலேயே தேங்காய் சட்னி", 21, 6),
        ("2026-09-12", 1_800, "Rice dishes", "எலுமிச்சை சாதம்", 39, 14),
        ("2026-09-07", 700, "Gravy and curry", "அம்மா ஸ்டைல் சாம்பார்", 14, 4),
        ("2026-09-02", 850, "Snacks", "மொறுமொறு வடை செய்வது எப்படி", 19, 7),
        ("2026-08-28", 600, "Snacks", "சுண்டல் - மாலை ஸ்நாக்ஸ்", 10, 3),
    ]
    reels = []
    for i, (d, views, topic, cap, saves, shares) in enumerate(rows):
        likes = int(views * 0.062)
        reels.append({
            "id": f"b_r{i:02d}", "date": d, "views": views, "likes": likes, "saves": saves,
            "shares": shares, "comments": max(2, int(likes * 0.04)), "format": "reels",
            "topic": topic, "caption": cap, "lang": "ta", "copyrighted_clips": False,
            "original_voiceover": True, "is_recent": i < 6,
        })
    return {
        "_id": "cr_b",
        "handle": "creator.b",
        "name": "Creator B",
        "avatar_hue": 24,
        "is_reference": False,
        "reference_note": "Fictional demo profile.",
        "bio": "Tamil home cooking from Madurai.",
        "niche": "food",
        "sub_niches": ["Tamil home cooking", "Quick breakfast"],
        "platforms": ["instagram"],
        "formats": ["reels"],
        "languages": ["ta"],
        "city": "Madurai",
        "region": "South",
        "followers": 2_000,
        "following": 310,
        "posts": 38,
        "avg_likes": int(sum(r["likes"] for r in reels) / len(reels)),
        "avg_comments": int(sum(r["comments"] for r in reels) / len(reels)),
        "reels": reels,
        "follower_history": [1_310, 1_360, 1_420, 1_470, 1_530, 1_580, 1_640, 1_700, 1_770, 1_840, 1_920, 2_000],
        "comment_insights": {"generic_share": 0.12, "sample_size": 90},
        "audience": {
            "age": {"13-17": 0.02, "18-24": 0.17, "25-34": 0.41, "35-44": 0.28, "45+": 0.12},
            "gender": {"male": 0.29, "female": 0.71},
            "cities": [
                {"name": "Madurai", "share": 0.28},
                {"name": "Chennai", "share": 0.22},
                {"name": "Coimbatore", "share": 0.11},
                {"name": "Tiruchirappalli", "share": 0.07},
                {"name": "Bengaluru", "share": 0.06},
                {"name": "Salem", "share": 0.05},
            ],
            "languages": {"ta": 0.92, "en": 0.08},
        },
        "income_goal": {"monthly": 10_000, "types": ["collective", "digital", "affiliate"]},
        "income_history": [],
        "past_deals": [],
        "best_deal": None,
        "current_rate": None,
        "inbound_channels": ["dm"],
        "skills": ["Home cooking", "Recipe writing"],
        "skill_gaps": ["Basic editing"],
        "expertise": "Traditional Tamil home cooking",
        "content_flags": [],
        "discoverable": True,
        "insights_connected": {"instagram": True, "youtube": False},
        "onboarded": True,
        "created_by": "seed",
    }


def build_roster(seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    out = []
    for cid, name, handle, niche, langs, city, followers, following, extras in ROSTER:
        reels = _reels(cid, niche, langs, followers, extras, rng)
        history, deals, rate = _income(cid, niche, followers, extras, rng)
        low = extras.get("low_trust")
        likes = [r["likes"] for r in reels] or [0]
        comments = [r["comments"] for r in reels] or [0]
        generic = rng.uniform(0.08, 0.22)
        if low == "pod":
            generic = rng.uniform(0.62, 0.78)
        if low == "f4f":
            generic = rng.uniform(0.35, 0.45)
        state, region = CITIES[city]
        flags = []
        if extras.get("strong_language"):
            flags.append("strong_language")
        out.append(
            {
                "_id": cid,
                "handle": handle,
                "name": name,
                "avatar_hue": rng.randint(0, 359),
                "is_reference": False,
                "reference_note": FICTIONAL,
                "bio": f"{NICHES[niche]['label']} from {city}.",
                "niche": niche,
                "sub_niches": TOPICS[niche][:2],
                "platforms": ["instagram"] + (["youtube"] if rng.random() < 0.3 else []),
                "formats": ["reels"] + (["carousel"] if niche in ("finance", "education") else []),
                "languages": langs,
                "city": city,
                "state": state,
                "region": region,
                "followers": followers,
                "following": following,
                "posts": rng.randint(40, 420) if followers > 1_000 else rng.randint(8, 40),
                "avg_likes": int(sum(likes) / len(likes)),
                "avg_comments": int(sum(comments) / len(comments)),
                "reels": reels,
                "follower_history": _follower_history(followers, extras, rng),
                "comment_insights": {"generic_share": round(generic, 2), "sample_size": rng.randint(80, 600)},
                "audience": _audience(niche, langs, city, rng),
                "income_goal": {"monthly": int(round(max(8_000, followers * 0.6), -3)), "types": ["brand", "affiliate"]},
                "income_history": history,
                "past_deals": deals,
                "best_deal": max((d["amount"] for d in deals), default=None),
                "current_rate": rate,
                "inbound_channels": ["dm", "bio_email"],
                "skills": [],
                "expertise": extras.get("expertise"),
                "content_flags": flags,
                "discoverable": True,
                "insights_connected": {"instagram": True, "youtube": False},
                "onboarded": True,
                "seed_low_trust": low,  # ground truth for tests only; never shown in UI
                "twin_of": extras.get("twin_of"),
                "created_by": "seed",
            }
        )
    return out
