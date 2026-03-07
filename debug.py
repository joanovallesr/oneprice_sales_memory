import asyncio
from fastmcp.client import Client
from fastmcp.client.transports.stdio import StdioTransport
import config

async def main():
    print("Connecting to VCON...")
    args = config.get_vcon_stdio_args()
    
    # FastMCP uses the command (docker) and the args separately
    transport = StdioTransport(command=config.VCON_MCP_COMMAND, args=args)
    
    async with Client(transport) as client:
        print("Connected! Creating test lead...")
        resp = await client.call_tool("create_vcon_from_template", {
            "template_name": "default",
            "subject": "Raw JSON Test",
            "parties": [{"name": "Test User", "role": "customer"}]
        })
        print("RAW RESPONSE FROM SERVER")
        print(resp)

if __name__ == "__main__":
    asyncio.run(main())