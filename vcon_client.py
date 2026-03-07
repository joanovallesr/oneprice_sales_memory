"""
Thin wrapper around VCON MCP Server. Uses FastMCP Client (STDIO or HTTP).
All functions are async and expect to be used with a client from get_vcon_client().
"""
# pyright: reportMissingImports=false
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional
from fastmcp import Client
from fastmcp.client.transports.stdio import StdioTransport

import config


def _vcon_parties(customer_name: str) -> list[dict]:
    """Build parties list: [customer, salesperson]. Party 0 = customer, 1 = agent."""
    return [
        {"name": customer_name, "role": "customer"},
        {"name": config.MULLINAX_SALESPERSON_NAME, "role": "agent"},
    ]


def _mullinax_subject(customer_name: str, source: str) -> str:
    """Subject line: Mullinax Lead – {customer_name} – {source} – {date}."""
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"Mullinax Lead – {customer_name} – {source} – {date}"


@asynccontextmanager
async def get_vcon_client():
    """Yield a FastMCP Client connected to VCON MCP Server (STDIO or HTTP)."""
    if config.VCON_MCP_URL:
        async with Client(config.VCON_MCP_URL) as client:
            yield client
    else:
        args = config.get_vcon_stdio_args()
        transport = StdioTransport(command=config.VCON_MCP_COMMAND, args=args)
        async with Client(transport) as client:
            yield client

async def _call(client: Client, tool: str, arguments: dict) -> dict:
    """Call VCON MCP tool; return result or raise with error message."""
    from fastmcp.exceptions import ToolError  # pyright: ignore[reportMissingImports]
    import json  # Added json import
    try:
        result = await client.call_tool(tool, arguments, raise_on_error=True)
        
        # If the server returned clean data, use it
        if result.data is not None:
            return result.data
            
        # If the server returned a JSON string inside a TextContent block, parse it!
        if result.content and isinstance(result.content, list) and hasattr(result.content[0], "text"):
            try:
                return json.loads(result.content[0].text)
            except json.JSONDecodeError:
                pass
                
        return {"content": result.content}
    except ToolError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def create_lead_vcon(
    client: Client,
    customer_name: str,
    source: str,
    vehicle_interest: Optional[str],
    notes: str,
) -> dict:
    """
    Create a new vCon for a Mullinax lead. Uses create_vcon_from_template,
    adds one text dialog, then tags (customer_name, source, funnel_stage, vehicle_interest).
    """
    template = "phone_call" if source == "phone_call" else "chat_conversation" if source == "web_lead" else "custom"
    subject = _mullinax_subject(customer_name, source)
    parties = _vcon_parties(customer_name)

    out = await _call(
        client,
        "create_vcon_from_template",
        {
            "template_name": template,
            "subject": subject,
            "parties": parties,
        },
    )
    if out.get("success") is False or "error" in out:
        return {"success": False, "error": out.get("error", out.get("message", str(out)))}
    uuid = out.get("uuid")
    if not uuid:
        return {"success": False, "error": "VCON returned no uuid"}

    # Add initial dialog (text body = notes)
    await _call(
        client,
        "add_dialog",
        {
            "vcon_uuid": uuid,
            "dialog": {
                "type": "text",
                "body": notes[:65535],
                "encoding": "none",
                "parties": [0, 1],
            },
        },
    )

    # Tags
    for key, value in [
        ("customer_name", customer_name),
        ("source", source),
        ("funnel_stage", "new_lead"),
    ] + ([("vehicle_interest", vehicle_interest)] if vehicle_interest else []):
        await _call(client, "add_tag", {"vcon_uuid": uuid, "key": key, "value": value})

    return {"success": True, "vcon_uuid": uuid, "subject": subject}


