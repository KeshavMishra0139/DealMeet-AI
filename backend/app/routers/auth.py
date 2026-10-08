"""Demo login. With Firebase configured the web app signs people in first and then
uses the same persona picker, because every persona is backed by demo data."""
import base64
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

PERSONAS = [
    {"id": "cr_a", "role": "creator", "title": "Creator A", "subtitle": "Anime-edit reels, Hindi and English, 21.3K followers", "tag": "Reference profile"},
    {"id": "cr_b", "role": "creator", "title": "Creator B", "subtitle": "Tamil home cooking, 2K followers, just starting", "tag": "Fictional"},
    {"id": "new_creator", "role": "creator", "title": "New creator", "subtitle": "Start from onboarding", "tag": "Onboarding"},
    {"id": "br_senpai", "role": "brand", "title": "Senpai Supply Co.", "subtitle": "Anime merch store", "tag": "Fictional brand"},
    {"id": "br_thalam", "role": "brand", "title": "Thalam Foods", "subtitle": "Regional masala and FMCG", "tag": "Fictional brand"},
    {"id": "new_brand", "role": "brand", "title": "New brand", "subtitle": "Start from brand onboarding", "tag": "Onboarding"},
]


class DemoLogin(BaseModel):
    persona: str


@router.get("/personas")
def personas():
    return PERSONAS


@router.post("/demo")
def demo_login(body: DemoLogin):
    p = next((p for p in PERSONAS if p["id"] == body.persona), None)
    if p is None:
        raise HTTPException(404, "Unknown persona")
    db = get_db()
    exists = True
    if p["role"] == "creator" and not p["id"].startswith("new_"):
        exists = db.creators.count_documents({"_id": p["id"]}) > 0
    if p["role"] == "brand" and not p["id"].startswith("new_"):
        exists = db.brands.count_documents({"_id": p["id"]}) > 0
    if not exists:
        raise HTTPException(404, "Persona data missing; reset the demo")
    token = base64.urlsafe_b64encode(json.dumps({"sub": p["id"], "role": p["role"]}).encode()).decode()
    return {"token": token, "persona": p}
