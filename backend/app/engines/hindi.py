"""Hindi copy for the Creator Studio's dynamic text (stage, moves, rate gap).

Built from the same numbers as the English copy, so the EN/हिंदी toggle never
needs a network call. Product names and topic labels stay in English where
creators use them that way (Hinglish).
"""
from __future__ import annotations

from .common import inr, inr_range

LANGS = {
    "hi": "हिंदी", "hinglish": "हिंग्लिश", "en": "अंग्रेज़ी", "ta": "तमिल", "te": "तेलुगु", "kn": "कन्नड़",
    "ml": "मलयालम", "mr": "मराठी", "bn": "बांग्ला", "gu": "गुजराती", "pa": "पंजाबी",
}

STAGES = {
    "pre_launch": ("शुरुआत से पहले", "अभी ऑडियंस नहीं है। जो आप पहले से जानते हैं, वहीं से शुरू करें।"),
    "expert_first": ("पहले हुनर, फिर ऑडियंस", "आपके पास असली हुनर है। अभी उससे कमाएँ; ऑडियंस बाद में आ सकती है।"),
    "starting": ("शुरुआत", "पोस्ट करने की आदत और कमाई का पहला ज़रिया बनाएँ।"),
    "growing": ("बढ़ रहे हैं", "आपकी पहुँच बढ़ रही है। अब इसे नियमित कमाई में बदलें।"),
    "underpriced": ("कमा रहे हैं, पर कम रेट पर", "ब्रैंड्स आपको पैसे देते हैं, पर आपकी पहुँच के हिसाब से कम।"),
    "fair": ("कमा रहे हैं, सही रेट पर", "आपका रेट आपकी पहुँच से मेल खाता है। अब कमाई के और ज़रिए जोड़ें।"),
    "established": ("स्थापित", "बड़े स्तर पर कई ज़रियों से कमाई। इसे सुरक्षित रखें और नियमित ज़रिए बढ़ाएँ।"),
}

EFFORT = {"S": "करीब 15 मिनट", "M": "कुछ घंटे", "L": "कुछ दिन"}


def stage(key: str) -> dict:
    label, line = STAGES[key]
    return {"label": label, "line": line}


def rate_gap_line(gap: float | None, rate: int | None) -> str:
    if not rate:
        return "आपने अभी कोई रेट तय नहीं किया है। यहीं से शुरू करें।"
    if gap and gap > 0:
        return f"हर ब्रैंड रील पर आप करीब {inr(gap)} छोड़ रहे हैं।"
    return "आपका रेट आपकी पहुँच के हिसाब से ठीक है।"


def _fraction(text: str) -> str:
    """'1 of 10' -> '10 में से 1'."""
    parts = text.split(" of ")
    return f"{parts[1]} में से {parts[0]}" if len(parts) == 2 else text