async def add_followup_vcon(client: Client, customer_name: str, notes: str) -> dict:
    """
    Create a new vCon for a follow-up (Option A: one vCon per event). Tagged
    source=followup_call and customer_name.
    """
    subject = f"Mullinax Follow-up – {customer_name} – {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    parties = _vcon_parties(customer_name)

    out = await _call(
        client,
        "create_vcon_from_template",
        {
            "template_name": "phone_call",
            "subject": subject,
            "parties": parties,
        },
    )
    if out.get("success") is False or "error" in out:
        return {"success": False, "error": out.get("error", out.get("message", str(out)))}
    uuid = out.get("uuid")
    if not uuid:
        return {"success": False, "error": "VCON returned no uuid"}

    await _call(
        client,
        "add_dialog",
        {
            "vcon_uuid": uuid,
            "dialog": {
                "type": "text",
                "body": notes[:65535],
                "encoding": "none",
                "parties": [0, 1],
            },
        },
    )
    await _call(client, "add_tag", {"vcon_uuid": uuid, "key": "customer_name", "value": customer_name})
    await _call(client, "add_tag", {"vcon_uuid": uuid, "key": "source", "value": "followup_call"})

    return {"success": True, "vcon_uuid": uuid, "customer_name": customer_name}


async def add_dialog(
    client: Client,
    vcon_uuid: str,
    body: str,
    parties: Optional[list[int]] = None,
) -> dict:
    """Add a text dialog to an existing vCon."""
    return await _call(
        client,
        "add_dialog",
        {
            "vcon_uuid": vcon_uuid,
            "dialog": {
                "type": "text",
                "body": body[:65535],
                "encoding": "none",
                "parties": parties or [0, 1],
            },
        },
    )


async def add_analysis(
    client: Client,
    vcon_uuid: str,
    type_name: str,
    vendor: str,
    body: str,
    encoding: str = "json",
    product: Optional[str] = None,
    schema_id: Optional[str] = None,
) -> dict:
    """Add an analysis object to a vCon (e.g. mullinax_lead_summary)."""
    payload = {
        "vcon_uuid": vcon_uuid,
        "analysis": {
            "type": type_name,
            "vendor": vendor,
            "body": body,
            "encoding": encoding,
        },
    }
    if product:
        payload["analysis"]["product"] = product
    if schema_id:
        payload["analysis"]["schema"] = schema_id
    return await _call(client, "add_analysis", payload)


async def add_tag(client: Client, vcon_uuid: str, key: str, value: Any) -> dict:
    """Add or update a single tag on a vCon."""
    return await _call(client, "add_tag", {"vcon_uuid": vcon_uuid, "key": key, "value": value})


async def get_vcon(
    client: Client,
    uuid: str,
    include_components: Optional[list[str]] = None,
) -> dict:
    """Retrieve a vCon by UUID."""
    args = {"uuid": uuid}
    if include_components is not None:
        args["include_components"] = include_components
    return await _call(client, "get_vcon", args)


async def search_vcons(
    client: Client,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    subject: Optional[str] = None,
    party_name: Optional[str] = None,
) -> dict:
    """Search vCons by metadata (subject, parties, dates)."""
    args = {"limit": limit, "offset": offset}
    if start_date:
        args["start_date"] = start_date
    if end_date:
        args["end_date"] = end_date
    if subject:
        args["subject"] = subject
    if party_name:
        args["party_name"] = party_name
    return await _call(client, "search_vcons", args)


async def search_by_tags(client: Client, tags: dict, limit: int = 50) -> dict:
    """Find vCons by tag key-value pairs."""
    return await _call(client, "search_by_tags", {"tags": tags, "limit": limit})


async def search_vcons_hybrid(
    client: Client,
    query: str,
    tags: Optional[dict] = None,
    limit: int = 20,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """Hybrid keyword + semantic search."""
    args = {"query": query, "limit": limit}
    if tags:
        args["tags"] = tags
    if start_date:
        args["start_date"] = start_date
    if end_date:
        args["end_date"] = end_date
    return await _call(client, "search_vcons_hybrid", args)
