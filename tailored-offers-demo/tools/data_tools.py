"""
Data access tools for Tailored Offers Demo
These simulate API calls to various data sources

Field names match the Tailored Offers Data Mapping Excel specification
"""
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

DATA_DIR = Path(__file__).parent.parent / "data"


def _load_json(filename: str) -> Any:
    """Load JSON data from file"""
    with open(DATA_DIR / filename, "r") as f:
        return json.load(f)


def get_customer(lylty_acct_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve customer profile data by LYLTY_ACCT_ID

    In production: Calls North Star Data Platform / Customer 360
    Source: PROD_LYLTY_METRICS_VW, custlylty_prod_pkg
    """
    customers = _load_json("customers.json")
    for customer in customers:
        if customer["lylty_acct_id"] == lylty_acct_id:
            return customer
    return None


def get_flight(operat_flight_nbr: int, leg_dep_dt: str = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve flight and inventory data by Operating Flight Number

    In production: Calls Flight Operations / fltcorepkg_prod_pkg_pii
    Source: flight_leg_nrt table
    """
    flights = _load_json("flights.json")
    for flight in flights:
        if flight["operat_flight_nbr"] == operat_flight_nbr:
            if leg_dep_dt is None or flight["leg_dep_dt"] == leg_dep_dt:
                return flight
    return None


def get_reservation(pnr_loctr_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve reservation/PNR data by PNR_LOCTR_ID

    In production: Calls sbpnr_prod_pkg / PNR_AIR_SEG
    Source: Streaming NRT (30 minutes)
    """
    reservations = _load_json("reservations.json")
    for reservation in reservations:
        if reservation["pnr_loctr_id"] == pnr_loctr_id:
            return reservation
    return None


def get_ml_scores(pnr_loctr_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve ML propensity scores for a PNR

    In production: Calls ML Model Serving API (the P(buy) model)
    Returns P(buy) at different price points for each product
    """
    ml_data = _load_json("ml_scores.json")
    return ml_data["scores"].get(pnr_loctr_id)


def get_all_customers() -> List[Dict[str, Any]]:
    """Get all customers"""
    return _load_json("customers.json")


def get_all_flights() -> List[Dict[str, Any]]:
    """Get all flights"""
    return _load_json("flights.json")


def get_all_reservations() -> List[Dict[str, Any]]:
    """Get all reservations"""
    return _load_json("reservations.json")


def get_all_eligible_pnrs() -> List[Dict[str, Any]]:
    """
    Get all PNRs eligible for offer evaluation

    In production: This would be triggered by the orchestration layer
    filtering flights that need treatment and their associated PNRs
    """
    reservations = _load_json("reservations.json")
    eligible = []

    for res in reservations:
        # Basic eligibility: main cabin (Y), not checked in, has time
        if res["max_bkd_cabin_cd"] == "Y" and not res["checked_in"]:
            if res["hours_to_departure"] >= 24:
                eligible.append(res)

    return eligible


def get_enriched_pnr(pnr_loctr_id: str) -> Optional[Dict[str, Any]]:
    """
    Get fully enriched PNR with customer, flight, and ML data

    This combines data from multiple sources - what the agents will work with
    Joins:
      - PNR data (sbpnr_prod_pkg.PNR_AIR_SEG)
      - Customer data (custlylty_prod_pkg via LYLTY_ACCT_ID)
      - Flight data (fltcorepkg_prod_pkg_pii via OPERAT_FLIGHT_NBR)
      - ML scores (ML Model Serving)
    """
    reservation = get_reservation(pnr_loctr_id)
    if not reservation:
        return None

    customer = get_customer(reservation["lylty_acct_id"])
    # Don't filter by date for demo - just match by flight number
    flight = get_flight(reservation["operat_flight_nbr"])
    ml_scores = get_ml_scores(pnr_loctr_id)

    return {
        "pnr": reservation,
        "customer": customer,
        "flight": flight,
        "ml_scores": ml_scores
    }
