"""Next-Step Engine: every week, the creator's next 3 moves.

Each move has a reason, a rupee or growth impact (as a range with
assumptions), an effort (S/M/L) and a "why". Creators mark moves done and log
how it went; next week's plan adapts: what worked gets a follow-up, what didn't
gets an alternative, and skipped moves carry over once.
"""
from __future__ import annotations

from datetime import timedelta

from ..config import get_settings, now_iso, today
from ..db import get_db
from ..seed.catalog import NICHES
from . import brand_safety, hindi, metrics
from .common import estimate, inp, inr, inr_range, percentile, short, why

EFFORT_HINT = {"S": "About 15 minutes", "M": "A few hours", "L": "A few days"}
CATEGORY_ORDER = ["money", "growth", "opportunity"]


def week_start(week: int):
    t = today()
    monday = t - timedelta(days=t.weekday())
    if not get_settings().demo_mode:
        return monday  # a live site: the week the plan is made in
    return monday + timedelta(days=7 * (week - 1))


def _move(kind, category, title, reason, impact, effort, why_, cta, priority, **extra):
    return {
        "kind": kind,
        "category": category,
        "title": title,
        "reason": reason,
        "impact": impact,
        "effort": effort,
        "effort_hint": EFFORT_HINT[effort],
        "why": why_,
        "cta": cta,
        "priority": priority,
        "status": "open",
        "outcome": None,
        **extra,
    }


def _top_share(ctx) -> int | None:
    sources = (ctx.get("durable") or {}).get("sources") or []
    return round(max(s["share"] for s in sources) * 100) if ctx["durable"].get("warning") and sources else None


# ---------------------------------------------------------------- generators
def g_raise_rate(c, ctx):
    rate, fair = c.get("current_rate"), ctx["fair"]
    if not rate or fair["range"]["low"] <= rate * 1.3:
        return None
    ratio = metrics.reach_ratio(c)
    dpm = metrics.brand_deals_per_month(c) or 0.5
    lo_d, hi_d = max(0.5, dpm * 0.6), max(1.0, dpm * 1.4)
    mid = (fair["range"]["low"] + fair["range"]["high"]) / 2
    return _move(
        "raise_rate",
        "money",
        f"Raise your {metrics.post_noun(c)} rate to {inr_range(fair['range']['low'], fair['range']['high'])}",
        f"Your {metrics.post_noun(c)}s reach about {ratio:.0f}x your {metrics.audience_noun(c)}, but you're priced on {metrics.audience_noun(c)}.",
        estimate(
            (mid - rate) * lo_d,
            (mid - rate) * hi_d,
            "inr",
            "month",
            [
                f"{lo_d:.1f} to {hi_d:.1f} brand deals a month, as in the last 6 months",
                f"Brands accept {inr_range(fair['range']['low'], fair['range']['high'])} when shown the breakdown",
            ],
            "medium",
        ),
        "S",
        why(
            [
                f"Your last 6 {metrics.post_noun(c)}s averaged {short(metrics.mean_views(c))} views on {short(c['followers'])} {metrics.audience_noun(c)}: about {ratio:.0f}x.",
                f"Your typical deal is {inr(rate)}, which is roughly {inr(c['followers'] * 0.33)} at {metrics.audience_noun(c)[:-1]} rates.",
                f"Priced on reach, a well-fitting brand like {fair['lister_name'] or 'yours'} should pay {inr_range(fair['range']['low'], fair['range']['high'])}.",
            ]
            + ([f"Your best deal ({inr(c['best_deal'])}) shows brands will pay more when they see the value."] if c.get("best_deal") else []),
            [
                inp(f"Average views, last 6 {metrics.post_noun(c)}s", short(metrics.mean_views(c)), metrics.prov(c, "reels.0.views")),
                inp(metrics.audience_noun(c).capitalize(), short(c["followers"]), metrics.prov(c, "followers")),
                inp("Typical deal", inr(rate), metrics.prov(c, "current_rate")),
                inp("Fair price", inr_range(fair["range"]["low"], fair["range"]["high"])),
            ],
            metrics.fields_simulated(c, "current_rate", "past_deals"),
            title="Why raise your rate",
        ),
        {"label": "See your price breakdown", "to": "/creator/money"},
        0.95,
        hi=hindi.move("raise_rate", low=fair["range"]["low"], high=fair["range"]["high"], ratio=ratio),
    )


