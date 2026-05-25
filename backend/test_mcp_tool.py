"""
Skrypt do testowania konkretnego narzedzia MCP.
Uzycie:
    python test_mcp_tool.py
    python test_mcp_tool.py --url http://localhost:8010/mcp --tool server_container_status
    python test_mcp_tool.py --list
"""
import argparse
import asyncio
import json
import sys


DEFAULT_URL = "http://localhost:8010/mcp"
DEFAULT_API_KEY = "dev-mcp-key"


async def list_tools(url: str, api_key: str) -> None:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    headers = {"X-API-Key": api_key} if api_key else {}
    async with asyncio.timeout(10):
        async with streamablehttp_client(url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                tools = getattr(result, "tools", [])
                print(f"\nDostepne narzedzia MCP ({len(tools)}):")
                for tool in tools:
                    print(f"  - {tool.name}: {tool.description or '(brak opisu)'}")


async def call_tool(url: str, api_key: str, tool_name: str, args: dict) -> None:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    headers = {"X-API-Key": api_key} if api_key else {}
    print(f"\nWywoluje narzedzie: {tool_name}")
    print(f"Argumenty: {json.dumps(args, ensure_ascii=False)}")
    print(f"URL: {url}\n")

    async with asyncio.timeout(20):
        async with streamablehttp_client(url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)

    is_error = getattr(result, "isError", False)
    status = "BLAD" if is_error else "OK"
    print(f"Status: {status}")

    content = getattr(result, "content", [])
    for item in content:
        text = getattr(item, "text", None)
        if text is not None:
            try:
                parsed = json.loads(text)
                print(json.dumps(parsed, indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                print(text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test narzedzia MCP")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"URL MCP serwera (domyslnie: {DEFAULT_URL})")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="Klucz API")
    parser.add_argument("--tool", default="server_container_status", help="Nazwa narzedzia do wywolania")
    parser.add_argument("--args", default="{}", help='Argumenty w formacie JSON, np. \'{"name_filter": "mcp"}\'')
    parser.add_argument("--list", action="store_true", help="Wylistuj dostepne narzedzia")
    return parser.parse_args()


async def main() -> None:
    ns = parse_args()
    try:
        if ns.list:
            await list_tools(ns.url, ns.api_key)
        else:
            tool_args = json.loads(ns.args)
            await call_tool(ns.url, ns.api_key, ns.tool, tool_args)
    except TimeoutError:
        print(f"\nBLAD: Timeout - MCP serwer nie odpowiada pod {ns.url}")
        print("Upewnij sie ze kontener mcp-server jest uruchomiony.")
        sys.exit(1)
    except Exception as exc:
        print(f"\nBLAD: {exc}")
        print("Upewnij sie ze MCP serwer dziala i adres URL jest poprawny.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
