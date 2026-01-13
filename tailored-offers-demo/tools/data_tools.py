"""
Data access tools for Tailored Offers Demo
These simulate API calls to various data sources
"""
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

DATA_DIR = Path(__file__).parent.parent / "data"


def _load_json(filename: str) -> Any:
    """Load JSON data from file"""
    with open(DATA_DIR / filename, "r") as f:
        return json.load(f)


def get_customer(customer_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve customer profile data

    In production: Calls North Star Data Platform / Customer 360
    """
    customers = _load_json("customers.json")
    for customer in customers:
        if customer["customer_id"] == customer_id:
            return customer
    return None


def get_customer_by_aadv(aadv_number: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve customer by AAdvantage number
    """
    customers = _load_json("customers.json")
    for customer in customers:
        if customer["aadv_number"] == aadv_number:
            return customer
    return None


def get_flight(flight_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve flight and inventory data

    In production: Calls Flight Operations / Inventory Management System
    """
    flights = _load_json("flights.json")
    for flight in flights:
        if flight["flight_id"] == flight_id:
            return flight
    return None


def get_reservation(pnr_locator: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve reservation/PNR data

    In production: Calls Reservation System / PNR Database
    """
    reservations = _load_json("reservations.json")
    for reservation in reservations:
        if reservation["pnr_locator"] == pnr_locator:
            return reservation
    return None


def get_ml_scores(pnr_locator: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve ML propensity scores for a PNR

    In production: Calls ML Model Serving API (the P(buy) model)
    """
    ml_data = _load_json("ml_scores.json")
    return ml_data["scores"].get(pnr_locator)


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
        # Basic eligibility: main cabin, not checked in, has time
        if res["current_cabin"] == "main_cabin" and not res["checked_in"]:
            if res["hours_to_departure"] >= 24:
                eligible.append(res)

    return eligible


def get_enriched_pnr(pnr_locator: str) -> Optional[Dict[str, Any]]:
    """
    Get fully enriched PNR with customer, flight, and ML data

    This combines data from multiple sources - what the agents will work with
    """
    reservation = get_reservation(pnr_locator)
    if not reservation:
        return None

    customer = get_customer(reservation["customer_id"])
    flight = get_flight(reservation["flight_id"])
    ml_scores = get_ml_scores(pnr_locator)

    return {
        "pnr": reservation,
        "customer": customer,
        "flight": flight,
        "ml_scores": ml_scores
    }
