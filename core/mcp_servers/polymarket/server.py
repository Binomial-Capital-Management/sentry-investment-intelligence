"""
MCP server wrapper exposing Polymarket tools via PolymarketService.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agents.mcp import MCPServer
from agents.mcp.server import CallToolResult
from mcp.types import TextContent

from .service import PolymarketService
from .http_client import PolymarketHTTPError

logger = logging.getLogger(__name__)


class PolymarketServer(MCPServer):
    """Thin MCP adapter around the Polymarket service layer."""

    def __init__(self, **service_kwargs: Any) -> None:
        super().__init__(use_structured_content=False)
        self._name = "PolymarketServer"
        self.service = PolymarketService(**service_kwargs)
        self._tools = self.service.build_tools()

    @property
    def name(self) -> str:
        return self._name

    async def connect(self):
        logger.info(
            "PolymarketServer connected (gamma=%s, clob=%s)",
            self.service.gamma_base_url,
            self.service.clob_base_url,
        )

    async def cleanup(self):
        await self.service.close()
        logger.info("PolymarketServer cleaned up")

    async def list_prompts(self) -> List[str]:
        return []

    async def get_prompt(self, name: str, arguments: Optional[Dict[str, Any]] = None):
        raise NotImplementedError("PolymarketServer does not expose prompts.")

    async def list_tools(self, run_context=None, agent=None) -> List[Any]:  # type: ignore[override]
        if run_context and hasattr(run_context, "tenant_id"):
            self.service.set_tenant(run_context.tenant_id)
        return self._tools

    async def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]]) -> CallToolResult:
        params = arguments or {}

        handlers = {
            "discover_polymarket_tags": self.service.discover_tags,
            "get_polymarket_markets_by_tag": self.service.get_markets_by_tag,
            "discover_polymarket_market_fields": self.service.discover_market_fields,
            "get_polymarket_quotes": self.service.get_quotes,
            "get_polymarket_price_history": self.service.get_price_history,
            "search_polymarket_markets": self.service.search_markets,
        }

        handler = handlers.get(tool_name)
        if handler is None:
            return _error_result(f"Unknown tool: {tool_name}")

        try:
            if "tenant_id" in params:
                self.service.set_tenant(str(params["tenant_id"]))
            payload = await handler(params)
            return _success_result(payload)
        except ValueError as exc:
            logger.warning("Polymarket tool validation error (%s): %s", tool_name, exc)
            return _error_result(str(exc))
        except PolymarketHTTPError as exc:
            logger.error("Polymarket API error (%s): %s", tool_name, exc)
            message = exc.payload if isinstance(exc.payload, str) else json.dumps(exc.payload, default=str)
            return _error_result(f"{exc} :: {message}")
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected Polymarket server failure for %s", tool_name)
            return _error_result(f"Unexpected Polymarket error: {exc}")


def _success_result(payload: Dict[str, Any]) -> CallToolResult:
    text = json.dumps(payload, default=str, indent=2)
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        isError=False,
    )


def _error_result(message: str) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=message)],
        isError=True,
    )
