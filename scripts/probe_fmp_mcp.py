"""Probe the FMP MCP server: list tools and dump each tool's input schema."""

import asyncio
import json
import os

from dotenv import load_dotenv
from fastmcp import Client

load_dotenv()


async def main():
    api_key = os.environ.get("FMP_API_KEY")
    if not api_key:
        raise SystemExit("FMP_API_KEY not set")

    url = f"https://financialmodelingprep.com/mcp?apikey={api_key}"
    async with Client(url) as c:
        tools = await c.list_tools()
        for t in sorted(tools, key=lambda x: x.name):
            print(f"\n=== {t.name} ===")
            if t.description:
                print(f"description: {t.description}")
            schema = getattr(t, "inputSchema", None) or getattr(t, "input_schema", None)
            if schema:
                print("inputSchema:")
                print(json.dumps(schema, indent=2))
            else:
                print("(no input schema)")
        print(f"\nTotal: {len(tools)} tools")


if __name__ == "__main__":
    asyncio.run(main())