def g_double_down(c, ctx):
    if ctx["gaps"] and ctx["gaps"][0]["kind"] == "topic":
        return None
    topics = [t for t in metrics.by_topic(c) if t["count"] >= 2]
    if not topics:
        return None
    best = max(topics, key=lambda t: (t["median_views"], t["save_rate"] or 0))
    views = best["views"]
    lo, hi = 2 * percentile(views, 0.25), 2 * percentile(views, 0.5)
    saved = [t for t in topics if t["save_rate"] is not None]  # YouTube videos don't report saves
    most_saved = bool(saved) and max(saved, key=lambda t: t["save_rate"])["topic"] == best["topic"]
    sim = metrics.fields_simulated(c, "reels.saves", "reels.topic")
    return _move(
        "double_down",
        "growth",
        f"Post 2 more {metrics.topic_plural(best['topic'])} this week",
        f"Your {metrics.topic_plural(best['topic'])} get the most views" + (" and the most saves." if most_saved else "."),
        estimate(lo, hi, "views", "week", [f"Each new one performs like your typical {metrics.topic_name(best['topic'])} (25th to 50th percentile)", "You post at your usual times"], "medium"),
        "M",
        why(
            [
                f"{best['count']} {metrics.topic_plural(best['topic'])} so far, median {short(best['median_views'])} views.",
                f"{best['save_rate'] * 100:.1f}% of viewers save them, the highest of your formats." if most_saved else "",
                "Doubling down on what already works is the fastest growth you can get.",
            ],
            [inp("Median views", short(best["median_views"]), metrics.prov(c, "reels.0.views"))]
            + ([inp("Saves per view", f"{best['save_rate'] * 100:.1f}%", metrics.prov(c, "reels.0.saves"))] if best["save_rate"] is not None else []),
            sim,
            title="Why this format",
        ),
        {"label": "See what's working", "to": "/creator/roadmap"},
        0.8,
        hi=hindi.move("double_down", topic=metrics.topic_plural(best["topic"]), most_saved=most_saved),
    )


def g_content_gap(c, ctx):
    gap = next((g for g in ctx["gaps"] if g["kind"] == "topic"), None)
    if not gap:
        return None
    topic = gap["id"].split(":", 1)[1]
    views = [r["views"] for r in c.get("reels") or [] if r.get("topic") == topic]
    lo, hi = 2 * min(views) * 0.8, 2 * percentile(views, 0.5)
    return _move(
        "content_gap",
        "growth",
        f"Post 2 {gap['title']} this week",
        f"{gap['evidence'][0]} {gap['evidence'][1]}",
        estimate(lo, hi, "views", "week", ["Each new reel performs like your earlier ones on this topic", "Peers keep posting at today's pace"], "medium"),
        "M",
        gap["why"],
        {"label": "See topic ideas", "to": "/creator/roadmap"},
        0.9,
        hi=hindi.move("content_gap", topic=gap["title"], lift=gap["lift"], supply=gap["supply"]),
    )


def g_voiceover(c, ctx):
    safety = brand_safety.assess(c)
    if not any(f["id"] == "copyrighted_clips" for f in safety["flags"]):
        return None
    uplift = ctx["fair"]["per_reel"] * 0.06
    return _move(
        "voiceover",
        "growth",
        "Add your own voiceover to your next edit",
        "Brands hesitate on edits built only from show clips. Your voice makes it original.",
        estimate(uplift * 0.8, uplift * 1.1, "inr", "deal", ["Removes the brand-safety adjustment from your fair price", "Applies to each brand reel"], "medium"),
        "M",
        why(["Anime edits use show clips, which brands treat as a copyright risk.", "Commentary or voiceover makes the work yours."], title="Why add your voice"),
        {"label": "See the roadmap", "to": "/creator/roadmap"},
        0.65,
        hi=hindi.move("voiceover"),
    )


