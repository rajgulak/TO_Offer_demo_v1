"""
Policy Configuration Service

Manages business policy values that control agent behavior.
These are actual configuration values, not prompt text.

Examples:
- goodwill_discount_percent: 10
- max_discount_percent: 25
- min_confidence_threshold: 0.6
- vip_revenue_threshold: 5000
"""

import json
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict

# Default policy values
DEFAULT_POLICY = {
    # Discount policies
    "goodwill_discount_percent": 10,
    "max_discount_percent": 25,
    "min_discount_percent": 5,
    "vip_discount_percent": 15,

    # Confidence thresholds
    "min_confidence_threshold": 0.6,
    "high_confidence_threshold": 0.8,

    # Customer thresholds
    "vip_revenue_threshold": 5000,
    "loyalty_tenure_days_threshold": 365,

    # Offer policies
    "max_offers_per_day": 3,
    "min_hours_before_departure": 24,
    "suppress_after_complaint_days": 30,

    # Pricing policies
    "business_upgrade_base_price": 499,
    "premium_economy_upgrade_base_price": 199,
    "mce_base_price": 99,
}

# Policy metadata for validation and display
POLICY_METADATA = {
    "goodwill_discount_percent": {
        "name": "Goodwill Discount",
        "description": "Discount percentage for customers with recent issues",
        "type": "percent",
        "min": 0,
        "max": 50,
        "unit": "%"
    },
    "max_discount_percent": {
        "name": "Maximum Discount",
        "description": "Maximum discount that can be applied",
        "type": "percent",
        "min": 0,
        "max": 75,
        "unit": "%"
    },
    "min_discount_percent": {
        "name": "Minimum Discount",
        "description": "Minimum discount to offer",
        "type": "percent",
        "min": 0,
        "max": 25,
        "unit": "%"
    },
    "vip_discount_percent": {
        "name": "VIP Discount",
        "description": "Special discount for VIP/Executive Platinum customers",
        "type": "percent",
        "min": 0,
        "max": 50,
        "unit": "%"
    },
    "min_confidence_threshold": {
        "name": "Minimum Confidence",
        "description": "Minimum ML confidence score to make an offer",
        "type": "decimal",
        "min": 0,
        "max": 1,
        "unit": ""
    },
    "high_confidence_threshold": {
        "name": "High Confidence",
        "description": "Threshold for high-confidence offers",
        "type": "decimal",
        "min": 0,
        "max": 1,
        "unit": ""
    },
    "vip_revenue_threshold": {
        "name": "VIP Revenue Threshold",
        "description": "Annual revenue to qualify as VIP",
        "type": "currency",
        "min": 0,
        "max": 100000,
        "unit": "$"
    },
    "loyalty_tenure_days_threshold": {
        "name": "Loyalty Tenure",
        "description": "Days of membership to qualify for loyalty benefits",
        "type": "days",
        "min": 0,
        "max": 3650,
        "unit": " days"
    },
    "max_offers_per_day": {
        "name": "Max Daily Offers",
        "description": "Maximum offers to send per customer per day",
        "type": "integer",
        "min": 1,
        "max": 10,
        "unit": ""
    },
    "min_hours_before_departure": {
        "name": "Min Hours Before Departure",
        "description": "Minimum hours before flight to send offer",
        "type": "hours",
        "min": 1,
        "max": 168,
        "unit": " hours"
    },
    "suppress_after_complaint_days": {
        "name": "Complaint Suppression Period",
        "description": "Days to suppress offers after a complaint",
        "type": "days",
        "min": 0,
        "max": 90,
        "unit": " days"
    },
    "business_upgrade_base_price": {
        "name": "Business Upgrade Price",
        "description": "Base price for business class upgrade",
        "type": "currency",
        "min": 0,
        "max": 2000,
        "unit": "$"
    },
    "premium_economy_upgrade_base_price": {
        "name": "Premium Economy Upgrade Price",
        "description": "Base price for premium economy upgrade",
        "type": "currency",
        "min": 0,
        "max": 1000,
        "unit": "$"
    },
    "mce_base_price": {
        "name": "MCE Price",
        "description": "Base price for Main Cabin Extra",
        "type": "currency",
        "min": 0,
        "max": 500,
        "unit": "$"
    },
}


