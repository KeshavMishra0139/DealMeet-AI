"""A brand's organisation profile, owned by the brand account: name, address (slug),
category, website, description and a private contact."""
from __future__ import annotations

import re
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator

from ..config import now_iso
from ..db import get_db
from . import auth as au

SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$")
RESERVED = {"new", "admin", "api", "brand", "brands", "search", "claim", "settings", "edit"}


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40].strip("-")
    return s if len(s) >= 3 else (s + "-brand")[:40]


def unique_slug(name: str, taken: set[str] | None = None, exclude_id: str | None = None) -> str:
    base = slugify(name)
    if base in RESERVED:
        base = f"{base}-brand"
    db = get_db()

    def used(s: str) -> bool:
        if taken is not None:
            return s in taken
        q: dict = {"slug": s}
        if exclude_id:
            q["_id"] = {"$ne": exclude_id}
        return db.brands.count_documents(q) > 0

    slug, n = base, 1
    while used(slug):
        n += 1
        slug = f"{base[: 40 - len(str(n)) - 1]}-{n}"
    return slug


def clean_website(v: str | None) -> str | None:
    if v in (None, ""):
        return None
    v = v.strip()
    if not re.match(r"^https?://[^\s/$.?#][^\s]*\.[^\s]{2,}$", v, re.I):
        raise ValueError("Enter a full website address starting with https://")
    return v


class Contact(BaseModel):
    name: str | None = Field(default=None, max_length=60)
    email: str | None = Field(default=None, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=20, pattern=r"^\+?[0-9 ()-]{6,20}$")


class OrgIn(BaseModel):
    """Only what's sent changes."""

    name: str | None = Field(default=None, min_length=2, max_length=60)
    slug: str | None = Field(default=None, min_length=3, max_length=40)
    category: str | None = Field(default=None, min_length=2, max_length=60)
    website: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=400)
    contact: Contact | None = None
    public_handles: dict[Literal["instagram", "youtube"], str | None] | None = None

    @field_validator("public_handles")
    @classmethod
    def _handles(cls, v: dict | None) -> dict | None:
        if v is None:
            return v
        out = {}
        for k, h in v.items():
            if h in (None, ""):
                continue
            h = h.strip()
            if not re.match(r"^@?[A-Za-z0-9._-]{2,40}$", h):
                raise ValueError("Enter a public handle like @brandname")
            out[k] = h if h.startswith("@") else f"@{h}"
        return out

    @field_validator("website")
    @classmethod
    def _site(cls, v: str | None) -> str | None:
        return clean_website(v)


def view(b: dict, owner: bool) -> dict:
    """The organisation profile. The contact is the owner's only."""
    d = {
        "id": b["_id"],
        "name": b["name"],
        "slug": b.get("slug"),
        "category": b.get("category"),
        "website": b.get("website"),
        "description": b.get("description") or "",
        "hue": b.get("hue", 260),
        "verified": bool(b.get("verified")),
        "source": b.get("source"),
        "public_handles": b.get("public_handles") or {},
    }
    if owner:
        d["contact"] = b.get("contact") or {"name": None, "email": None, "phone": None}
        d["updated_at"] = b.get("updated_at")
    return d


def update(b: dict, body: OrgIn, user: dict) -> dict:
    db = get_db()
    ch = body.model_dump(exclude_unset=True)
    if "slug" in ch:
        slug = (ch["slug"] or "").strip().lower()
        if not SLUG.match(slug) or "--" in slug:
            raise HTTPException(422, "Use 3 to 40 lowercase letters, numbers and single hyphens for the address.")
        if slug in RESERVED:
            raise HTTPException(422, "That address is reserved. Pick another.")
        if db.brands.count_documents({"slug": slug, "_id": {"$ne": b["_id"]}}):
            raise HTTPException(409, "That address is taken. Pick another.")
        ch["slug"] = slug
    for k in ("name", "category", "description"):
        if ch.get(k) is not None:
            ch[k] = ch[k].strip()
    if "website" in ch and not ch["website"]:
        ch["website"] = None
    if ch.get("contact") is not None:
        ch["contact"] = {k: (v.strip() if isinstance(v, str) and v.strip() else None) for k, v in ch["contact"].items()}
    if ch:
        ch["updated_at"] = now_iso()
        db.brands.update_one({"_id": b["_id"]}, {"$set": ch})
        au.audit("brand_profile_updated", user["_id"], user.get("role"), brand_id=b["_id"], fields=sorted(k for k in ch if k != "updated_at"))
    return view(db.brands.find_one({"_id": b["_id"]}), owner=True)
