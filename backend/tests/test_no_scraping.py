"""JodiDar AI only uses data a creator connects via official OAuth, types or uploads,
plus seeded mock data. This test fails if scraping tools or direct page fetches
of social platforms appear anywhere in the app code."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN = [ROOT / "backend" / "app", ROOT / "frontend" / "src", ROOT / "scripts"]
EXTS = {".py", ".ts", ".tsx", ".js", ".mjs"}

BANNED_IMPORTS = re.compile(
    r"\b(BeautifulSoup|bs4|selenium|scrapy|instaloader|instagrapi|requests_html|puppeteer|cheerio|playwright|snscrape|yt_dlp|youtube_dl)\b"
)
# An HTTP call aimed at a social platform's public pages (official APIs are mocked).
PLATFORM_FETCH = re.compile(
    r"(get|post|fetch|urlopen|request|Request)\s*\(\s*[\"'`]https?://(www\.)?(instagram|youtube|facebook|tiktok|x|twitter)\.com",
    re.IGNORECASE,
)


def _files():
    for base in SCAN:
        for p in base.rglob("*"):
            if p.suffix in EXTS and "node_modules" not in p.parts:
                yield p


def test_no_scraping_libraries():
    hits = []
    for p in _files():
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if BANNED_IMPORTS.search(line):
                hits.append(f"{p.relative_to(ROOT)}:{i}: {line.strip()[:100]}")
    assert not hits, "Scraping tooling found:\n" + "\n".join(hits)


def test_no_direct_platform_fetches():
    hits = []
    for p in _files():
        text = p.read_text(encoding="utf-8", errors="ignore")
        for m in PLATFORM_FETCH.finditer(text):
            hits.append(f"{p.relative_to(ROOT)}: {m.group(0)}")
    assert not hits, "Direct platform fetches found:\n" + "\n".join(hits)


def test_qa_screenshots_only_target_localhost():
    qa = ROOT / "qa" / "screenshots.mjs"
    if qa.exists():
        text = qa.read_text(encoding="utf-8")
        urls = re.findall(r"https?://[^\s\"'`]+", text)
        assert all(re.match(r"https?://(localhost|127\.0\.0\.1)", u) for u in urls), urls
