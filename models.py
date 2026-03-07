"""
Pydantic models for tool inputs/outputs and internal types.
Aligns with plan §3 tool outputs and analysis.py LLM response shape.
"""
# pyright: reportMissingImports=false
from builtins import bool, str
from pydantic import BaseModel
from pydantic.fields import Field
from typing import Optional


class LeadSummary(BaseModel):
    """One lead in get_hot_leads or get_missed_leads response."""
    customer_name: str
    vcon_uuid: str
    subject: Optional[str] = None
    vehicle_interest: Optional[str] = None
    source: Optional[str] = None
    created_at: Optional[str] = None


class VconMetadata(BaseModel):
    """Minimal vCon reference for create/add tool responses."""
    success: bool = True
    vcon_uuid: Optional[str] = None
    subject: Optional[str] = None
    customer_name: Optional[str] = None
    error: Optional[str] = None


class AnalysisResult(BaseModel):
    """Structured output from OpenAI classify_lead (analysis.py)."""
    funnel_stage: str = Field(description="One of: new_lead, appointment_set, in_store, pending_finance, sold, lost")
    urgency: str = Field(description="One of: hot_lead, warm_lead, cold_lead")
    vehicle_interest: Optional[str] = None
    payment_sensitive: bool = False
    shopping_competitors: bool = False
    price_shock: bool = False
    needs_manager_followup: bool = False
    timeline: Optional[str] = None
    summary: Optional[str] = None


class FollowUpResult(BaseModel):
    """Output for generate_followup tool."""
    customer_name: str
    followup_script: str
    suggested_channel: str = Field(description="One of: phone, email")
