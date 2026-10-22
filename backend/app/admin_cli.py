"""Grant or remove the admin role from the server. There is no sign-up path to admin.

    python -m app.admin_cli grant someone@example.com
    python -m app.admin_cli revoke someone@example.com
    python -m app.admin_cli list
    python -m app.admin_cli reset-2fa someone@example.com   # lost phone and recovery codes

The account must already exist (signed up with that email). Granting signs the
account out everywhere, so its next sign-in starts as an admin.
"""
from __future__ import annotations

import sys

from .db import get_db
from .services import auth as au


def main(argv: list[str]) -> int:
    if len(argv) < 1 or argv[0] not in ("grant", "revoke", "list", "reset-2fa") or (argv[0] != "list" and len(argv) != 2):
        print(__doc__.strip())
        return 2
    db = get_db()
    if argv[0] == "list":
        for u in db.users.find({"role": "admin"}, {"email": 1, "name": 1}):
            print(f"{u.get('email')}\t{u.get('name')}")
        return 0
    email = argv[1].strip().lower()
    user = db.users.find_one({"email": email})
    if not user:
        print(f"No account with the email {email}. Sign up first, then grant.")
        return 1
    if argv[0] == "reset-2fa":
        # Lost phone and recovery codes: two-step sign-in is set up again at the next sign-in.
        from .services import totp

        totp.reset(user["_id"])
        au.audit("admin_2fa_reset", user["_id"], user.get("role"), via="cli")
        print(f"{email}: two-step sign-in is off and their sessions were signed out. It's set up again at the next sign-in.")
        return 0
    if argv[0] == "grant":
        # An admin account manages the platform; it doesn't keep a creator or brand profile.
        update = {"role": "admin", "previous_role": user.get("role")}
    else:
        if user.get("role") != "admin":
            print(f"{email} isn't an admin.")
            return 1
        update = {"role": user.get("previous_role") or "creator"}
    db.users.update_one({"_id": user["_id"]}, {"$set": update})
    au.revoke_all(user["_id"])
    au.audit(f"admin_{argv[0]}", user["_id"], update["role"], via="cli")
    print(f"{email}: role is now {update['role']}. Their sessions were signed out.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
