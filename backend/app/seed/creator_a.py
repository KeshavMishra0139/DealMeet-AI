"""Creator A: reference profile based on a real creator field interview.

Identity is withheld. Only the values marked "real" come from the interview and
public snapshot; everything marked "simulated" is illustrative for the demo.
No captions or statements are stored, so nothing is attributed to the creator.
"""
from __future__ import annotations

REFERENCE_NOTE = (
    "Reference profile based on a real creator interview. Identity withheld; some fields simulated."
)

# Last six reels: views and dates are real. Format labels and every engagement
# number besides views are simulated.
_LAST_SIX = [
    # date, views (real) | format, likes, saves, shares, comments (simulated)
    ("2026-09-20", 359_000, "Beat-sync fight edit", 17_950, 6_820, 4_310, 184),
    ("2026-09-22", 142_000, "Emotional slow-mo edit", 7_100, 1_990, 1_420, 73),
    ("2026-09-27", 88_900, "Meme edit", 4_450, 530, 1_420, 45),
    ("2026-09-28", 33_200, "Manga-panel transition", 1_660, 300, 170, 17),
    ("2026-09-29", 210_000, "Beat-sync fight edit", 10_500, 3_990, 2_520, 107),
    ("2026-10-01", 117_000, "Emotional slow-mo edit", 5_850, 1_640, 1_170, 60),
]

# Earlier reels: the 50K-150K range is real; the individual reels are simulated.
_EARLIER = [
    ("2026-08-14", 72_000, "Character tribute", 3_600, 790, 500, 38),
    ("2026-08-19", 131_000, "Beat-sync fight edit", 6_550, 2_490, 1_570, 66),
    ("2026-08-24", 58_000, "Meme edit", 2_900, 350, 930, 30),
    ("2026-08-30", 96_000, "Emotional slow-mo edit", 4_800, 1_340, 960, 49),
    ("2026-09-05", 144_000, "Beat-sync fight edit", 7_200, 2_740, 1_730, 74),
    ("2026-09-12", 63_000, "Manga-panel transition", 3_150, 570, 320, 32),
]


def _reel(i: int, row: tuple, real_views: bool) -> dict:
    date, views, fmt, likes, saves, shares, comments = row
    return {
        "id": f"a_r{i:02d}",
        "date": date,
        "views": views,
        "likes": likes,
        "saves": saves,
        "shares": shares,
        "comments": comments,
        "format": "reels",
        "topic": fmt,
        "caption": None,
        "lang": None,
        "copyrighted_clips": True,
        "original_voiceover": False,
        "is_recent": real_views,
    }