def g_apply_matches(c, ctx):
    picks = [o for o in ctx["opps"] if o["type"] in ("brand_campaign", "pr_service") and not o["applied"]
             and o["deal_kind"] == "paid" and o["fit"] >= 80 and o["value"].get("estimate")][:2]
    if len(picks) < 2:
        return None
    lo = sum(o["value"]["estimate"]["low"] for o in picks)
    hi = sum(o["value"]["estimate"]["high"] for o in picks)
    return _move(
        "apply_matches",
        "opportunity",
        "Apply to these 2 matched opportunities",
        f"{picks[0]['title']} and {picks[1]['title']} fit your audience ({picks[0]['fit']} and {picks[1]['fit']} out of 100).",
        estimate(lo, hi, "inr", "deal", ["If both accept", "Paid at the listing budget, up to your fair price"], "medium"),
        "S",
        why(picks[0]["why"]["reasons"][:2] + [f"Both fund escrow before you post, and it's released after the post is approved."], [inp(o["title"], f"Fit {o['fit']}") for o in picks],
            ["audience demographics"] if any(o["why"]["simulated_fields"] for o in picks) else [], title="Why these two"),
        {"label": "View the matches", "to": "/creator/opportunities"},
        0.75,
        listing_ids=[o["id"] for o in picks],
        hi=hindi.move("apply_matches", a=picks[0]["title"], b=picks[1]["title"], fa=picks[0]["fit"], fb=picks[1]["fit"]),
    )


def g_join_collective(c, ctx):
    coll = [o for o in ctx["opps"] if o["type"] == "collective" and not o["applied"] and o["fit"] >= 80]
    if not coll:
        return None
    o = max(coll, key=lambda x: x["fit"])
    est = o["value"]["estimate"]
    small = c.get("followers", 0) < 10_000
    return _move(
        "join_collective",
        "opportunity",
        f"Opt in to the {o['lister']['name']} collective",
        f"{o['lister']['name']} is booking {o['collective_size']} creators like you in one pack. Your share is priced on your reach.",
        est,
        "S",
        why([f"Fit {o['fit']}/100 for {o['title']}.", "One escrow payment from the brand, split among the members.", "A big-brand deal without needing a big following."],
            [inp("Your share", inr_range(est["low"], est["high"]))], title="Why this collective"),
        {"label": "See the collective", "to": "/creator/opportunities"},
        0.85 if small else 0.6,
        listing_ids=[o["id"]],
        hi=hindi.move("join_collective", brand=o["lister"]["name"], size=o["collective_size"]),
    )


def g_digital(c, ctx):
    p = next((p for p in ctx["paths"][:3] if p["type"] == "digital" and not p["active"]), None)
    if not p:
        return None
    return _move(
        "digital",
        "money",
        f"Draft your {p['title']}",
        p["why"]["reasons"][0],
        p["estimate"],
        "M",
        p["why"],
        {"label": "See money paths", "to": "/creator/money"},
        0.7,
        hi=hindi.move("digital", title=p["title"]),
    )


def g_affiliate(c, ctx):
    p = next((p for p in ctx["paths"] if p["type"] == "affiliate" and not p["active"]), None)
    if not p or not (ctx["durable"].get("warning") or c.get("followers", 0) < 10_000):
        return None
    return _move(
        "affiliate",
        "money",
        p["first_step"],
        (ctx["durable"]["warning"] + " A link adds income that repeats.") if ctx["durable"].get("warning") else p["why"]["reasons"][0],
        p["estimate"],
        "S",
        p["why"],
        {"label": "See money paths", "to": "/creator/money"},
        0.6,
        hi=hindi.move("affiliate", share=_top_share(ctx)),
    )


def g_service(c, ctx):
    if not (c.get("followers", 0) < 1_000 and c.get("expertise")):
        return None
    p = next((p for p in ctx["paths"] if p["type"] == "services"), None)
    if not p:
        return None
    return _move("service", "money", f"Offer {p['title'].lower()} from your link-in-bio", p["why"]["reasons"][0], p["estimate"], "S", p["why"],
                 {"label": "Set up your page", "to": "/creator/kit"}, 0.92, hi=hindi.move("service"))


