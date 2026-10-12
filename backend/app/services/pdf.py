"""PDF invoices and media kits (ReportLab). DejaVu Sans is bundled for the
rupee sign and Noto Sans Devanagari for Hindi; both ship with their licenses in
app/assets/fonts."""
from __future__ import annotations

import io
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

FONTS = Path(__file__).resolve().parents[1] / "assets" / "fonts"
VIOLET = colors.HexColor("#6D28D9")
MAGENTA = colors.HexColor("#BE185D")
ORANGE = colors.HexColor("#C2410C")
INK = colors.HexColor("#16132B")
MUTED = colors.HexColor("#5F5980")
LINE = colors.HexColor("#E7E4F0")
SOFT = colors.HexColor("#F3F1FA")

_registered = False


def _fonts() -> tuple[str, str]:
    global _registered
    try:
        if not _registered:
            pdfmetrics.registerFont(TTFont("JD", str(FONTS / "DejaVuSans.ttf")))
            pdfmetrics.registerFont(TTFont("JD-Bold", str(FONTS / "DejaVuSans-Bold.ttf")))
            _registered = True
        return "JD", "JD-Bold"
    except Exception:
        return "Helvetica", "Helvetica-Bold"


def money(v: float) -> str:
    regular, _ = _fonts()
    n = int(round(v))
    s = str(n)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return f"{'₹' if regular == 'JD' else 'Rs. '}{s}"


def _brand_bar(c: Canvas, w: float, h: float) -> None:
    # Signature gradient as three bands across the top.
    band = w / 3
    for i, col in enumerate((VIOLET, MAGENTA, ORANGE)):
        c.setFillColor(col)
        c.rect(i * band, h - 4 * mm, band + 1, 4 * mm, stroke=0, fill=1)


def _wordmark(c: Canvas, x: float, y: float) -> None:
    regular, bold = _fonts()
    c.setStrokeColor(VIOLET)
    c.setLineWidth(1.6)
    c.circle(x + 3 * mm, y + 1.6 * mm, 2.6 * mm)
    c.setStrokeColor(MAGENTA)
    c.circle(x + 5.6 * mm, y + 1.6 * mm, 2.6 * mm)
    c.setFillColor(INK)
    c.setFont(bold, 13)
    c.drawString(x + 10 * mm, y, "JodiDar")
    c.setFillColor(MAGENTA)
    c.drawString(x + 10 * mm + c.stringWidth("JodiDar ", bold, 13), y, "AI")