def move(kind: str, **v) -> dict:
    """Hindi title and reason for a move; `v` carries the numbers the English copy used."""
    t = {
        "raise_rate": (
            f"अपना रील रेट {inr_range(v.get('low', 0), v.get('high', 0))} करें",
            f"आपकी रील्स फ़ॉलोअर्स से करीब {v.get('ratio', 0):.0f}x लोगों तक पहुँचती हैं, पर आपका रेट फ़ॉलोअर्स के हिसाब से है।",
        ),
        "double_down": (
            f"इस हफ़्ते 2 और {v.get('topic', '')} पोस्ट करें",
            f"आपकी {v.get('topic', '')} पर सबसे ज़्यादा व्यूज़" + (" और सेव मिलते हैं।" if v.get("most_saved") else " मिलते हैं।"),
        ),
        "content_gap": (
            f"इस हफ़्ते 2 {v.get('topic', '')} पोस्ट करें",
            f"ऐसी रील्स पर आपको बाकी रील्स से {v.get('lift', 0):.1f}x सेव मिले। आपकी भाषा के {_fraction(v.get('supply', ''))} क्रिएटर ही इन्हें पोस्ट करते हैं।",
        ),
        "voiceover": (
            "अगले एडिट में अपनी आवाज़ में वॉइसओवर जोड़ें",
            "सिर्फ़ शो क्लिप्स वाले एडिट पर ब्रैंड्स हिचकते हैं। आपकी आवाज़ उसे ओरिजिनल बनाती है।",
        ),
        "apply_matches": (
            "इन 2 मैच हुए मौकों पर अप्लाई करें",
            f"{v.get('a', '')} और {v.get('b', '')} आपकी ऑडियंस से मेल खाते हैं ({v.get('fa', 0)} और {v.get('fb', 0)}/100)।",
        ),
        "join_collective": (
            f"{v.get('brand', '')} कलेक्टिव में शामिल हों",
            f"{v.get('brand', '')} आप जैसे {v.get('size', 0)} क्रिएटर्स को एक पैक में बुक कर रहा है। आपका हिस्सा आपकी पहुँच पर तय है।",
        ),
        "digital": (
            f"अपना {v.get('title', '')} तैयार करें",
            "एक बार बनाइए, यह हर महीने बिक सकता है। अनुमान आपकी पहुँच और सेव पर आधारित है।",
        ),
        "affiliate": (
            "अपना एफ़िलिएट लिंक सेट करें",
            (f"आपकी {v.get('share', 0)}% कमाई एक ही ज़रिए से आती है। लिंक से हर महीने दोहराने वाली कमाई जुड़ती है।"
             if v.get("share") else "लिंक से हर महीने दोहराने वाली कमाई जुड़ती है, बिना बड़ी फ़ॉलोइंग के।"),
        ),
        "service": (
            "अपने लिंक-इन-बायो से अपनी सर्विस ऑफ़र करें",
            "आपका हुनर अभी कमाई दे सकता है; ऑडियंस बाद में बढ़ सकती है।",
        ),
        "rate_card": (
            f"अपना पहला रेट कार्ड {inr_range(v.get('low', 0), v.get('high', 0))} प्रति रील रखें",
            "जब आप वजह के साथ रेट बताते हैं, तो ब्रैंड्स आपको गंभीरता से लेते हैं।",
        ),
        "lock_rate": (
            f"अपना {inr(v.get('amount', 0))} रेट कार्ड 3 पुराने ब्रैंड्स को भेजें",
            "आपका नया रेट चल गया। जो ब्रैंड्स आपका काम जानते हैं, उनसे इसे पक्का करें।",
        ),
        "bundle_offer": (
            f"रेट घटाने के बजाय {inr_range(v.get('low', 0), v.get('high', 0))} में 2-रील बंडल ऑफ़र करें",
            "जो ब्रैंड एक ऊँचे रेट पर रुकते हैं, वे अक्सर ज़्यादा वैल्यू वाले बंडल पर हाँ कहते हैं।",
        ),
        "series": (
            "इसे तय दिन वाली साप्ताहिक सीरीज़ बनाएँ",
            "इस फ़ॉर्मेट की पिछली पोस्ट्स चलीं। तय दिन दर्शकों को नियमित बनाता है।",
        ),
        "new_hook": (
            "उसी फ़ॉर्मेट पर पहले सेकंड का नया हुक आज़माएँ",
            "फ़ॉर्मेट आपकी ऑडियंस के लिए सही है; शायद शुरुआत में दिक्कत है।",
        ),
    }[kind]
    return {"title": t[0], "reason": t[1]}


def alert(kind: str, **v) -> dict:
    """Hindi text and detail for a pipeline alert."""
    t = {
        "low_offer": (
            f"{v.get('brand', 'यह')} का ऑफ़र आपके सही रेट से {v.get('pct', 0)}% कम है",
            f"{inr(v.get('amount', 0))} ऑफ़र; {v.get('deliverables', '')} के लिए सही रेट {inr(v.get('fair', 0))} है।",
        ),
        "verify_late": (
            f"{v.get('brand', 'ब्रैंड')} आपकी पोस्ट कन्फ़र्म करने में {v.get('days', 0)} दिन देर कर चुका है",
            f"{inr(v.get('amount', 0))} एस्क्रो में सुरक्षित है। हमने याद दिलाया है; {v.get('left', 0)} दिन में यह अपने-आप आपको मिल जाएगा।",
        ),
        "invoice_late": (
            f"{inr(v.get('amount', 0))} का इनवॉइस {v.get('days', 0)} दिन से बकाया है",
            f"{v.get('to', '')} को {v.get('due', '')} तक भुगतान करना था। इनवॉइस के साथ रिमाइंडर भेजें।",
        ),
    }[kind]
    return {"text": t[0], "detail": t[1]}
