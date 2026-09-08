from __future__ import annotations

import json
from itertools import count
from typing import Any

import httpx


class MCPError(RuntimeError):
    pass


class ZoteroMCPClient:
    """Small JSON-RPC client for the Streamable HTTP server in zotero-mcp.

    The Zotero plugin returns a ``Mcp-Session-Id`` response header. We keep it
    and send it on subsequent calls, but deliberately use only public MCP tools
    rather than reading Zotero/plugin SQLite files directly.
    """

    def __init__(self, url: str, timeout: float = 120.0) -> None:
        self.url = url
        self._ids = count(1)
        self._session_id: str | None = None
        self._initialized = False
        self._http = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=10.0),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> ZoteroMCPClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": next(self._ids),
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        headers: dict[str, str] = {}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        response = self._http.post(self.url, json=payload, headers=headers)
        response.raise_for_status()

        new_session = response.headers.get("Mcp-Session-Id")
        if new_session:
            self._session_id = new_session

        if not response.content:
            return {}

        data = response.json()
        if "error" in data:
            error = data["error"] or {}
            raise MCPError(f"MCP {method} failed ({error.get('code')}): {error.get('message')}")
        return data.get("result", {})

    def initialize(self) -> dict[str, Any]:
        if self._initialized:
            return {}
        result = self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "graph-research-zotero", "version": "0.1.0"},
            },
        )
        self._initialized = True
        return result

    def ping(self) -> None:
        self.initialize()
        self._request("ping")

    def list_tools(self) -> list[dict[str, Any]]:
        self.initialize()
        return list(self._request("tools/list").get("tools", []))

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        self.initialize()
        result = self._request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        content = result.get("content", [])
        if not content:
            return result

        # zotero-mcp wraps each tool result in MCP text content and the text is
        # itself JSON when the underlying tool returned an object/array.
        text_parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        text = "\n".join(text_parts)
        if not text:
            return result
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