def invoice_pdf(inv: dict, creator: dict, deal: dict | None) -> bytes:
    regular, bold = _fonts()
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=A4)
    w, h = A4
    _brand_bar(c, w, h)
    _wordmark(c, 18 * mm, h - 22 * mm)
    c.setFont(bold, 22)
    c.setFillColor(INK)
    c.drawRightString(w - 18 * mm, h - 22 * mm, "Invoice")
    c.setFont(regular, 9.5)
    c.setFillColor(MUTED)
    c.drawRightString(w - 18 * mm, h - 28 * mm, f"{inv['number']}  ·  Issued {inv['issued']}")

    y = h - 48 * mm
    c.setFont(bold, 9)
    c.drawString(18 * mm, y, "FROM")
    c.drawString(105 * mm, y, "BILL TO")
    c.setFont(regular, 11)
    c.setFillColor(INK)
    c.drawString(18 * mm, y - 6 * mm, creator.get("name", "Creator"))
    c.drawString(105 * mm, y - 6 * mm, inv["to"])
    c.setFont(regular, 9.5)
    c.setFillColor(MUTED)
    c.drawString(18 * mm, y - 11 * mm, f"@{creator.get('handle', '')}")
    if creator.get("is_reference"):
        c.drawString(18 * mm, y - 16 * mm, "Reference profile (identity withheld)")

    y -= 34 * mm
    c.setFillColor(SOFT)
    c.rect(18 * mm, y - 2 * mm, w - 36 * mm, 9 * mm, stroke=0, fill=1)
    c.setFillColor(MUTED)
    c.setFont(bold, 9)
    c.drawString(22 * mm, y + 1 * mm, "DESCRIPTION")
    c.drawRightString(w - 22 * mm, y + 1 * mm, "AMOUNT")
    y -= 11 * mm
    c.setFont(regular, 11)
    c.setFillColor(INK)
    desc = inv.get("description") or "Creator services"
    if deal and deal.get("listing_title"):
        desc = f"{desc} for {deal['listing_title']}"
    c.drawString(22 * mm, y, desc[:80])
    c.drawRightString(w - 22 * mm, y, money(inv["amount"]))
    c.setStrokeColor(LINE)
    c.line(18 * mm, y - 5 * mm, w - 18 * mm, y - 5 * mm)
    y -= 13 * mm
    c.setFont(bold, 12)
    c.drawString(22 * mm, y, "Total")
    c.drawRightString(w - 22 * mm, y, money(inv["amount"]))

    y -= 20 * mm
    c.setFont(regular, 10)
    c.setFillColor(MUTED)
    status = inv.get("status", "pending")
    lines = []
    stamp = {"paid_simulated": "SIMULATED", "paid": "MARKED PAID" if inv.get("off_platform") else "PAID"}.get(status, status.upper())
    if status == "paid_simulated":
        p = (deal or {}).get("payouts", [{}])[-1]
        lines.append(f"Simulated payout recorded on {(p.get('at') or inv['issued'])[:10]}. No money moved: this is demo data.")
    elif status == "paid" and inv.get("off_platform"):
        lines.append(f"Marked paid by the creator on {(inv.get('paid_at') or inv['issued'])[:10]}.")
    elif inv.get("off_platform"):
        lines.append(f"Due by {inv['due']}. Please pay by UPI or bank transfer.")
    else:
        lines.append("Payable from JodiDar escrow once the brand approves the post (or it is approved automatically).")
    lines.append("Demo invoice generated by JodiDar AI. Not a tax invoice.")
    for ln in lines:
        c.drawString(18 * mm, y, ln)
        y -= 6 * mm

    c.setFillColor(VIOLET if status == "paid" else ORANGE)
    c.roundRect(w - 52 * mm, h - 62 * mm, 34 * mm, 9 * mm, 4, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(bold, 10)
    c.drawCentredString(w - 35 * mm, h - 59 * mm, stamp)
    c.showPage()
    c.save()
    return buf.getvalue()


KIT_TEXT = {
    "en": {
        "title": "Media kit",
        "version": "Version {n}, saved {d}",
        "best": "What performs best",
        "median": "{topic}: median {views} views",
        "rates_estimate": "Rates (priced on reach)",
        "rates_own": "Rates",
        "rates_note_estimate": "Estimated ranges, not promises. Final price depends on deliverables, usage rights and fit with your brand.",
        "rates_note_own": "Rates set by the creator. Final price depends on deliverables and usage rights.",
        "audience": "Audience",
        "book": "Book through {link}. Brands fund escrow before the post goes live.",
        "trust": "Trust {score}/100 {source}.",
        "trust_sim": "partly from sample data",
        "trust_real": "from insights connected via the official API",
        "sources": "Data: L = Live data (official API), S = Self-reported, * = Sample data (illustrative, not the creator's).",
    },
    "hi": {
        "title": "मीडिया किट",
        "version": "वर्शन {n}, {d} को सेव किया",
        "best": "सबसे अच्छा क्या चलता है",
        "median": "{topic}: मीडियन {views} व्यूज़",
        "rates_estimate": "रेट (पहुँच के आधार पर)",
        "rates_own": "रेट",
        "rates_note_estimate": "ये अनुमानित रेंज हैं, वादा नहीं। आखिरी कीमत डिलिवरेबल्स, यूसेज राइट्स और ब्रैंड फ़िट पर निर्भर है।",
        "rates_note_own": "ये रेट क्रिएटर ने तय किए हैं। आखिरी कीमत डिलिवरेबल्स और यूसेज राइट्स पर निर्भर है।",
        "audience": "ऑडियंस",
        "book": "{link} से बुक करें। पोस्ट लाइव होने से पहले ब्रैंड एस्क्रो में पैसे जमा करते हैं।",
        "trust": "ट्रस्ट {score}/100, {source}।",
        "trust_sim": "कुछ हिस्सा सैंपल डेटा से",
        "trust_real": "आधिकारिक API से जुड़े इनसाइट्स से",
        "sources": "डेटा: L = लाइव डेटा (आधिकारिक API), S = खुद बताया गया, * = सैंपल डेटा (उदाहरण के लिए, क्रिएटर का नहीं)।",
    },
}


def _mark(source: str | None) -> str:
    """A short source mark for print, explained in the footer."""
    return {"instagram_api": " L", "youtube_api": " L", "manual": " S", "synthetic": " *"}.get(source or "", "")


def media_kit_pdf(kit: dict) -> bytes:
    regular, bold = _fonts()
    lang = kit.get("lang", "en")
    tx = KIT_TEXT["hi" if lang == "hi" else "en"]
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=A4)
    w, h = A4
    c.setTitle(f"{kit['name']} · {tx['title']}")
    _brand_bar(c, w, h)
    _wordmark(c, 18 * mm, h - 22 * mm)
    c.setFillColor(MUTED)
    ver = kit.get("version")
    head = f"{tx['title']} · {kit['generated_on']}" if not ver else tx["version"].format(n=ver["number"], d=ver["saved_on"])
    text(c, w - 18 * mm, h - 22 * mm, head, 9, align="right")

    y = h - 44 * mm
    c.setFillColor(INK)
    text(c, 18 * mm, y, kit["name"], 24, bold=True)
    c.setFillColor(MUTED)
    text(c, 18 * mm, y - 7 * mm, f"@{kit['handle']} · {kit['niche']} · {', '.join(kit['languages'])}{' · ' + kit['location'] if kit.get('location') else ''}", 11)
    y -= 18 * mm
    c.setFillColor(INK)
    text(c, 18 * mm, y, kit["copy"]["headline"][:90], 13, bold=True)
    y -= 7 * mm
    c.setFillColor(MUTED)
    for line in wrap(kit["copy"]["bio"], 10.5, w - 36 * mm):
        text(c, 18 * mm, y, line, 10.5)
        y -= 5.5 * mm

    tiles = kit.get("stats") or []
    tw = (w - 36 * mm - 3 * 4 * mm) / 4
    for row in range(0, len(tiles), 4):
        y -= 6 * mm
        for i, t in enumerate(tiles[row : row + 4]):
            x = 18 * mm + i * (tw + 4 * mm)
            c.setFillColor(SOFT)
            c.roundRect(x, y - 18 * mm, tw, 20 * mm, 6, stroke=0, fill=1)
            c.setFillColor(MUTED)
            text(c, x + 4 * mm, y - 4 * mm, _fit(t["label"] + _mark(t.get("source") or ("synthetic" if t.get("simulated") else None)), 8, tw - 6 * mm), 8)
            c.setFillColor(INK)
            text(c, x + 4 * mm, y - 13 * mm, t["value"], 15, bold=True)
        y -= 22 * mm
    if tiles:
        y -= 6 * mm

    if kit.get("formats"):
        c.setFillColor(INK)
        text(c, 18 * mm, y, tx["best"], 11, bold=True)
        y -= 6 * mm
        c.setFillColor(MUTED)
        for f in kit["formats"]:
            text(c, 18 * mm, y, tx["median"].format(topic=f["topic"], views=f["views"]) + _mark(f.get("source") or ("synthetic" if f.get("simulated") else None)), 10)
            y -= 5.5 * mm
        y -= 4 * mm

    if kit.get("rates"):
        own = kit.get("rates_kind") == "your_rate"
        c.setFillColor(INK)
        text(c, 18 * mm, y, tx["rates_own" if own else "rates_estimate"], 11, bold=True)
        y -= 7 * mm
        for r in kit["rates"]:
            c.setFillColor(INK)
            text(c, 18 * mm, y, r["label"], 10.5)
            text(c, w - 18 * mm, y, r["value"], 10.5, bold=True, align="right")
            c.setStrokeColor(LINE)
            c.line(18 * mm, y - 2.5 * mm, w - 18 * mm, y - 2.5 * mm)
            y -= 8 * mm
        c.setFillColor(MUTED)
        for line in wrap(tx["rates_note_own" if own else "rates_note_estimate"], 8.5, w - 36 * mm):
            text(c, 18 * mm, y, line, 8.5)
            y -= 4.5 * mm
        y -= 4 * mm

    if kit.get("audience"):
        a = kit["audience"]
        c.setFillColor(INK)
        text(c, 18 * mm, y, tx["audience"] + _mark(a.get("source") or ("synthetic" if a.get("simulated") else None)), 11, bold=True)
        y -= 6 * mm
        c.setFillColor(MUTED)
        for line in wrap(a["line"], 10, w - 36 * mm):
            text(c, 18 * mm, y, line, 10)
            y -= 5 * mm
        y -= 5 * mm

    c.setFillColor(MUTED)
    trust = kit.get("trust")
    footer = [tx["book"].format(link=kit["link"])]
    if trust:
        footer.insert(0, tx["trust"].format(score=trust["score"], source=tx["trust_sim"] if trust.get("simulated") else tx["trust_real"]))
    if kit.get("safety_note"):
        footer.append(kit["safety_note"])
    if kit.get("reference_note"):
        footer.append(kit["reference_note"])
    footer.append(tx["sources"])
    y = max(y, 40 * mm)
    for ln in footer:
        for part in wrap(ln, 9.5, w - 36 * mm):
            text(c, 18 * mm, y, part, 9.5)
            y -= 5 * mm
    c.showPage()
    c.save()
    return buf.getvalue()