def build() -> tuple[dict, dict[str, str]]:
    reels = [_reel(i, r, True) for i, r in enumerate(_LAST_SIX)]
    reels += [_reel(i + len(_LAST_SIX), r, False) for i, r in enumerate(_EARLIER)]

    creator = {
        "_id": "cr_a",
        "handle": "creator.a",
        "name": "Creator A",
        "avatar_hue": 268,
        "is_reference": True,
        "reference_note": REFERENCE_NOTE,
        "bio": "Anime-edit reels in Hindi and English.",
        "niche": "anime_edits",
        "sub_niches": ["Beat-sync edits", "Slow-mo edits", "Meme edits"],
        "platforms": ["instagram"],
        "formats": ["reels"],
        "languages": ["hi", "en"],
        "city": None,
        "region": "North India",
        "followers": 21_300,
        "following": 39,
        "posts": 106,
        "avg_likes": 7_900,
        "avg_comments": 81,
        "earlier_views_range": [50_000, 150_000],
        "reels": reels,
        "follower_history": [
            17_450, 17_820, 18_130, 18_420, 18_790, 19_060,
            19_380, 19_720, 20_050, 20_410, 20_880, 21_300,
        ],
        "comment_insights": {"generic_share": 0.17, "sample_size": 420},
        "audience": {
            "age": {"13-17": 0.14, "18-24": 0.58, "25-34": 0.21, "35-44": 0.05, "45+": 0.02},
            "gender": {"male": 0.76, "female": 0.24},
            "cities": [
                {"name": "Delhi", "share": 0.14},
                {"name": "Mumbai", "share": 0.09},
                {"name": "Lucknow", "share": 0.07},
                {"name": "Jaipur", "share": 0.06},
                {"name": "Patna", "share": 0.05},
                {"name": "Pune", "share": 0.04},
            ],
            "languages": {"hi": 0.62, "en": 0.38},
        },
        "income_goal": {"monthly": 50_000, "types": ["brand", "affiliate", "collective"]},
        "income_history": [
            {"month": "2026-04", "source": "brand", "amount": 6_000, "recurring": False, "paid_on_time": False, "days_late": 18},
            {"month": "2026-05", "source": "brand", "amount": 7_500, "recurring": False, "paid_on_time": True, "days_late": 0},
            {"month": "2026-06", "source": "page", "amount": 1_500, "recurring": False, "paid_on_time": True, "days_late": 0},
            {"month": "2026-07", "source": "brand", "amount": 20_000, "recurring": False, "paid_on_time": True, "days_late": 0},
            {"month": "2026-08", "source": "brand", "amount": 7_000, "recurring": False, "paid_on_time": False, "days_late": 25},
            {"month": "2026-09", "source": "brand", "amount": 6_500, "recurring": False, "paid_on_time": True, "days_late": 0},
        ],
        "past_deals": [
            {"with": "A gaming accessories store", "amount": 6_000, "date": "2026-04-11", "deliverables": "1 reel", "basis": "Brand's offer"},
            {"with": "An energy drink brand", "amount": 7_500, "date": "2026-05-06", "deliverables": "1 reel", "basis": "Brand's offer"},
            {"with": "A streaming app", "amount": 20_000, "date": "2026-07-09", "deliverables": "1 reel", "basis": "No clear basis"},
            {"with": "A headphones brand", "amount": 7_000, "date": "2026-08-03", "deliverables": "1 reel", "basis": "Brand's offer"},
            {"with": "A sneaker store", "amount": 6_500, "date": "2026-09-08", "deliverables": "1 reel", "basis": "Brand's offer"},
        ],
        "best_deal": 20_000,
        "current_rate": 7_000,
        "inbound_channels": ["bio_email", "dm"],
        "skills": ["Video editing", "Beat sync", "Colour grading"],
        "expertise": None,
        "content_flags": [],
        "discoverable": True,
        "insights_connected": {"instagram": True, "youtube": False},
        "onboarded": True,
        "created_by": "seed",
    }

    real = [
        "niche", "platforms", "formats", "languages", "followers", "following", "posts",
        "avg_likes", "avg_comments", "earlier_views_range", "best_deal", "inbound_channels",
        "past_deals.2.amount",
    ]
    for i in range(len(_LAST_SIX)):
        real += [f"reels.{i}.views", f"reels.{i}.date"]
    for i in range(len(_LAST_SIX)):
        real += [f"reels.{i}.copyrighted_clips"]  # anime edits are built from show clips

    simulated = [
        "region", "sub_niches", "audience", "audience.age", "audience.gender",
        "audience.cities", "audience.languages", "income_goal", "income_history",
        "past_deals", "current_rate", "follower_history", "comment_insights", "skills", "bio",
    ]
    for i, _ in enumerate(reels):
        for f in ("likes", "saves", "shares", "comments", "topic"):
            simulated.append(f"reels.{i}.{f}")
        if i >= len(_LAST_SIX):
            simulated += [f"reels.{i}.views", f"reels.{i}.date", f"reels.{i}.copyrighted_clips"]

    provenance = {k: "simulated" for k in simulated}
    provenance.update({k: "real" for k in real})
    return creator, provenance
