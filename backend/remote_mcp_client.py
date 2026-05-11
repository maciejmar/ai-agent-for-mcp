from __future__ import annotations

import asyncio
import json
import os
from typing import Any


class RemoteMCPClient:
    def __init__(self) -> None:
        self.url = os.getenv("MCP_SERVER_URL", "http://mcp-server:8000/mcp")
        self.api_key = os.getenv("MCP_API_KEY", "")
        self.timeout_seconds = float(os.getenv("MCP_CLIENT_TIMEOUT_SECONDS", "20"))
        self.enabled = os.getenv("REMOTE_MCP_ENABLED", "true").lower() in {"1", "true", "yes"}

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "error": "Remote MCP client is disabled."}

        try:
            return asyncio.run(self._call_tool(name, arguments or {}))
        except Exception as exc:
            return {"ok": False, "tool": name, "error": f"Remote MCP call failed: {exc}"}

    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        headers = {"X-API-Key": self.api_key} if self.api_key else {}
        async with asyncio.timeout(self.timeout_seconds):
            async with streamablehttp_client(self.url, headers=headers) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments)

        return {
            "ok": not getattr(result, "isError", False),
            "tool": name,
            "result": self._serialize_result(result),
        }

    def _serialize_result(self, result: Any) -> Any:
        content = getattr(result, "content", None)
        if content is None:
            return result

        serialized: list[Any] = []
        for item in content:
            text = getattr(item, "text", None)
            if text is not None:
                serialized.append(self._parse_json_or_text(text))
                continue

            model_dump = getattr(item, "model_dump", None)
            serialized.append(model_dump() if callable(model_dump) else str(item))

        if len(serialized) == 1:
            return serialized[0]
        return serialized

    @staticmethod
    def _parse_json_or_text(value: str) -> Any:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