def g_rate_card(c, ctx):
    if c.get("current_rate") or c.get("followers", 0) < 1_000:
        return None
    fair = ctx["fair"]
    return _move(
        "rate_card",
        "money",
        f"Set your first rate card at {inr_range(fair['range']['low'], fair['range']['high'])} a {metrics.post_noun(c)}",
        "Brands take you seriously when you name a price with reasons.",
        estimate(fair["range"]["low"] * 0.5, fair["range"]["high"], "inr", "month", [f"About one paid {metrics.post_noun(c)} a month to start"], "low"),
        "S",
        fair["why"],
        {"label": "See your media kit", "to": "/creator/kit"},
        0.5,
        hi=hindi.move("rate_card", low=fair["range"]["low"], high=fair["range"]["high"]),
    )


# Fallbacks: only to fill a plan the moves above leave short of 3, so no week has an empty
# slot. Built from the creator's own numbers and settings, never from sample listings.
def fb_steady_pace(c, ctx):
    if not metrics.has_reels(c):
        return None
    noun, recent = metrics.post_noun(c), metrics.recent(c)
    pace = metrics.posts_per_week(c)
    target = max(1, min(3, round(pace) + 1))
    views = [r["views"] for r in recent]
    plural = f"{noun}s" if target != 1 else noun
    return _move(
        "steady_pace",
        "growth",
        f"Post {target} {plural} this week",
        f"You posted {pace:.1f} {noun}s a week over the last 4 weeks. A steady pace gives brands, and your fair price, recent views to go on.",
        estimate(target * percentile(views, 0.25), target * percentile(views, 0.5), "views", "week",
                 [f"Each new {noun} performs like your typical one (25th to 50th percentile of your last {len(views)})"], "medium"),
        "M",
        why(
            [f"Your last {len(views)} {noun}s had a median of {short(metrics.median_views(c))} views.", f"{pace:.1f} {noun}s a week over the last 4 weeks."],
            [
                inp("Median views", short(metrics.median_views(c)), metrics.prov(c, "reels.0.views")),
                inp(f"{noun.capitalize()}s a week", f"{pace:.1f}", metrics.prov(c, "reels.0.date")),
            ],
            metrics.recent_simulated(c, "views"),
            title="Why a steady pace",
        ),
        {"label": "See what's working", "to": "/creator/roadmap"},
        0.3,
        hi=hindi.move("steady_pace", n=target, video=noun == "video"),
    )


def fb_real_numbers(c, ctx):
    """No views on file: everything runs on an estimate from the follower count."""
    if metrics.has_reels(c) or (c.get("manual") or {}).get("avg_views") or (c.get("channels") or {}).get("youtube") or (c.get("channels") or {}).get("instagram"):
        return None
    from ..services import youtube_public

    fair, link = ctx["fair"], youtube_public.configured()
    return _move(
        "real_numbers",
        "growth",
        "Link your YouTube channel" if link else "Add your average views",
        f"Your price and moves use an estimate from your {metrics.audience_noun(c)[:-1]} count. Your real views make them fit you.",
        estimate(fair["range"]["low"], fair["range"]["high"], "inr", "deal", ["Your fair price per post today, from that estimate: real views can move it either way"], "low"),
        "S",
        why(
            [f"Priced on about {short(metrics.median_views(c))} views a post, estimated from {short(c.get('followers', 0))} {metrics.audience_noun(c)}.", "Moves like posting more of what works need your real views."],
            [inp(metrics.audience_noun(c).capitalize(), short(c.get("followers", 0)), metrics.prov(c, "followers"))],
            title="Why your real numbers",
        ),
        {"label": "Link your channel", "to": "/creator/connections"} if link else {"label": "Add your views", "to": "/creator/profile"},
        0.3,
        hi=hindi.move("real_numbers", link=link),
    )


