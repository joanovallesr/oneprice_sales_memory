"""
OpenAI integration: classify a vCon into funnel/urgency/tags and generate
Mullinax-style follow-up scripts. Uses models.AnalysisResult.
"""
# pyright: reportMissingImports=false
import json
from builtins import ValueError, bool, enumerate, str, tuple
from pathlib import Path
from typing import Any, Dict

from openai._client import AsyncOpenAI
from pydantic import ValidationError

import config
from models import AnalysisResult


def _openai_client() -> AsyncOpenAI:
    if not config.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set")
    return AsyncOpenAI(api_key=config.OPENAI_API_KEY)


def _vcon_to_text(vcon: Dict[str, Any]) -> str:
    """Extract subject + dialog bodies + existing analysis for LLM context."""
    parts = []
    if vcon.get("subject"):
        parts.append(f"Subject: {vcon['subject']}")
    for i, d in enumerate(vcon.get("dialog") or []):
        if d.get("body"):
            parts.append(f"Dialog[{i}]: {d['body']}")
    for a in vcon.get("analysis") or []:
        if a.get("body"):
            parts.append(f"Analysis: {a['body']}")
    return "\n\n".join(parts) or "(no content)"


CLASSIFY_SYSTEM = """You classify car-sales conversation summaries for Mullinax Ford (no-haggle, one-price dealer).
Output valid JSON only, with these exact keys:
- funnel_stage: one of new_lead, appointment_set, in_store, pending_finance, sold, lost
- urgency: one of hot_lead, warm_lead, cold_lead
- vehicle_interest: string or null (e.g. F-150, Bronco, Explorer)
- payment_sensitive: boolean
- shopping_competitors: boolean
- price_shock: boolean
- needs_manager_followup: boolean
- timeline: string or null (e.g. "2_weeks", "this_week", "just_browsing")
- summary: one or two sentence summary
"""


async def classify_lead(vcon_dict: Dict[str, Any]) -> AnalysisResult:
    """
    Call OpenAI to classify the vCon into funnel stage, urgency, and tags.
    Returns an AnalysisResult for attaching as analysis + tags.
    """
    text = _vcon_to_text(vcon_dict)
    client = _openai_client()
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": CLASSIFY_SYSTEM},
            {"role": "user", "content": f"Classify this conversation:\n\n{text}"},
        ],
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content
    data = json.loads(raw)
    try:
        return AnalysisResult(
            funnel_stage=data.get("funnel_stage", "new_lead"),
            urgency=data.get("urgency", "warm_lead"),
            vehicle_interest=data.get("vehicle_interest"),
            payment_sensitive=bool(data.get("payment_sensitive", False)),
            shopping_competitors=bool(data.get("shopping_competitors", False)),
            price_shock=bool(data.get("price_shock", False)),
            needs_manager_followup=bool(data.get("needs_manager_followup", False)),
            timeline=data.get("timeline"),
            summary=data.get("summary"),
        )
    except ValidationError:
        return AnalysisResult(
            funnel_stage=data.get("funnel_stage", "new_lead"),
            urgency=data.get("urgency", "warm_lead"),
            vehicle_interest=data.get("vehicle_interest"),
            payment_sensitive=bool(data.get("payment_sensitive", False)),
            shopping_competitors=bool(data.get("shopping_competitors", False)),
            price_shock=bool(data.get("price_shock", False)),
            needs_manager_followup=bool(data.get("needs_manager_followup", False)),
            timeline=data.get("timeline"),
            summary=data.get("summary"),
        )


def _load_mullinax_tone() -> str:
    path = Path(__file__).resolve().parent / "sample_data" / "mullinax_tone.md"
    if path.exists():
        return path.read_text()
    return "Mullinax Ford: one price, no haggle, transparent, friendly, no pressure."


async def generate_followup_script(customer_name: str, vcons_context: str) -> tuple[str, str]:
    """
    Generate a short Mullinax-style follow-up (phone or email). Returns (script, channel).
    """
    tone = _load_mullinax_tone()
    client = _openai_client()
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"You write follow-up messages for Mullinax Ford sales. Tone: {tone}. Keep it short (2–4 sentences). Output JSON only with keys: followup_script (string), suggested_channel (phone or email).",
            },
            {
                "role": "user",
                "content": f"Customer: {customer_name}\n\nContext:\n{vcons_context}\n\nWrite a follow-up.",
            },
        ],
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content
    data = json.loads(raw)
    script = data.get("followup_script", "Hi, just following up. Please call us when you're ready.")
    channel = data.get("suggested_channel", "phone")
    if channel not in ("phone", "email"):
        channel = "phone"
    return script, channel
