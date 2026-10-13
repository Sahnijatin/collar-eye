import asyncio, os, sys
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

async def main():
    params = StdioServerParameters(command=sys.executable, args=["mcp/mcp_eye.py"],
                                   env={**os.environ, "EYE_GATEWAY": "http://localhost:7863", "EYE_TOKEN": "k1"})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print("tools:", [t.name for t in tools.tools])
            for name, args in [("look", {}), ("look_burst", {"count": 2, "interval_seconds": 0.3}), ("camera_status", {}), ("say", {"text": "hi"}), ("set_camera", {"fps": 3})]:
                res = await s.call_tool(name, args)
                print(name, "error" if res.is_error else "ok", [(c.type, getattr(c, "mime_type", None) or getattr(c, "mimeType", None), (getattr(c, "text", "") or "")[:80]) for c in res.content])
asyncio.run(main())
