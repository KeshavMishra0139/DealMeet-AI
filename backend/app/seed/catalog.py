"""Reference tables shared by the seed generator and the engines."""
from __future__ import annotations

# cpm: seeded rupees per 1,000 views for the niche (range 100-200).
# ss_bench: typical (saves + shares) / views for the niche.
# family: niches that collaborate or bundle well together.
NICHES: dict[str, dict] = {
    "anime_edits": {"label": "Anime edits", "cpm": 120, "ss_bench": 0.022, "family": "anime_gaming"},
    "gaming": {"label": "Gaming", "cpm": 130, "ss_bench": 0.018, "family": "anime_gaming"},
    "food": {"label": "Food and cooking", "cpm": 140, "ss_bench": 0.035, "family": "food_home"},
    "finance": {"label": "Personal finance", "cpm": 200, "ss_bench": 0.040, "family": "finance_edu"},
    "tech": {"label": "Tech and coding", "cpm": 180, "ss_bench": 0.035, "family": "finance_edu"},
    "fitness": {"label": "Fitness and yoga", "cpm": 150, "ss_bench": 0.030, "family": "wellness"},
    "fashion": {"label": "Fashion", "cpm": 160, "ss_bench": 0.020, "family": "style"},
    "beauty": {"label": "Beauty and skincare", "cpm": 170, "ss_bench": 0.025, "family": "style"},
    "comedy": {"label": "Comedy", "cpm": 110, "ss_bench": 0.020, "family": "entertainment"},
    "education": {"label": "Education", "cpm": 170, "ss_bench": 0.045, "family": "finance_edu"},
    "travel": {"label": "Travel", "cpm": 160, "ss_bench": 0.030, "family": "lifestyle"},
    "parenting": {"label": "Parenting", "cpm": 160, "ss_bench": 0.035, "family": "food_home"},
}

LANGS: dict[str, dict] = {
    "hi": {"label": "Hindi", "native": "हिंदी"},
    "en": {"label": "English", "native": "English"},
    "hinglish": {"label": "Hinglish", "native": "Hinglish"},
    "ta": {"label": "Tamil", "native": "தமிழ்"},
    "te": {"label": "Telugu", "native": "తెలుగు"},
    "kn": {"label": "Kannada", "native": "ಕನ್ನಡ"},
    "ml": {"label": "Malayalam", "native": "മലയാളം"},
    "bn": {"label": "Bengali", "native": "বাংলা"},
    "mr": {"label": "Marathi", "native": "मराठी"},
    "gu": {"label": "Gujarati", "native": "ગુજરાતી"},
}

# city -> (state, region)
CITIES: dict[str, tuple[str, str]] = {
    "Mumbai": ("Maharashtra", "West"),
    "Pune": ("Maharashtra", "West"),
    "Nagpur": ("Maharashtra", "Central"),
    "Ahmedabad": ("Gujarat", "West"),
    "Surat": ("Gujarat", "West"),
    "Delhi": ("Delhi", "North"),
    "Gurugram": ("Haryana", "North"),
    "Noida": ("Uttar Pradesh", "North"),
    "Lucknow": ("Uttar Pradesh", "North"),
    "Jaipur": ("Rajasthan", "North"),
    "Chandigarh": ("Chandigarh", "North"),
    "Patna": ("Bihar", "East"),
    "Kolkata": ("West Bengal", "East"),
    "Guwahati": ("Assam", "Northeast"),
    "Indore": ("Madhya Pradesh", "Central"),
    "Bhopal": ("Madhya Pradesh", "Central"),
    "Bengaluru": ("Karnataka", "South"),
    "Mysuru": ("Karnataka", "South"),
    "Chennai": ("Tamil Nadu", "South"),
    "Madurai": ("Tamil Nadu", "South"),
    "Coimbatore": ("Tamil Nadu", "South"),
    "Tiruchirappalli": ("Tamil Nadu", "South"),
    "Salem": ("Tamil Nadu", "South"),
    "Hyderabad": ("Telangana", "South"),
    "Vijayawada": ("Andhra Pradesh", "South"),
    "Visakhapatnam": ("Andhra Pradesh", "South"),
    "Kochi": ("Kerala", "South"),
    "Kozhikode": ("Kerala", "South"),
    "Thiruvananthapuram": ("Kerala", "South"),
}

# Nearby audience cities by primary language, used to shape audience demographics.
LANG_CITIES: dict[str, list[str]] = {
    "ta": ["Chennai", "Madurai", "Coimbatore", "Tiruchirappalli", "Salem", "Bengaluru"],
    "te": ["Hyderabad", "Vijayawada", "Visakhapatnam", "Bengaluru", "Chennai"],
    "kn": ["Bengaluru", "Mysuru", "Hyderabad", "Pune"],
    "ml": ["Kochi", "Thiruvananthapuram", "Kozhikode", "Bengaluru"],
    "bn": ["Kolkata", "Guwahati", "Delhi", "Bengaluru"],
    "mr": ["Pune", "Mumbai", "Nagpur"],
    "gu": ["Ahmedabad", "Surat", "Mumbai"],
    "hi": ["Delhi", "Lucknow", "Jaipur", "Patna", "Indore", "Bhopal", "Mumbai"],
    "hinglish": ["Delhi", "Mumbai", "Bengaluru", "Pune", "Gurugram", "Lucknow"],
    "en": ["Bengaluru", "Mumbai", "Delhi", "Pune", "Hyderabad", "Chennai"],
}

