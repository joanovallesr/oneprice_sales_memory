import asyncio
from vcon_client import get_vcon_client, create_lead_vcon

async def main():
    print("Spinning up the VCON Docker container via STDIO...")
    try:
        async with get_vcon_client() as client:
            print("Successfully connected to VCON Server!")
            
            print("Attempting to create a test lead...")
            out = await create_lead_vcon(
                client, 
                customer_name="Test User", 
                source="web_lead", 
                vehicle_interest="Ford Mustang", 
                notes="Testing the connection"
            )
            print("Result:", out)
    except Exception as e:
        print("Crash detected:", str(e))

if __name__ == "__main__":
    asyncio.run(main())