# ------------------------------------------------------------------ mixed Latin and Devanagari text
# DejaVu Sans has no Devanagari and Noto Sans Devanagari has no Latin letters, so text is
# drawn in runs, each in the font that has its characters. Devanagari runs are shaped
# with HarfBuzz (uharfbuzz), which ReportLab uses for conjuncts and vowel signs.
_DEVA = re.compile(r"[\u0900-\u097F\u1CD0-\u1CFF\uA8E0-\uA8FF\u200C\u200D]")
_deva_registered: bool | None = None


def _deva_fonts() -> tuple[str, str] | None:
    global _deva_registered
    if _deva_registered is None:
        try:
            pdfmetrics.registerFont(TTFont("JD-Deva", str(FONTS / "NotoSansDevanagari-Regular.ttf"), shapable=True))
            pdfmetrics.registerFont(TTFont("JD-Deva-Bold", str(FONTS / "NotoSansDevanagari-Bold.ttf"), shapable=True))
            _deva_registered = True
        except Exception:
            _deva_registered = False
    return ("JD-Deva", "JD-Deva-Bold") if _deva_registered else None


def can_shape() -> bool:
    """True when Devanagari can be drawn correctly: the font is bundled and HarfBuzz is installed."""
    fonts = _deva_fonts()
    return bool(fonts and pdfmetrics.getFont(fonts[0]).shapable)


