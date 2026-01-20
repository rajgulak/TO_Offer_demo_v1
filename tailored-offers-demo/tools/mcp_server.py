"""
MCP Server for Tailored Offers Data Tools

This server exposes the data access tools via the Model Context Protocol (MCP).
In production, swap the JSON file reads with real API calls.

Run standalone:
    python tools/mcp_server.py

Run with MCP Inspector:
    mcp dev tools/mcp_server.py
"""
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path so we can import data_tools
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP
from tools.data_tools import (
    get_customer,
    get_reservation,
    get_flight,
    get_ml_scores,
    get_enriched_pnr,
    get_all_eligible_pnrs
)

# Create MCP server instance
mcp = FastMCP("TailoredOffersData")


@mcp.tool()
def mcp_get_customer(lylty_acct_id: str) -> dict:
    """
    Retrieve customer profile by loyalty account ID.

    In production: Calls North Star Data Platform / Customer 360
    Source: PROD_LYLTY_METRICS_VW, custlylty_prod_pkg

    Args:
        lylty_acct_id: Customer's loyalty account ID (e.g., "LYLTY001")

    Returns:
        Customer profile with loyalty_tier, historical_upgrades, preferences, etc.
    """
    result = get_customer(lylty_acct_id)
    return result if result else {}


@mcp.tool()
def mcp_get_reservation(pnr_loctr_id: str) -> dict:
    """
    Retrieve reservation/PNR data by PNR locator.

    In production: Calls sbpnr_prod_pkg / PNR_AIR_SEG
    Source: Streaming NRT (30 minutes latency)

    Args:
        pnr_loctr_id: PNR locator code (e.g., "ABC123")

    Returns:
        Reservation with flight details, cabin, hours_to_departure, etc.
    """
    result = get_reservation(pnr_loctr_id)
    return result if result else {}


@mcp.tool()
def mcp_get_flight(operat_flight_nbr: int, leg_dep_dt: Optional[str] = None) -> dict:
    """
    Retrieve flight and inventory data by operating flight number.

    In production: Calls Flight Operations / fltcorepkg_prod_pkg_pii
    Source: flight_leg_nrt table

    Args:
        operat_flight_nbr: Operating flight number (e.g., 2847)
        leg_dep_dt: Optional departure date filter (YYYY-MM-DD)

    Returns:
        Flight data with cabins, inventory, load factors, product catalog
    """
    result = get_flight(operat_flight_nbr, leg_dep_dt)
    return result if result else {}


@mcp.tool()
def mcp_get_ml_scores(pnr_loctr_id: str) -> dict:
    """
    Retrieve ML propensity scores for a PNR.

    In production: Calls ML Model Serving API (the P(buy) model)
    Returns P(buy) at different price points for each product.

    Args:
        pnr_loctr_id: PNR locator code (e.g., "ABC123")

    Returns:
        Propensity scores with price_points, confidence, segment, price_sensitivity
    """
    result = get_ml_scores(pnr_loctr_id)
    return result if result else {}


@mcp.tool()
def mcp_get_enriched_pnr(pnr_loctr_id: str) -> dict:
    """
    Get fully enriched PNR with customer, flight, and ML data.

    This is the main tool used by the agent pipeline - combines:
    - PNR data (sbpnr_prod_pkg.PNR_AIR_SEG)
    - Customer data (custlylty_prod_pkg via LYLTY_ACCT_ID)
    - Flight data (fltcorepkg_prod_pkg_pii via OPERAT_FLIGHT_NBR)
    - ML scores (ML Model Serving)

    Args:
        pnr_loctr_id: PNR locator code (e.g., "ABC123")

    Returns:
        Combined object with pnr, customer, flight, and ml_scores
    """
    result = get_enriched_pnr(pnr_loctr_id)
    return result if result else {}


@mcp.tool()
def mcp_get_eligible_pnrs() -> list:
    """
    Get all PNRs eligible for offer evaluation.

    In production: Triggered by orchestration layer filtering flights
    that need treatment and their associated PNRs.

    Returns:
        List of eligible reservation records
    """
    return get_all_eligible_pnrs()


if __name__ == "__main__":
    # Run with stdio transport (for subprocess communication)
    # For HTTP transport, use: mcp.run(transport="streamable-http", port=8001)
    mcp.run(transport="stdio")