def fb_share_kit(c, ctx):
    fair, noun = ctx["fair"], metrics.post_noun(c)
    niche = NICHES[c["niche"]]["label"].lower()
    return _move(
        "share_kit",
        "money",
        f"Send your media kit to 3 {niche} brands",
        f"Your kit shows your numbers and a fair price with reasons: {inr_range(fair['range']['low'], fair['range']['high'])} a {noun}.",
        estimate(0, fair["range"]["high"], "inr", "month", [f"If one of the 3 brands books one paid {noun} at your fair price", "Many brands don't reply; that's normal"], "low"),
        "S",
        why(
            [f"Your fair price is {inr_range(fair['range']['low'], fair['range']['high'])} a {noun}, priced on {short(metrics.median_views(c))} median views.", "A short note with your kit link is enough."],
            title="Why reach out",
        ),
        {"label": "Open your media kit", "to": "/creator/kit"},
        0.28,
        hi=hindi.move("share_kit", niche=niche),
    )


def fb_dream_brands(c, ctx):
    from ..services.directory import VISIBLE

    db = get_db()
    # Only when there are brands to save (a new live site may have none yet).
    if db.wishlists.count_documents({"creator_id": c["_id"]}) >= 3 or db.brands.count_documents(VISIBLE) < 3:
        return None
    fair, noun = ctx["fair"], metrics.post_noun(c)
    return _move(
        "dream_brands",
        "opportunity",
        "Save 3 Dream Brands",
        "When a brand you saved opens a campaign, it shows up in your Dream Brands news.",
        estimate(fair["range"]["low"], fair["range"]["high"], "inr", "deal", [f"If a saved brand opens a campaign that fits and books one {noun} at your fair price"], "low"),
        "S",
        why([f"Brands in {NICHES[c['niche']]['label'].lower()} post campaigns here.", "Saving them is how you hear first."], title="Why Dream Brands"),
        {"label": "Browse brands", "to": "/creator/brands"},
        0.26,
        hi=hindi.move("dream_brands"),
    )


def fb_profile(c, ctx):
    """The first unfinished item of the profile brands search and read."""
    from ..services.profile import completeness

    todo = next((i for i in completeness(c)["items"] if not i["done"]), None)
    if not todo:
        return None
    fair, noun = ctx["fair"], metrics.post_noun(c)
    return _move(
        "finish_profile",
        "opportunity",
        f"Finish your profile: {todo['label'].lower()}",
        todo["fix"],
        estimate(fair["range"]["low"], fair["range"]["high"], "inr", "deal", [f"If a brand finds you in search and books one {noun} at your fair price"], "low"),
        "S",
        why(["Brands search creators by niche, city, language and reach.", "A complete profile shows them what they need to say yes."], title="Why finish your profile"),
        {"label": "Open your profile", "to": "/creator/profile"},
        0.24,
        hi=hindi.move("finish_profile"),
    )


FALLBACKS = [fb_steady_pace, fb_real_numbers, fb_share_kit, fb_dream_brands, fb_profile]


# Follow-ups, chosen by last week's outcomes.
def f_lock_rate(c, ctx, prev):
    amount = (prev.get("outcome") or {}).get("amount") or ctx["fair"]["range"]["low"]
    return _move(
        "lock_rate",
        "money",
        f"Send your {inr(amount)} rate card to 3 past brands",
        "Your new rate landed. Anchor it with brands who already know your work.",
        estimate((amount - (c.get("current_rate") or amount * 0.5)) * 0.3, (amount - (c.get("current_rate") or amount * 0.5)) * 0.9, "inr", "month",
                 ["One or two past brands rebook at the new rate"], "medium"),
        "S",
        why(["Last week's rate raise worked.", "Past brands rebook faster than new ones."], title="Why follow up"),
        {"label": "Open your media kit", "to": "/creator/kit"},
        0.93,
        follow_up_of="raise_rate",
        hi=hindi.move("lock_rate", amount=amount),
    )


