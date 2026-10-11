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
    session_hours: int = 72
    razorpay_webhook_secret: str | None = None
    # In-memory mongomock instead of MONGODB_URI (tests and the local demo). Never a silent fallback.
    use_mock_db: bool = False
    firebase_service_account_json: str | None = None
    google_application_credentials: str | None = None
    youtube_api_key: str | None = None

    @property
    def has_ai(self) -> bool:
        return bool(self.ai_api_key and self.ai_model)

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
        session_hours=int(_env("SESSION_HOURS", "72") or 72),
        razorpay_webhook_secret=_env("RAZORPAY_WEBHOOK_SECRET"),
        use_mock_db=_flag("USE_MOCK_DB"),
        firebase_service_account_json=_env("FIREBASE_SERVICE_ACCOUNT_JSON"),
        google_application_credentials=_env("GOOGLE_APPLICATION_CREDENTIALS"),
        youtube_api_key=_env("YOUTUBE_API_KEY"),
    )


def today() -> date:
    """The demo's 'today'. Fixed so seeded deadlines and reel dates stay consistent."""
    return get_settings().demo_today


_BOOT_DATE = datetime.now(IST).date()


def now() -> datetime:
    """Demo date combined with the real time of day (IST). Days that pass while the
    server runs still count, so timestamps keep increasing after midnight."""
    real = datetime.now(IST)
    d = today() + (real.date() - _BOOT_DATE)
    return real.replace(year=d.year, month=d.month, day=d.day)


def now_iso() -> str:
    return now().isoformat(timespec="seconds")
