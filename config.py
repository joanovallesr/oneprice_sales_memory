"""
Load settings from environment. Used by vcon_client (VCON MCP connection)
and analysis (OpenAI). Supports STDIO (Docker/local) for VCON MCP.
"""
# pyright: reportMissingImports=false
import os
from builtins import str
from pathlib import Path
from typing import List

from dotenv.main import load_dotenv

# Load .env from project root (directory containing this file)
load_dotenv(Path(__file__).resolve().parent / ".env")

# VCON MCP connection
VCON_MCP_URL = os.getenv("VCON_MCP_URL")  # If set, use HTTP transport
VCON_MCP_COMMAND = os.getenv("VCON_MCP_COMMAND", "docker")
VCON_MCP_STDIO_ARGS = os.getenv("VCON_MCP_STDIO_ARGS", "run,--rm,-i,vcon/vcon-mcp")

def get_vcon_stdio_args() -> List[str]:
    """Parse VCON_MCP_STDIO_ARGS (comma-separated) into a list for StdioTransport."""
    if not VCON_MCP_STDIO_ARGS:
        return []
    return [a.strip() for a in VCON_MCP_STDIO_ARGS.split(",") if a.strip()]

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Optional: name used as salesperson/agent in vCon parties
SALESPERSON_NAME = os.getenv("SALESPERSON_NAME", "Mullinax Sales")