def f_bundle(c, ctx, prev):
    fair = ctx["fair"]
    lo, hi = fair["range"]["low"] * 1.85, fair["range"]["high"] * 1.85
    return _move(
        "bundle_offer",
        "money",
        f"Offer a 2-{metrics.post_noun(c)} bundle at {inr_range(lo, hi)} instead of cutting your rate",
        "Brands that balk at one higher price often say yes to more value per rupee.",
        estimate(lo * 0.4, hi * 0.8, "inr", "month", ["One brand in three takes the bundle"], "low"),
        "S",
        why(["Last week's rate raise was turned down.", f"A bundle keeps your per-{metrics.post_noun(c)} rate intact."], title="Why a bundle"),
        {"label": "See your price breakdown", "to": "/creator/money"},
        0.9,
        follow_up_of="raise_rate",
        hi=hindi.move("bundle_offer", low=lo, high=hi),
    )


def f_series(c, ctx, prev):
    return _move(
        "series",
        "growth",
        "Make it a weekly series with a fixed day",
        "Your last posts in this format worked. A fixed day turns viewers into regulars.",
        prev["impact"],
        "M",
        why(["Last week's format posts worked.", "Series build habit and predictable reach, which brands pay more for."], title="Why a series"),
        prev["cta"],
        0.86,
        follow_up_of=prev["kind"],
        hi=hindi.move("series"),
    )


def f_new_hook(c, ctx, prev):
    return _move(
        "new_hook",
        "growth",
        "Test a new first-second hook on the same format",
        "The format still fits your audience; the opening may be the issue.",
        prev["impact"],
        "M",
        why(["Last week's posts underperformed.", "Most viewers decide in the first second."], title="Why test a hook"),
        prev["cta"],
        0.85,
        follow_up_of=prev["kind"],
        hi=hindi.move("new_hook"),
    )


GENERATORS = [g_raise_rate, g_service, g_digital, g_affiliate, g_rate_card, g_content_gap, g_double_down, g_voiceover, g_apply_matches, g_join_collective]
FOLLOW_UPS = {
    ("raise_rate", "worked"): f_lock_rate,
    ("raise_rate", "partly"): f_lock_rate,
    ("raise_rate", "no"): f_bundle,
    ("double_down", "worked"): f_series,
    ("double_down", "no"): f_new_hook,
    ("content_gap", "worked"): f_series,
    ("content_gap", "no"): f_new_hook,
}


def generate_moves(c: dict, ctx: dict, previous: dict | None = None) -> tuple[list[dict], list[str]]:
    learning = c.get("learning") or {}
    candidates, changes, skip_kinds = [], [], set()
    if previous:
        for m in previous["moves"]:
            res = (m.get("outcome") or {}).get("result")
            if m["status"] == "done":
                skip_kinds.add(m["kind"])
                f = FOLLOW_UPS.get((m["kind"], res))
                if f:
                    candidates.append(f(c, ctx, m))
                    verb = {"worked": "worked", "partly": "partly worked", "no": "didn't land"}[res]
                    changes.append(f"'{m['title']}' {verb}, so this week {('builds on it' if res != 'no' else 'tries another way')}.")
            elif m["status"] in ("open", "skipped"):
                skip_kinds.add(m["kind"]) if m.get("carried_over") else None
    for gen in GENERATORS:
        mv = gen(c, ctx)
        if mv and mv["kind"] not in skip_kinds:
            stats = learning.get(mv["kind"]) or {}
            mv["priority"] += 0.05 * (stats.get("wins", 0) - stats.get("misses", 0))
            candidates.append(mv)
    if previous:
        for m in previous["moves"]:
            if m["status"] != "done" and not m.get("carried_over"):
                fresh = next((x for x in candidates if x["kind"] == m["kind"]), None)
                if fresh:
                    fresh["carried_over"] = True
                    fresh["priority"] -= 0.02
                    changes.append(f"'{fresh['title']}' carries over from last week.")
    picked: list[dict] = []
    for cat in CATEGORY_ORDER:
        pool = sorted([m for m in candidates if m["category"] == cat and m not in picked], key=lambda m: -m["priority"])
        if pool:
            picked.append(pool[0])
    rest = sorted([m for m in candidates if m not in picked], key=lambda m: -m["priority"])
    picked += rest[: max(0, 3 - len(picked))]
    if len(picked) < 3:
        # Short of 3: fill from the fallbacks, categories the plan doesn't have yet first.
        have, kinds = {m["category"] for m in picked}, {m["kind"] for m in picked} | skip_kinds
        extra = [m for m in (f(c, ctx) for f in FALLBACKS) if m and m["kind"] not in kinds]
        extra.sort(key=lambda m: (m["category"] in have, -m["priority"]))
        picked += extra[: 3 - len(picked)]
    picked = sorted(picked[:3], key=lambda m: -m["priority"])
    return picked, changes