AGE_BUCKETS = ["13-17", "18-24", "25-34", "35-44", "45+"]

STAGES = [
    {"id": "zero", "label": "0 followers", "min": 0, "max": 0},
    {"id": "under_1k", "label": "Under 1K", "min": 1, "max": 999},
    {"id": "1k_10k", "label": "1K to 10K", "min": 1_000, "max": 9_999},
    {"id": "10k_100k", "label": "10K to 100K", "min": 10_000, "max": 99_999},
    {"id": "100k_plus", "label": "100K+", "min": 100_000, "max": 10**12},
]

INCOME_TYPES = {
    "brand": "Brand collaborations",
    "services": "Services",
    "digital": "Digital products",
    "affiliate": "Affiliate",
    "pr": "PR and events",
    "collective": "Collective deals",
    "page": "Page shoutouts",
}

FORMATS = {
    "reels": "Reels",
    "shorts": "Shorts",
    "long": "Long-form video",
    "carousel": "Carousels",
    "stories": "Stories",
    "live": "Live streams",
}

# Short captions in the creator's own language and script, by niche. Used for
# fictional seeded creators only; the reference profile has no captions on file.
CAPTIONS: dict[tuple[str, str], list[str]] = {
    ("food", "ta"): [
        "10 நிமிடத்தில் ரவா உப்புமா",
        "ராகி தோசை - காலை டிபன்",
        "மதுரை ஸ்டைல் காரக் குழம்பு",
        "வீட்டிலேயே தேங்காய் சட்னி",
        "தக்காளி ரசம் எளிய முறை",
        "சேமியா பாயசம்",
        "அம்மா ஸ்டைல் சாம்பார்",
        "மொறுமொறு வடை செய்வது எப்படி",
    ],
    ("food", "te"): [
        "10 నిమిషాల్లో ఉప్మా",
        "అమ్మ చేతి పప్పు",
        "ఇంట్లోనే గోంగూర పచ్చడి",
        "కరకరలాడే దోసె",
        "సులభమైన టమాటా రసం",
    ],
    ("food", "kn"): [
        "ಮನೆಯಲ್ಲೇ ಬಿಸಿಬೇಳೆ ಬಾತ್",
        "10 ನಿಮಿಷದಲ್ಲಿ ಉಪ್ಪಿಟ್ಟು",
        "ರಾಗಿ ಮುದ್ದೆ ಸುಲಭ ವಿಧಾನ",
        "ಮಸಾಲೆ ದೋಸೆ ಮನೆಯಲ್ಲೇ",
    ],
    ("food", "ml"): [
        "നാടൻ പുട്ടും കടലയും",
        "10 മിനിറ്റിൽ ഉപ്പുമാവ്",
        "അമ്മയുടെ സാമ്പാർ",
        "കേരള സ്റ്റൈൽ അവിയൽ",
    ],
    ("food", "hi"): [
        "10 मिनट में पोहा",
        "घर का बना राजमा चावल",
        "मसाला चाय की सही रेसिपी",
        "ढाबा स्टाइल दाल तड़का",
    ],
    ("food", "bn"): [
        "১০ মিনিটে লুচি আলুর দম",
        "মায়ের হাতের মাছের ঝোল",
        "সহজ ডিমের কারি",
    ],
    ("food", "mr"): ["१० मिनिटांत पोहे", "घरगुती मिसळ पाव"],
    ("anime_edits", "hinglish"): [
        "Ye fight scene dekh ke goosebumps aa gaye",
        "Slow-mo edit, headphones laga ke dekho",
        "Is character ka sabse best moment",
    ],
    ("anime_edits", "en"): [
        "Frame-by-frame beat sync edit",
        "Manga panel to anime transition",
        "Character tribute edit, part 3",
    ],
    ("anime_edits", "hi"): ["इस सीन पर पूरा एडिट", "दोस्ती पर सबसे इमोशनल एडिट"],
    ("anime_edits", "mr"): ["हा सीन पाहून अंगावर काटा आला", "मैत्रीवर खास एडिट"],
    ("gaming", "hinglish"): [
        "Last zone mein 1v3 clutch",
        "Rank push stream ke highlights",
        "Is setting se aim better hoga",
    ],
    ("gaming", "en"): ["Speedrun route, explained", "Best budget setup for mobile gaming"],
    ("gaming", "hi"): ["आज का सबसे अच्छा क्लच", "नए खिलाड़ियों के लिए 5 टिप्स"],
    ("gaming", "gu"): ["આજનો શ્રેષ્ઠ ક્લચ", "નવા ખેલાડીઓ માટે ટીપ્સ"],
    ("finance", "hinglish"): [
        "SIP vs FD, simple samjho",
        "Tax bachane ke 3 legal tareeke",
        "Pehli salary ka budget kaise banaye",
    ],
    ("finance", "hi"): ["इमरजेंसी फंड क्यों ज़रूरी है", "क्रेडिट स्कोर कैसे सुधारें"],
    ("finance", "en"): ["ITR filing in 5 steps", "Old vs new tax regime, explained"],
    ("finance", "bn"): ["সঞ্চয়ের সহজ নিয়ম", "প্রথম বেতনের বাজেট"],
    ("finance", "ta"): ["வருமான வரி எளிய விளக்கம்", "சேமிப்பு திட்டம் தொடங்குவது எப்படி"],
    ("tech", "hinglish"): ["10 minute mein to-do app banao", "DSA roadmap placements ke liye"],
    ("tech", "en"): ["Build a portfolio site in one evening", "What AI tools actually save time"],
    ("tech", "te"): ["కోడింగ్ ఎలా మొదలు పెట్టాలి", "ఇంటర్వ్యూ కోసం 5 టిప్స్"],
    ("tech", "mr"): ["कोडिंग सुरुवात कशी करावी", "पहिली वेबसाइट बनवा"],
    ("fitness", "hi"): ["सुबह 10 मिनट योग", "घर पर पूरा वर्कआउट"],
    ("fitness", "hinglish"): ["Desi diet for fat loss", "Gym mein pehla hafta"],
    ("fitness", "ta"): ["சூரிய நமஸ்காரம் சரியான முறை", "40 வயதுக்கு மேல் உடற்பயிற்சி"],
    ("fitness", "mr"): ["घरी करता येणारा व्यायाम", "सकाळचा योग"],
    ("fashion", "hinglish"): ["Festive look under 999", "Ek kurta, teen looks"],
    ("fashion", "ta"): ["பட்டுப் புடவை கட்டும் முறை", "தீபாவளி லுக்"],
    ("fashion", "en"): ["Capsule wardrobe for college", "Office wear on a budget"],
    ("beauty", "bn"): ["বর্ষায় ত্বকের যত্ন", "সহজ মেকআপ"],
    ("beauty", "en"): ["Monsoon skincare routine", "Sunscreen myths, sorted"],
    ("comedy", "hinglish"): ["Jab mummy ko WiFi password chahiye", "Office meeting be like"],
    ("comedy", "ta"): ["சென்னை ஆட்டோ அனுபவம்", "அம்மா vs மொபைல்"],
    ("education", "hi"): ["कक्षा 10 गणित की आसान ट्रिक", "प्रतिशत निकालने का तरीका"],
    ("education", "en"): ["Current affairs in 60 seconds", "How to read the newspaper for exams"],
    ("education", "ml"): ["പരീക്ഷയ്ക്ക് എങ്ങനെ പഠിക്കാം", "ഇന്നത്തെ വാർത്തകൾ"],
    ("travel", "en"): ["Weekend trail under 5,000 rupees", "Homestays worth the climb"],
    ("travel", "hi"): ["पहाड़ों में सस्ता सफर", "होमस्टे कैसे चुनें"],
    ("parenting", "ta"): ["குழந்தைகளுக்கு சத்தான ஸ்நாக்ஸ்", "லஞ்ச் பாக்ஸ் ஐடியாக்கள்"],
    ("parenting", "en"): ["Toddler lunchbox ideas", "Screen time rules that work"],
}

TOPICS: dict[str, list[str]] = {
    "anime_edits": ["Beat-sync fight edit", "Emotional slow-mo edit", "Meme edit", "Manga-panel transition", "Character tribute"],
    "gaming": ["Clutch highlights", "Settings guide", "Stream recap", "Beginner tips", "Budget setup"],
    "food": ["Quick breakfast", "Gravy and curry", "Chutney and sides", "Sweets", "Rice dishes", "Snacks"],
    "finance": ["Tax basics", "Saving and SIPs", "Budgeting", "Credit and loans"],
    "tech": ["Build-along", "Career advice", "Tool reviews", "Interview prep"],
    "fitness": ["Home workout", "Yoga routine", "Diet basics", "Form check"],
    "fashion": ["Festive look", "Budget styling", "Saree and drapes", "Wardrobe basics"],
    "beauty": ["Skincare routine", "Makeup basics", "Product myths"],
    "comedy": ["Family skits", "Office skits", "City life"],
    "education": ["Maths tricks", "Current affairs", "Exam strategy"],
    "travel": ["Budget trips", "Homestays", "Trail guides"],
    "parenting": ["Lunchbox ideas", "Routines", "Kids nutrition"],
}
