"""
Mullinax Sales Memory – FastMCP server exposing 6 tools that sit on top of VCON MCP.
Entrypoint: run this module to start the MCP server (STDIO).
"""
# pyright: reportMissingImports=false
from builtins import str, bool, dict, list, isinstance, int, Exception
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastmcp.server.server import FastMCP

import config
from analysis import classify_lead, generate_followup_script
from vcon_client import (
    add_analysis as vcon_add_analysis,
    add_followup_vcon as vcon_add_followup,
    add_tag,
    create_lead_vcon as vcon_create_lead,
    get_vcon,
    get_vcon_client,
    search_by_tags,
    search_vcons,
    search_vcons_hybrid,
)

mcp = FastMCP(name="mullinax_sales_memory")


@mcp.tool()
async def create_mullinax_lead_vcon(
    customer_name: str,
    notes: str,
    source: str,
    vehicle_interest: Optional[str] = None,
) -> dict:
    """
    Create a new vCon for a Mullinax lead (web, showroom, or phone).
    Uses VCON MCP create_vcon_from_template, adds one dialog, and tags (customer_name, source, funnel_stage, vehicle_interest).
    """
    if source not in ("web_lead", "phone_call", "showroom"):
        return {"success": False, "error": "source must be one of: web_lead, phone_call, showroom"}
    async with get_vcon_client() as client:
        out = await vcon_create_lead(client, customer_name, source, vehicle_interest, notes)
    if not out.get("success"):
        return {"success": False, "error": out.get("error", "Unknown error")}
    return {"success": True, "vcon_uuid": out["vcon_uuid"], "subject": out.get("subject", "")}


@mcp.tool()
async def add_followup_vcon(customer_name: str, notes: str) -> dict:
    """
    Record a follow-up (call or note) for an existing customer. Creates a new vCon tagged source=followup_call and customer_name.
    """
    async with get_vcon_client() as client:
        out = await vcon_add_followup(client, customer_name, notes)
    if not out.get("success"):
        return {"success": False, "error": out.get("error", "Unknown error")}
    return {"success": True, "vcon_uuid": out["vcon_uuid"], "customer_name": out["customer_name"]}


@mcp.tool()
async def analyze_and_tag_vcon(vcon_id: str) -> dict:
    """
    Run LLM classification on a vCon and attach analysis + tags (funnel_stage, urgency, vehicle_interest, etc.) via VCON MCP.
    """
    async with get_vcon_client() as client:
        get_out = await get_vcon(client, vcon_id, include_components=["parties", "dialog", "analysis", "attachments"])
    if get_out.get("success") is False or get_out.get("error"):
        return {"success": False, "error": get_out.get("error", "Failed to fetch vCon")}
    vcon = get_out.get("vcon") or get_out
    if not vcon:
        return {"success": False, "error": "vCon not found"}

    try:
        result = await classify_lead(vcon)
    except Exception as e:
        return {"success": False, "error": f"OpenAI classification failed: {e}"}

    body = result.model_dump_json()
    async with get_vcon_client() as client:
        await vcon_add_analysis(
            client,
            vcon_id,
            type_name="mullinax_lead_summary",
            vendor="MullinaxSalesMemory",
            body=body,
            encoding="json",
            product="openai-gpt-4o-mini",
            schema_id="mullinax-v1",
        )
        tags_added = []
        for key, value in result.model_dump(exclude_none=True).items():
            if isinstance(value, bool):
                value = str(value).lower()
            await add_tag(client, vcon_id, key, value)
            tags_added.append(key)

    return {
        "success": True,
        "vcon_uuid": vcon_id,
        "funnel_stage": result.funnel_stage,
        "urgency": result.urgency,
        "tags_added": tags_added,
    }


def _tags_from_vcon(vcon: dict) -> dict:
    """Get tags from vCon (metadata.tags or top-level tags)."""
    if vcon.get("metadata") and isinstance(vcon["metadata"].get("tags"), dict):
        return vcon["metadata"]["tags"]
    return vcon.get("tags") or {}


def _lead_summaries_from_vcons(vcons_list: list) -> list[dict]:
    """Build LeadSummary-like dicts from VCON search results (vcons array or results with vcon)."""
    out = []
    for item in vcons_list:
        vcon = item.get("vcon") if isinstance(item, dict) else item
        if not isinstance(vcon, dict):
            continue
        tags = _tags_from_vcon(vcon)
        out.append({
            "customer_name": tags.get("customer_name") or (vcon.get("parties") or [{}])[0].get("name") or "—",
            "vcon_uuid": vcon.get("uuid", ""),
            "subject": vcon.get("subject"),
            "vehicle_interest": tags.get("vehicle_interest"),
            "source": tags.get("source"),
            "created_at": vcon.get("created_at"),
        })
    return out


