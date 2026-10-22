"""Runtime settings. Every external service is optional; the demo runs offline."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CACHE_DIR = BACKEND / ".cache"
IST = timezone(timedelta(hours=5, minutes=30))


def _read_text_any(path: Path) -> str:
    """Text of a file saved as UTF-8 (with or without a BOM) or as UTF-16.

    Windows PowerShell 5.1 writes UTF-16 for `echo X > .env`, and older Notepad
    adds a UTF-8 BOM; both should just work.
    """
    data = path.read_bytes()
    try:
        if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
            return data.decode("utf-16")
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"{path} isn't UTF-8 or UTF-16 text. Open it in a text editor and save it as UTF-8.") from exc


def _load_dotenv(path: Path | None = None) -> None:
    """Read KEY=VALUE pairs from the repo-root .env without overriding real env vars."""
    path = path or ROOT / ".env"
    if not path.exists():
        return
    for raw in _read_text_any(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _search_index() -> str:
    """ATLAS_SEARCH_INDEX unset: "brands_search". Set to empty or "off": disabled."""
    v = os.getenv("ATLAS_SEARCH_INDEX")
    if v is None:
        return "brands_search"
    return "" if v.strip().lower() in ("", "off", "none") else v.strip()


def _flag(name: str) -> bool:
    return (_env(name, "0") or "0").strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    mongodb_uri: str | None
    mongodb_db: str
    ai_api_key: str | None
    ai_model: str | None
    razorpay_key_id: str | None
    razorpay_key_secret: str | None
    firebase_project_id: str | None
    demo_today: date
    # On a shared URL, put the demo data back to its seeded state every N minutes (0 = never).
    demo_reset_minutes: int = 0
    # Persona sign-in, seeded data and the reset button exist only in demo mode (DEMO_MODE=1).
    demo_mode: bool = False
    # A seeded "Demo admin" persona for local walkthroughs of the admin console. Only with
    # DEMO_MODE=1 and DEMO_ADMIN=1 on a demo that doesn't reset itself (not a shared URL).
    demo_admin: bool = False
    session_hours: int = 72
    razorpay_webhook_secret: str | None = None
    # In-memory mongomock instead of MONGODB_URI (tests and the local demo). Never a silent fallback.
    use_mock_db: bool = False
    firebase_service_account_json: str | None = None
    google_application_credentials: str | None = None
    youtube_api_key: str | None = None
    # OpenRouter (https://openrouter.ai): used for AI copy when ANTHROPIC_API_KEY isn't set.
    # AI_MODEL is then OpenRouter's model id, e.g. an Anthropic model listed as "anthropic/...".
    openrouter_api_key: str | None = None
    token_enc_key: str | None = None
    ig_app_id: str | None = None
    ig_app_secret: str | None = None
    ig_redirect_uri: str | None = None
    frontend_url: str | None = None
    # Who runs this site, shown on /privacy and /terms (DPDP Act: a contact for questions
    # and a grievance officer). Unset fields show as "not published yet".
    legal_name: str | None = None  # the business or person operating the site
    legal_address: str | None = None
    contact_email: str | None = None
    grievance_name: str | None = None
    grievance_email: str | None = None
    legal_city: str | None = None  # courts for disputes under the Terms
    # Meta Graph API version for graph.instagram.com calls, and the window for audience
    # demographics. Check both against Meta's changelog; they're settings for that reason.
    ig_graph_version: str = "v25.0"
    ig_demographics_timeframe: str = "this_month"
    # Atlas Search index on brands, used by the brand directory on Atlas. Empty: plain regex search.
    atlas_search_index: str = "brands_search"
    # Protected computation (services/tee.py). No endpoint: "not_configured", and the
    # documented fallback runs. With one, attestation must verify against the trust root
    # and the measurement policy below, or nothing is sent to it.
    tee_endpoint: str | None = None
    tee_trust_root: str | None = None  # PEM text, or a path to the PEM file
    tee_measurements: str | None = None  # JSON: {"0": "<PCR0 hex>", "1": "...", "2": "..."}
    tee_max_age_s: int = 300
    # Outgoing email over SMTP (services/email.py): any provider with an SMTP endpoint.
    # Without a host and sender, nothing is sent and callers say email isn't set up.
    smtp_host: str | None = None
    smtp_port: int = 587  # 587: STARTTLS; 465: TLS from the start
    smtp_user: str | None = None
    smtp_password: str | None = None
    email_from: str | None = None  # e.g. "DealMeet AI <hello@yourdomain.com>"
    # Upgrade to TLS on ports other than 465. Only a local mail catcher (Mailpit) needs it off.
    smtp_starttls: bool = True

    @property
    def ai_provider(self) -> str | None:
        """"anthropic" (direct, ANTHROPIC_API_KEY), else "openrouter" (OPENROUTER_API_KEY), else None."""
        if not self.ai_model:
            return None
        return "anthropic" if self.ai_api_key else "openrouter" if self.openrouter_api_key else None

    @property
    def has_ai(self) -> bool:
        return self.ai_provider is not None

    @property
    def has_razorpay(self) -> bool:
        return bool(
            self.razorpay_key_id
            and self.razorpay_key_secret
            and self.razorpay_key_id.startswith("rzp_test_")
        )

    @property
    def has_firebase(self) -> bool:
        """Server-side Firebase token checks need a service account."""
        return bool(self.firebase_service_account_json or self.google_application_credentials)


@lru_cache
def get_settings() -> Settings:
    _load_dotenv()
    return Settings(
        mongodb_uri=_env("MONGODB_URI"),
        mongodb_db=_env("MONGODB_DB", "jodidar") or "jodidar",
        ai_api_key=_env("ANTHROPIC_API_KEY"),
        ai_model=_env("AI_MODEL"),
        razorpay_key_id=_env("RAZORPAY_KEY_ID"),
        razorpay_key_secret=_env("RAZORPAY_KEY_SECRET"),
        firebase_project_id=_env("FIREBASE_PROJECT_ID") or _env("VITE_FIREBASE_PROJECT_ID"),
        demo_today=date.fromisoformat(_env("DEMO_TODAY", "2026-10-08") or "2026-10-08"),
        demo_reset_minutes=int(_env("DEMO_RESET_MINUTES", "0") or 0),
        demo_mode=_flag("DEMO_MODE"),
        demo_admin=_flag("DEMO_MODE") and _flag("DEMO_ADMIN") and int(_env("DEMO_RESET_MINUTES", "0") or 0) == 0,
        session_hours=int(_env("SESSION_HOURS", "72") or 72),
        razorpay_webhook_secret=_env("RAZORPAY_WEBHOOK_SECRET"),
        use_mock_db=_flag("USE_MOCK_DB"),
        firebase_service_account_json=_env("FIREBASE_SERVICE_ACCOUNT_JSON"),
        google_application_credentials=_env("GOOGLE_APPLICATION_CREDENTIALS"),
        youtube_api_key=_env("YOUTUBE_API_KEY"),
        openrouter_api_key=_env("OPENROUTER_API_KEY"),
        token_enc_key=_env("TOKEN_ENC_KEY"),
        ig_app_id=_env("IG_APP_ID"),
        ig_app_secret=_env("IG_APP_SECRET"),
        ig_redirect_uri=_env("IG_REDIRECT_URI"),
        frontend_url=(_env("FRONTEND_URL") or "").rstrip("/") or None,
        legal_name=_env("LEGAL_NAME"),
        legal_address=_env("LEGAL_ADDRESS"),
        contact_email=_env("CONTACT_EMAIL"),
        grievance_name=_env("GRIEVANCE_OFFICER_NAME"),
        grievance_email=_env("GRIEVANCE_OFFICER_EMAIL"),
        legal_city=_env("LEGAL_CITY"),
        ig_graph_version=_env("IG_GRAPH_VERSION", "v25.0") or "v25.0",
        ig_demographics_timeframe=_env("IG_DEMOGRAPHICS_TIMEFRAME", "this_month") or "this_month",
        atlas_search_index=_search_index(),
        tee_endpoint=(_env("TEE_ENDPOINT") or "").rstrip("/") or None,
        tee_trust_root=_env("TEE_TRUST_ROOT"),
        tee_measurements=_env("TEE_MEASUREMENTS"),
        tee_max_age_s=int(_env("TEE_ATTESTATION_MAX_AGE_S", "300") or 300),
        smtp_host=_env("SMTP_HOST"),
        smtp_port=int(_env("SMTP_PORT", "587") or 587),
        smtp_user=_env("SMTP_USER"),
        smtp_password=_env("SMTP_PASSWORD"),
        email_from=_env("EMAIL_FROM"),
        smtp_starttls=(_env("SMTP_STARTTLS", "1") or "1").strip().lower() in ("1", "true", "yes", "on"),
    )


def today() -> date:
    """In demo mode, the demo's fixed 'today', so seeded deadlines and reel dates stay
    consistent. On a live site (DEMO_MODE=0), the real date in India."""
    s = get_settings()
    return s.demo_today if s.demo_mode else datetime.now(IST).date()


_BOOT_DATE = datetime.now(IST).date()


def now() -> datetime:
    """Demo date combined with the real time of day (IST). Days that pass while the
    server runs still count, so timestamps keep increasing after midnight."""
    real = datetime.now(IST)
    if not get_settings().demo_mode:
        return real  # a live site runs on the real clock
    d = today() + (real.date() - _BOOT_DATE)
    return real.replace(year=d.year, month=d.month, day=d.day)


def now_iso() -> str:
    return now().isoformat(timespec="seconds")
