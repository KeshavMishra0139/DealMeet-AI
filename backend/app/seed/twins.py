"""Reference twins: mock public profiles one or two stages ahead, in the same
niche and language, with what they did next. Clearly labelled as mock."""

TWINS: dict[str, list[dict]] = {
    "anime_edits": [
        {"name": "Hindi anime recap page", "followers": 142_000, "platform": "Instagram", "languages": ["hi", "en"],
         "steps": ["Added Hindi voiceover recaps at about 45K followers", "Switched brand pricing from a flat fee to views", "Launched a ₹199 editing preset pack"],
         "lesson": "Original voiceover made brand deals easier to sign."},
        {"name": "Anime edit and merch page", "followers": 98_000, "platform": "Instagram", "languages": ["hinglish"],
         "steps": ["Joined a 12-creator merch collective", "Put an affiliate link in bio and stories", "Affiliate grew to about a third of income"],
         "lesson": "Recurring affiliate income smoothed out months without brand deals."},
        {"name": "Gaming and anime crossover editor", "followers": 210_000, "platform": "Instagram + YouTube Shorts", "languages": ["hi", "en"],
         "steps": ["Reposted the best reels to YouTube Shorts", "Started a weekly 'top edits' series", "Began taking paid edit commissions"],
         "lesson": "A second platform doubled reach without new content."},
    ],
    "gaming": [
        {"name": "Hinglish clutch-clips creator", "followers": 180_000, "platform": "Instagram + YouTube", "languages": ["hinglish"],
         "steps": ["Weekly highlight series", "Peripheral brand deals priced on views", "Paid coaching sessions"],
         "lesson": "A predictable series made sponsors easier to land."},
        {"name": "Mobile gaming tips page", "followers": 120_000, "platform": "Instagram", "languages": ["hi"],
         "steps": ["Settings guides for each new update", "Sold a ₹149 sensitivity guide", "Joined a gaming collective"],
         "lesson": "Practical guides get saved, and saved posts sell products."},
        {"name": "Speedrun explainer", "followers": 65_000, "platform": "YouTube Shorts", "languages": ["en"],
         "steps": ["Explained one trick per short", "Built a Discord community", "Community memberships became recurring income"],
         "lesson": "Teaching beat showing off for steady growth."},
    ],
    "food:ta": [
        {"name": "Tamil breakfast reels creator", "followers": 18_400, "platform": "Instagram", "languages": ["ta"],
         "steps": ["Posted a 10-minute breakfast daily for a month", "First FMCG collective at about 9K followers", "Started a monthly masala brand retainer"],
         "lesson": "A clear, repeatable format grew faster than mixed recipes."},
        {"name": "Chettinad home cook", "followers": 42_000, "platform": "Instagram", "languages": ["ta"],
         "steps": ["Sold a ₹149 e-book of 25 family recipes", "About 600 copies in 6 months", "Added weekend cooking classes"],
         "lesson": "Recipes people save are recipes people will pay to keep."},
        {"name": "Millet recipes creator", "followers": 110_000, "platform": "Instagram + YouTube", "languages": ["ta", "en"],
         "steps": ["Kitchenware affiliate links on every reel", "Grew a long-form YouTube channel", "Annual deal with a millet brand"],
         "lesson": "Affiliate links compound when every recipe uses the product."},
    ],
    "food": [
        {"name": "Regional home-cooking creator", "followers": 25_000, "platform": "Instagram", "languages": [],
         "steps": ["A daily quick-recipe series", "First FMCG collective", "A ₹199 recipe e-book"],
         "lesson": "Consistency in one format beat variety."},
        {"name": "Tiffin and lunchbox creator", "followers": 60_000, "platform": "Instagram", "languages": [],
         "steps": ["Lunchbox ideas every weekday", "Kitchenware affiliate", "A meal-planning product"],
         "lesson": "Solving a weekday problem kept people coming back."},
        {"name": "Festival sweets creator", "followers": 140_000, "platform": "Instagram + YouTube", "languages": [],
         "steps": ["Seasonal series before each festival", "Brand retainers around festivals", "Cooking classes"],
         "lesson": "Planning around festivals made income predictable."},
    ],
}

GENERIC = [
    {"name": "Creator one stage ahead", "followers": 0, "platform": "Instagram", "languages": [],
     "steps": ["Picked one format and posted it weekly", "Priced deals on views, not followers", "Added one recurring income stream"],
     "lesson": "Focus and one recurring stream made the biggest difference."},
    {"name": "Creator two stages ahead", "followers": 0, "platform": "Instagram + YouTube", "languages": [],
     "steps": ["Repurposed reels to a second platform", "Joined a collective for bigger brands", "Launched a small digital product"],
     "lesson": "A second platform and a product reduced dependence on brand deals."},
    {"name": "Expert-led creator", "followers": 0, "platform": "Instagram", "languages": [],
     "steps": ["Sold a service before growing an audience", "Turned common questions into reels", "Packaged answers into a product"],
     "lesson": "Expertise earned before the audience did."},
]