@mcp.tool()
async def get_hot_leads(days: int = 2) -> dict:
    """
    Return recent hot leads that have not received follow-up. Uses VCON search by date then filters by urgency and excludes customers who already have a follow-up vCon.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    start_date = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_date = end.strftime("%Y-%m-%dT%H:%M:%SZ")

    async with get_vcon_client() as client:
        search_out = await search_vcons(client, start_date=start_date, end_date=end_date, limit=100)
    if search_out.get("success") is False or search_out.get("error"):
        return {"success": False, "error": search_out.get("error", "Search failed"), "leads": []}

    vcons = search_out.get("vcons") or []
    # Filter: has urgency=hot_lead (or funnel_stage=new_lead for demo), and no follow-up for this customer
    by_customer: dict[str, list] = {}
    for v in vcons:
        tags = _tags_from_vcon(v)
        cust = tags.get("customer_name") or (v.get("parties") or [{}])[0].get("name") or ""
        if not cust:
            continue
        src = tags.get("source")
        if src == "followup_call":
            by_customer.setdefault(cust, []).append("followup")
        else:
            by_customer.setdefault(cust, []).append(v)

    hot = []
    for cust, list_or_vcons in by_customer.items():
        if "followup" in list_or_vcons:
            continue
        for v in list_or_vcons:
            if v == "followup":
                continue
            tags = _tags_from_vcon(v)
            if tags.get("urgency") == "hot_lead" or tags.get("funnel_stage") == "new_lead":
                hot.append(v)
                break

    leads = _lead_summaries_from_vcons(hot)
    return {"success": True, "leads": leads}


@mcp.tool()
async def get_missed_leads(days: int = 2) -> dict:
    """
    New leads with no follow-up vCon in the given period. Search vCons by date, filter to funnel_stage=new_lead (or source in web_lead/phone_call/showroom), exclude customers with any source=followup_call.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    start_date = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_date = end.strftime("%Y-%m-%dT%H:%M:%SZ")

    async with get_vcon_client() as client:
        search_out = await search_vcons(client, start_date=start_date, end_date=end_date, limit=100)
    if search_out.get("success") is False or search_out.get("error"):
        return {"success": False, "error": search_out.get("error", "Search failed"), "leads": []}

    vcons = search_out.get("vcons") or []
    by_customer: dict[str, list] = {}
    for v in vcons:
        tags = _tags_from_vcon(v)
        cust = tags.get("customer_name") or (v.get("parties") or [{}])[0].get("name") or ""
        if not cust:
            continue
        src = tags.get("source")
        if src == "followup_call":
            by_customer.setdefault(cust, []).append("followup")
        else:
            by_customer.setdefault(cust, []).append(v)

    missed = []
    for cust, list_or_vcons in by_customer.items():
        if "followup" in list_or_vcons:
            continue
        for v in list_or_vcons:
            if v == "followup":
                continue
            tags = _tags_from_vcon(v)
            stage = tags.get("funnel_stage")
            src = tags.get("source")
            if stage == "new_lead" or src in ("web_lead", "phone_call", "showroom"):
                missed.append(v)
                break

    leads = _lead_summaries_from_vcons(missed)
    return {"success": True, "leads": leads}


@mcp.tool()
async def generate_followup(customer_name: str) -> dict:
    """
    Generate a Mullinax-style (no-haggle, one-price, friendly) follow-up message. Finds all vCons for this customer, builds context, and uses OpenAI to produce a short script.
    """
    async with get_vcon_client() as client:
        tag_out = await search_by_tags(client, {"customer_name": customer_name}, limit=20)
    if tag_out.get("success") is False or tag_out.get("error"):
        return {"success": False, "error": tag_out.get("error", "Search failed"), "customer_name": customer_name}

    uuids = tag_out.get("vcon_uuids") or []
    vcons = tag_out.get("vcons") or []
    if not uuids and not vcons:
        return {"success": False, "error": f"No vCons found for customer: {customer_name}", "customer_name": customer_name}

    # If we only got UUIDs, fetch full vCons
    if not vcons and uuids:
        async with get_vcon_client() as client:
            for uuid in uuids[:10]:
                g = await get_vcon(client, uuid)
                if g.get("vcon"):
                    vcons.append(g["vcon"])

    from analysis import _vcon_to_text
    context_parts = [_vcon_to_text(v) for v in vcons]
    vcons_context = "\n---\n".join(context_parts)

    try:
        script, channel = await generate_followup_script(customer_name, vcons_context)
    except Exception as e:
        return {"success": False, "error": str(e), "customer_name": customer_name}

    return {
        "success": True,
        "customer_name": customer_name,
        "followup_script": script,
        "suggested_channel": channel,
    }


@mcp.tool()
async def search_by_intent(intent_query: str, days: int = 7) -> dict:
    """Semantic/hybrid search (e.g. 'customers worried about monthly payment under 600')."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    start_date = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_date = end.strftime("%Y-%m-%dT%H:%M:%SZ")
    async with get_vcon_client() as client:
        out = await search_vcons_hybrid(client, intent_query, start_date=start_date, end_date=end_date)

    if out.get("success") is False:
        return {"success": False, "error": out.get("error"), "results": []}

    raw = out.get("results") or []
    vcons = [r.get("vcon") or r for r in raw if isinstance(r, dict)]
    results = _lead_summaries_from_vcons(vcons)
    return {"success": True, "results": results, "query": intent_query}


if __name__ == "__main__":
    mcp.run(transport="stdio")