def _runs(s: str) -> list[tuple[bool, str]]:
    """Split into (is_devanagari, chunk). Spaces stay with the run they're in."""
    out: list[tuple[bool, str]] = []
    for ch in s:
        deva = bool(_DEVA.match(ch)) if not ch.isspace() else (out[-1][0] if out else False)
        if out and out[-1][0] == deva:
            out[-1] = (deva, out[-1][1] + ch)
        else:
            out.append((deva, ch))
    return out


def _font_for(deva: bool, bold: bool) -> str:
    regular, b = _fonts()
    if deva and (fonts := _deva_fonts()):
        return fonts[1] if bold else fonts[0]
    return b if bold else regular


def _width(chunk: str, font: str, size: float, shaping: bool) -> float:
    if shaping:
        from reportlab.pdfbase.ttfonts import ShapedStr, shapeStr

        shaped = shapeStr(chunk, font, size)
        if isinstance(shaped, ShapedStr):  # unchanged text comes back as a plain str
            return sum(g.x_advance for g in shaped.__shapeData__) * size / 1000
    return pdfmetrics.stringWidth(chunk, font, size)


def text_width(s: str, size: float, bold: bool = False) -> float:
    return sum(_width(chunk, _font_for(deva, bold), size, deva and can_shape()) for deva, chunk in _runs(s))


def text(c: Canvas, x: float, y: float, s: str, size: float, bold: bool = False, align: str = "left") -> None:
    """Draw a line that may mix Latin and Devanagari."""
    if align == "right":
        x -= text_width(s, size, bold)
    for deva, chunk in _runs(s):
        font = _font_for(deva, bold)
        c.setFont(font, size)
        shaping = deva and can_shape()
        if shaping:
            # canvas.drawString(shaping=True) only shapes when the optional rlbidi package is
            # installed, so shape here and draw through a text object, which applies the
            # HarfBuzz glyph positions.
            from reportlab.pdfbase.ttfonts import shapeStr

            t = c.beginText(x, y)
            t.setFont(font, size)
            t.textLine(shapeStr(chunk, font, size))
            c.drawText(t)
        else:
            c.drawString(x, y, chunk)
        x += _width(chunk, font, size, shaping)


def wrap(s: str, size: float, width: float, bold: bool = False) -> list[str]:
    words, lines, cur = s.split(), [], ""
    for wd in words:
        trial = f"{cur} {wd}".strip()
        if text_width(trial, size, bold) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def _fit(s: str, size: float, width: float) -> str:
    """Trim a label to fit a tile."""
    while s and text_width(s, size) > width:
        s = s[:-2].rstrip() + "…"
    return s
