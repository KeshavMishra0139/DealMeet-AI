#!/usr/bin/env python3
"""Load JodiDar's sample data (every record marked source: "synthetic") into the
configured database: MONGODB_URI, or the in-memory one with USE_MOCK_DB=1.

From the repo root, with the API's virtual environment:

    backend/.venv/bin/python scripts/seed.py                    # only if the collections are empty
    backend/.venv/bin/python scripts/seed.py --reset            # replace the sample data (in-memory database)
    backend/.venv/bin/python scripts/seed.py --reset --confirm-reset   # same, on Atlas or any real MongoDB

On a real database --reset removes only records marked synthetic and the seeded demo
accounts; real accounts and their data stay. (Windows: backend\\.venv\\Scripts\\python.exe)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db import DatabaseNotConfigured, db_mode, get_db  # noqa: E402
from app.seed.load import SEEDED, seed_all  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Load JodiDar's sample (synthetic) data.")
    ap.add_argument("--reset", action="store_true", help="replace the sample data even if collections aren't empty")
    ap.add_argument("--confirm-reset", action="store_true", help="required with --reset on a real (non-mock) database")
    args = ap.parse_args(argv)
    try:
        db = get_db()
        mode = db_mode()
    except DatabaseNotConfigured as e:
        print(e)
        return 1
    if mode == "mock":
        print("Note: USE_MOCK_DB=1 is an in-memory database. This data disappears when this script exits;")
        print("the running app seeds its own copy in demo mode (DEMO_MODE=1).")
    if args.reset and mode != "mock" and not args.confirm_reset:
        print(f"--reset on a real database ({mode}) needs --confirm-reset as well. Only sample (synthetic) records are replaced.")
        return 2
    filled = {name: db[name].count_documents({}) for name in SEEDED if db[name].count_documents({})}
    if filled and not args.reset:
        print(f"Collections already have data, so nothing was changed: {filled}. Use --reset to replace the sample data.")
        return 0
    result = seed_all(db, force=True, sandbox=mode == "mock")
    print(f"Seeded sample data into {mode}: {result.get('counts')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
