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


def _load_dotenv() -> None:
    """Read KEY=VALUE pairs from the repo-root .env without overriding real env vars."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


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
        return bool(self.firebase_project_id)


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
        firebase_project_id=_env("VITE_FIREBASE_PROJECT_ID"),
        demo_today=date.fromisoformat(_env("DEMO_TODAY", "2026-10-08") or "2026-10-08"),
    )


def today() -> date:
    """The demo's 'today'. Fixed so seeded deadlines and reel dates stay consistent."""
    return get_settings().demo_today


def now() -> datetime:
    """Demo date combined with the real time of day (IST)."""
    real = datetime.now(IST)
    d = today()
    return real.replace(year=d.year, month=d.month, day=d.day)


def now_iso() -> str:
    return now().isoformat(timespec="seconds")
