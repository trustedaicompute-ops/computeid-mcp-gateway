"""Smoke test: start the installed server over stdio, initialize, list tools.

Usage: python .github/smoke_mcp.py <command> [args...]
e.g.   python .github/smoke_mcp.py computeid-mcp
       python .github/smoke_mcp.py python -m computeid_mcp

No API key or network is needed: initialize and tools/list are served
locally by the MCP server.
"""
import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED = {"issue_agent_passport", "verify_agent_passport", "register_device", "list_devices", "revoke_device"}


async def main(cmd, args):
    params = StdioServerParameters(command=cmd, args=args)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await asyncio.wait_for(session.initialize(), timeout=20)
            tools = {t.name for t in (await session.list_tools()).tools}
    missing = EXPECTED - tools
    assert not missing, f"missing tools: {sorted(missing)}"
    assert "approve_device" not in tools, "approve_device should be gone"
    print(f"{' '.join([cmd, *args])}: server '{init.serverInfo.name}' started, {len(tools)} tools")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2:]))