def current_plan(c: dict, ctx: dict) -> dict:
    db = get_db()
    plan = db.plans.find_one({"creator_id": c["_id"]}, sort=[("week", -1)])
    if plan is None:
        moves, _ = generate_moves(c, ctx)
        plan = _save(c, 1, moves, [])
    elif len(plan["moves"]) < 3 and all(m["status"] == "open" for m in plan["moves"]):
        # Saved before plans were filled to 3, and not acted on yet: build it again.
        moves, _ = generate_moves(c, ctx, db.plans.find_one({"creator_id": c["_id"], "week": plan["week"] - 1}))
        if len(moves) > len(plan["moves"]):
            plan = _save(c, plan["week"], moves, plan.get("changes") or [])
    return _out(plan)


def next_week(c: dict, ctx: dict) -> dict:
    db = get_db()
    prev = db.plans.find_one({"creator_id": c["_id"]}, sort=[("week", -1)])
    week = (prev["week"] + 1) if prev else 1
    moves, changes = generate_moves(c, ctx, prev)
    if not changes:
        changes = ["New week, fresh moves from your latest numbers."]
    return _out(_save(c, week, moves, changes))


def rebuild(c: dict, ctx: dict, week: int, reason: str) -> dict:
    """This week's moves again, from new numbers. Only for a plan nobody has acted on yet.
    Last week's plan still shapes it (follow-ups, moves already done)."""
    prev = get_db().plans.find_one({"creator_id": c["_id"], "week": week - 1})
    moves, _ = generate_moves(c, ctx, prev)
    return _out(_save(c, week, moves, [reason]))


def _save(c: dict, week: int, moves: list[dict], changes: list[str]) -> dict:
    for i, m in enumerate(moves):
        m["id"] = f"w{week}-{m['kind']}"
        m["order"] = i + 1
    doc = {
        "_id": f"{c['_id']}:w{week}",
        "creator_id": c["_id"],
        "week": week,
        "week_start": week_start(week).isoformat(),
        "moves": moves,
        "changes": changes,
        "generated_at": now_iso(),
    }
    get_db().plans.replace_one({"_id": doc["_id"]}, doc, upsert=True)
    return doc


def _out(plan: dict) -> dict:
    d = dict(plan)
    d["id"] = d.pop("_id")
    d["done_count"] = sum(1 for m in d["moves"] if m["status"] == "done")
    return d


def record_outcome(c: dict, move_id: str, result: str | None, amount: int | None, note: str | None, status: str = "done") -> dict:
    db = get_db()
    plan = db.plans.find_one({"creator_id": c["_id"]}, sort=[("week", -1)])
    if not plan:
        raise KeyError("No plan")
    move = next((m for m in plan["moves"] if m["id"] == move_id), None)
    if not move:
        raise KeyError("No move")
    move["status"] = status
    move["outcome"] = {"result": result, "amount": amount, "note": note, "at": now_iso()} if status == "done" else None
    db.plans.replace_one({"_id": plan["_id"]}, plan)
    if status == "done" and result:
        learning = c.get("learning") or {}
        stats = learning.setdefault(move["kind"], {"wins": 0, "misses": 0})
        if result == "worked":
            stats["wins"] += 1
        elif result == "no":
            stats["misses"] += 1
        update: dict = {"learning": learning}
        # A logged rate becomes the creator's typical rate. Provenance is left
        # unchanged: on the reference profile this is a demo action, not data
        # the creator shared.
        if move["kind"] in ("raise_rate", "lock_rate", "bundle_offer") and result in ("worked", "partly") and amount:
            update["current_rate"] = int(amount)
        db.creators.update_one({"_id": c["_id"]}, {"$set": update})
    return _out(plan)
