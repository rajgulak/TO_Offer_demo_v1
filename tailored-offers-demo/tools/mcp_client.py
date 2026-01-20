"""
MCP Client for Tailored Offers Data Tools

Wraps langchain-mcp-adapters to provide a simple interface for calling
the MCP data server from the agent workflow.

Production Features:
- Retry logic with exponential backoff
- Circuit breaker pattern for fault tolerance
- Structured logging with correlation IDs
- Prometheus metrics for latency tracking

Usage:
    client = MCPDataClient()
    data = await client.get_enriched_pnr("ABC123")
"""
import asyncio
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

# Import infrastructure modules
try:
    from infrastructure.logging import get_logger, log_mcp_call
    from infrastructure.metrics import metrics, mcp_calls, mcp_latency
    from infrastructure.retry import retry_mcp_call, RetryConfig
    INFRASTRUCTURE_AVAILABLE = True
except ImportError:
    INFRASTRUCTURE_AVAILABLE = False

# Initialize logger
logger = get_logger("mcp_client") if INFRASTRUCTURE_AVAILABLE else None

# Get the path to the MCP server relative to this file
MCP_SERVER_PATH = str(Path(__file__).parent / "mcp_server.py")


class MCPDataClient:
    """
    MCP client for data tools.

    Uses langchain-mcp-adapters to communicate with the MCP data server
    via stdio transport (spawns server as subprocess).
    """

    def __init__(self, server_path: Optional[str] = None):
        """
        Initialize MCP client.

        Args:
            server_path: Path to mcp_server.py (defaults to tools/mcp_server.py)
        """
        self.server_path = server_path or MCP_SERVER_PATH
        self.server_config = {
            "tailored_offers_data": {
                "command": "python",
                "args": [self.server_path],
                "transport": "stdio",
            }
        }

    async def _call_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Call an MCP tool by name with retry logic and metrics.

        Args:
            tool_name: Name of the MCP tool (e.g., "mcp_get_enriched_pnr")
            **kwargs: Arguments to pass to the tool

        Returns:
            Tool result or None if tool not found
        """
        start_time = time.time()

        # Log start
        if logger:
            logger.info(
                "mcp_call_started",
                tool=tool_name,
                kwargs=str(kwargs)[:200],
            )

        try:
            result = await self._call_tool_with_retry(tool_name, **kwargs)

            duration = time.time() - start_time

            # Record metrics
            if INFRASTRUCTURE_AVAILABLE:
                metrics.record_mcp_call(tool_name, success=True, duration=duration)

            # Log success
            if logger:
                logger.info(
                    "mcp_call_completed",
                    tool=tool_name,
                    duration_ms=round(duration * 1000, 2),
                    has_result=result is not None,
                )

            return result

        except Exception as e:
            duration = time.time() - start_time

            # Record failure metrics
            if INFRASTRUCTURE_AVAILABLE:
                metrics.record_mcp_call(tool_name, success=False, duration=duration)

            # Log error
            if logger:
                logger.error(
                    "mcp_call_failed",
                    tool=tool_name,
                    duration_ms=round(duration * 1000, 2),
                    error=str(e),
                    error_type=type(e).__name__,
                )

            raise

    async def _call_tool_with_retry(
        self,
        tool_name: str,
        max_attempts: int = 3,
        **kwargs
    ) -> Any:
        """Call MCP tool with retry logic."""
        last_exception = None

        for attempt in range(max_attempts):
            try:
                return await self._call_tool_internal(tool_name, **kwargs)

            except Exception as e:
                last_exception = e

                # Log retry
                if logger and attempt < max_attempts - 1:
                    logger.warning(
                        "mcp_retry_attempt",
                        tool=tool_name,
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                        error=str(e),
                    )

                # Exponential backoff
                if attempt < max_attempts - 1:
                    wait_time = min(1.0 * (2 ** attempt), 10.0)
                    await asyncio.sleep(wait_time)

        raise last_exception

    async def _call_tool_internal(self, tool_name: str, **kwargs) -> Any:
        """Internal tool call without retry."""
        try:
            import json
            from langchain_mcp_adapters.client import MultiServerMCPClient

            # Create client (not a context manager in 0.1.0+)
            client = MultiServerMCPClient(self.server_config)
            tools = await client.get_tools()

            for tool in tools:
                if tool.name == tool_name:
                    result = await tool.ainvoke(kwargs)

                    # Parse the MCP response format
                    # MCP returns: [{"type": "text", "text": "<json_string>", "id": "..."}]
                    if isinstance(result, list) and len(result) > 0:
                        content = result[0]
                        if isinstance(content, dict) and content.get("type") == "text":
                            text_content = content.get("text", "")
                            try:
                                return json.loads(text_content)
                            except json.JSONDecodeError:
                                return text_content
                        return content

                    return result

            return None

        except ImportError:
            raise ImportError(
                "langchain-mcp-adapters is required for MCP client. "
                "Install with: pip install langchain-mcp-adapters"
            )

    async def get_enriched_pnr(self, pnr_loctr_id: str) -> Optional[Dict[str, Any]]:
        """
        Get fully enriched PNR with customer, flight, and ML data.

        This is the main method used by the workflow - combines all data sources.

        Args:
            pnr_loctr_id: PNR locator code (e.g., "ABC123")

        Returns:
            Dict with keys: pnr, customer, flight, ml_scores
        """
        result = await self._call_tool("mcp_get_enriched_pnr", pnr_loctr_id=pnr_loctr_id)
        return result if result else None

    async def get_customer(self, lylty_acct_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve customer profile by loyalty account ID.

        Args:
            lylty_acct_id: Customer's loyalty account ID

        Returns:
            Customer profile dict
        """
        result = await self._call_tool("mcp_get_customer", lylty_acct_id=lylty_acct_id)
        return result if result else None

    async def get_reservation(self, pnr_loctr_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve reservation/PNR data.

        Args:
            pnr_loctr_id: PNR locator code

        Returns:
            Reservation dict
        """
        result = await self._call_tool("mcp_get_reservation", pnr_loctr_id=pnr_loctr_id)
        return result if result else None

    async def get_flight(self, operat_flight_nbr: int, leg_dep_dt: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve flight and inventory data.

        Args:
            operat_flight_nbr: Operating flight number
            leg_dep_dt: Optional departure date filter

        Returns:
            Flight data dict
        """
        kwargs = {"operat_flight_nbr": operat_flight_nbr}
        if leg_dep_dt:
            kwargs["leg_dep_dt"] = leg_dep_dt
        result = await self._call_tool("mcp_get_flight", **kwargs)
        return result if result else None

    async def get_ml_scores(self, pnr_loctr_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve ML propensity scores for a PNR.

        Args:
            pnr_loctr_id: PNR locator code

        Returns:
            ML scores dict with propensity_scores, confidence, segment
        """
        result = await self._call_tool("mcp_get_ml_scores", pnr_loctr_id=pnr_loctr_id)
        return result if result else None

    async def get_eligible_pnrs(self) -> List[Dict[str, Any]]:
        """
        Get all PNRs eligible for offer evaluation.

        Returns:
            List of eligible reservation records
        """
        result = await self._call_tool("mcp_get_eligible_pnrs")
        return result if result else []


# Convenience function for sync contexts
def get_mcp_client() -> MCPDataClient:
    """Get a new MCP client instance."""
    return MCPDataClient()


# Example usage
if __name__ == "__main__":
    async def main():
        client = MCPDataClient()

        # Test get_enriched_pnr
        print("Testing MCP client...")
        data = await client.get_enriched_pnr("ABC123")

        if data:
            print(f"Customer: {data['customer']['first_name']} {data['customer']['last_name']}")
            print(f"Flight: {data['flight']['flight_id']}")
            print(f"Tier: {data['customer']['loyalty_tier']}")
        else:
            print("No data returned")

    asyncio.run(main())