class PolicyService:
    """Service for managing policy configuration."""

    _config_file = Path(__file__).parent / "custom_policy.json"
    _custom_policy: dict = {}
    _loaded = False

    @classmethod
    def _load(cls):
        """Load custom policy from file."""
        if cls._loaded:
            return

        if cls._config_file.exists():
            try:
                with open(cls._config_file) as f:
                    cls._custom_policy = json.load(f)
            except Exception:
                cls._custom_policy = {}

        cls._loaded = True

    @classmethod
    def _save(cls):
        """Save custom policy to file."""
        with open(cls._config_file, 'w') as f:
            json.dump(cls._custom_policy, f, indent=2)

    @classmethod
    def get(cls, key: str) -> Any:
        """Get a policy value (custom if set, otherwise default)."""
        cls._load()
        if key in cls._custom_policy:
            return cls._custom_policy[key]
        return DEFAULT_POLICY.get(key)

    @classmethod
    def get_all(cls) -> dict:
        """Get all policy values with metadata."""
        cls._load()
        result = {}
        for key, default_value in DEFAULT_POLICY.items():
            current_value = cls._custom_policy.get(key, default_value)
            is_custom = key in cls._custom_policy
            metadata = POLICY_METADATA.get(key, {})

            result[key] = {
                "value": current_value,
                "default": default_value,
                "is_custom": is_custom,
                "name": metadata.get("name", key),
                "description": metadata.get("description", ""),
                "type": metadata.get("type", "string"),
                "min": metadata.get("min"),
                "max": metadata.get("max"),
                "unit": metadata.get("unit", ""),
            }

        return result

    @classmethod
    def set(cls, key: str, value: Any) -> tuple[bool, str]:
        """
        Set a policy value.
        Returns (success, message).
        """
        cls._load()

        if key not in DEFAULT_POLICY:
            return False, f"Unknown policy key: {key}"

        metadata = POLICY_METADATA.get(key, {})

        # Type conversion
        try:
            if metadata.get("type") in ["percent", "integer", "days", "hours"]:
                value = int(value)
            elif metadata.get("type") in ["decimal"]:
                value = float(value)
            elif metadata.get("type") == "currency":
                value = float(value)
        except (ValueError, TypeError):
            return False, f"Invalid value type for {key}"

        # Range validation
        min_val = metadata.get("min")
        max_val = metadata.get("max")
        if min_val is not None and value < min_val:
            return False, f"{metadata.get('name', key)} cannot be less than {min_val}"
        if max_val is not None and value > max_val:
            return False, f"{metadata.get('name', key)} cannot be more than {max_val}"

        # Save
        cls._custom_policy[key] = value
        cls._save()

        unit = metadata.get("unit", "")
        return True, f"{metadata.get('name', key)} updated to {value}{unit}"

    @classmethod
    def reset(cls, key: str) -> tuple[bool, str]:
        """Reset a policy value to default."""
        cls._load()

        if key not in DEFAULT_POLICY:
            return False, f"Unknown policy key: {key}"

        if key in cls._custom_policy:
            del cls._custom_policy[key]
            cls._save()

        metadata = POLICY_METADATA.get(key, {})
        default = DEFAULT_POLICY[key]
        return True, f"{metadata.get('name', key)} reset to default ({default})"

    @classmethod
    def reset_all(cls):
        """Reset all policies to defaults."""
        cls._custom_policy = {}
        cls._save()
        return True, "All policies reset to defaults"


# Convenience functions
def get_policy(key: str) -> Any:
    return PolicyService.get(key)

def set_policy(key: str, value: Any) -> tuple[bool, str]:
    return PolicyService.set(key, value)

def get_all_policies() -> dict:
    return PolicyService.get_all()

def reset_policy(key: str) -> tuple[bool, str]:
    return PolicyService.reset(key)
