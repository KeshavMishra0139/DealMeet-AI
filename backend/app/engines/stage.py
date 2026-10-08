"""Creator lifecycle stage: where you are, in words that suggest what to do."""
from __future__ import annotations

from ..services.views import audience_stage
from . import metrics
from . import hindi
from .common import inp, inr, inr_range, short, why

STAGES = {
    "pre_launch": ("Pre-launch", "No audience yet. Start with what you already know."),
    "expert_first": ("Expert, audience later", "You have a real skill. Earn from it now; the audience can follow."),
    "starting": ("Starting", "Build a posting habit and your first income stream."),
    "growing": ("Growing", "Your reach is building. Turn it into steady income."),
    "underpriced": ("Earning, underpriced", "Brands already pay you, but below what your reach supports."),
    "fair": ("Earning, fairly priced", "Your rate matches your reach. Widen your income sources next."),
    "established": ("Established", "Diversified income at scale. Protect it and grow recurring streams."),
}


def detect(c: dict, fair: dict | None) -> dict:
    followers = c.get("followers", 0)
    income = metrics.monthly_income(c)
    rate = c.get("current_rate")
    sources = metrics.income_by_source(c)
    if followers == 0:
        key = "pre_launch"
    elif followers < 1_000 and c.get("expertise"):
        key = "expert_first"
    elif income == 0 and followers < 10_000:
        key = "starting"
    elif rate and fair and rate < 0.7 * fair["range"]["low"]:
        key = "underpriced"
    elif followers >= 100_000 and len(sources) >= 3:
        key = "established"
    elif income > 0:
        key = "fair"
    else:
        key = "growing"
    label, line = STAGES[key]

    reasons, inputs = [], [inp("Followers", short(followers), metrics.prov(c, "followers"))]
    if key == "underpriced" and fair:
        ratio = metrics.reach_ratio(c)
        reasons = [
            f"Your last 6 reels averaged about {ratio:.0f}x your followers in views.",
            f"Your typical deal is {inr(rate)}, but your reach supports {inr_range(fair['range']['low'], fair['range']['high'])} a reel.",
        ]
        if c.get("best_deal"):
            reasons.append(f"Your best deal ({inr(c['best_deal'])}) shows brands will pay more when they see the value.")
        inputs += [
            inp("Average views, last 6 reels", short(metrics.mean_views(c)), metrics.prov(c, "reels.0.views")),
            inp("Typical deal", inr(rate), metrics.prov(c, "current_rate")),
        ]
    elif key == "starting":
        reasons = [
            "No income recorded yet and under 10K followers.",
            "At this stage, consistency and one first income stream matter more than follower count.",
        ]
    elif key == "expert_first":
        reasons = [
            f"You have expertise ({c.get('expertise')}) but under 1K followers.",
            "Services and digital products can earn before an audience exists.",
        ]
    elif key == "fair" and fair:
        reasons = [f"Your typical rate is close to your fair price of {inr_range(fair['range']['low'], fair['range']['high'])}."]
    else:
        reasons = [line]
    sim = metrics.fields_simulated(c, "current_rate", "income_history") if key in ("underpriced", "fair") else []
    return {
        "id": key,
        "label": label,
        "line": line,
        "hi": hindi.stage(key),
        "audience_stage": audience_stage(followers),
        "why": why(reasons, inputs, sim, title=f"Why '{label}'"),
    }
