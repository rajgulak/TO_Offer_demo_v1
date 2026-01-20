"""
LLM Response Validation Module

Provides semantic validation for LLM outputs:
- Structure validation (required fields, types)
- Business logic validation (guardrails, constraints)
- Semantic validation (content quality, coherence)
"""

import re
import json
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum

from .logging import get_logger
from .metrics import metrics

logger = get_logger("validation")


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    ERROR = "error"      # Must be fixed, use fallback
    WARNING = "warning"  # Log but proceed
    INFO = "info"        # Informational only


@dataclass
class ValidationIssue:
    """A single validation issue."""
    field: str
    message: str
    severity: ValidationSeverity
    actual_value: Any = None
    expected: Any = None


@dataclass
class ValidationResult:
    """Result of validation containing all issues found."""
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    validated_data: Optional[Dict[str, Any]] = None

    @property
    def errors(self) -> List[ValidationIssue]:
        """Get only error-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> List[ValidationIssue]:
        """Get only warning-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    def add_issue(
        self,
        field: str,
        message: str,
        severity: ValidationSeverity = ValidationSeverity.ERROR,
        actual_value: Any = None,
        expected: Any = None,
    ):
        """Add a validation issue."""
        self.issues.append(ValidationIssue(
            field=field,
            message=message,
            severity=severity,
            actual_value=actual_value,
            expected=expected,
        ))
        if severity == ValidationSeverity.ERROR:
            self.is_valid = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "is_valid": self.is_valid,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues": [
                {
                    "field": i.field,
                    "message": i.message,
                    "severity": i.severity.value,
                }
                for i in self.issues
            ],
        }


class LLMResponseValidator:
    """
    Validator for LLM response outputs.

    Provides validation for:
    - JSON structure
    - Required fields
    - Value constraints
    - Business logic rules
    """

    def __init__(self, agent_name: str):
        self.agent_name = agent_name

    def validate(
        self,
        response: Any,
        schema: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """
        Validate an LLM response against a schema.

        Args:
            response: The parsed LLM response (dict or raw string)
            schema: Validation schema with field definitions
            context: Optional context for contextual validation

        Returns:
            ValidationResult with validation status and issues
        """
        result = ValidationResult(is_valid=True)

        # Parse if string
        if isinstance(response, str):
            try:
                response = self._parse_json(response)
            except json.JSONDecodeError as e:
                result.add_issue(
                    field="_raw",
                    message=f"Failed to parse JSON: {str(e)}",
                    severity=ValidationSeverity.ERROR,
                )
                return result

        if not isinstance(response, dict):
            result.add_issue(
                field="_type",
                message=f"Expected dict, got {type(response).__name__}",
                severity=ValidationSeverity.ERROR,
            )
            return result

        # Validate each field in schema
        for field_name, field_schema in schema.items():
            self._validate_field(result, response, field_name, field_schema, context)

        # Store validated data
        result.validated_data = response

        # Record metrics
        metrics.record_validation(self.agent_name, result.is_valid)

        # Log validation result
        if not result.is_valid:
            logger.warning(
                "validation_failed",
                agent=self.agent_name,
                errors=[i.message for i in result.errors],
            )

        return result

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Parse JSON from LLM response text."""
        # Try to find JSON in code blocks
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))

        # Try to find raw JSON
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])

        raise json.JSONDecodeError("No JSON found", text, 0)

    def _validate_field(
        self,
        result: ValidationResult,
        data: Dict[str, Any],
        field_name: str,
        schema: Dict[str, Any],
        context: Optional[Dict[str, Any]],
    ):
        """Validate a single field against its schema."""
        value = data.get(field_name)

        # Check required
        if schema.get("required", False) and value is None:
            result.add_issue(
                field=field_name,
                message=f"Required field '{field_name}' is missing",
                severity=ValidationSeverity.ERROR,
            )
            return

        if value is None:
            return  # Optional field not present

        # Check type
        expected_type = schema.get("type")
        if expected_type:
            if not self._check_type(value, expected_type):
                result.add_issue(
                    field=field_name,
                    message=f"Expected type {expected_type}, got {type(value).__name__}",
                    severity=ValidationSeverity.ERROR,
                    actual_value=type(value).__name__,
                    expected=expected_type,
                )
                return

        # Check enum values
        if "enum" in schema:
            if value not in schema["enum"]:
                result.add_issue(
                    field=field_name,
                    message=f"Value '{value}' not in allowed values: {schema['enum']}",
                    severity=ValidationSeverity.ERROR,
                    actual_value=value,
                    expected=schema["enum"],
                )
                return

        # Check min/max for numbers
        if isinstance(value, (int, float)):
            if "min" in schema and value < schema["min"]:
                result.add_issue(
                    field=field_name,
                    message=f"Value {value} is less than minimum {schema['min']}",
                    severity=ValidationSeverity.ERROR,
                    actual_value=value,
                    expected=f">= {schema['min']}",
                )
            if "max" in schema and value > schema["max"]:
                result.add_issue(
                    field=field_name,
                    message=f"Value {value} exceeds maximum {schema['max']}",
                    severity=ValidationSeverity.ERROR,
                    actual_value=value,
                    expected=f"<= {schema['max']}",
                )

        # Check string length
        if isinstance(value, str):
            if "max_length" in schema and len(value) > schema["max_length"]:
                result.add_issue(
                    field=field_name,
                    message=f"String length {len(value)} exceeds max {schema['max_length']}",
                    severity=ValidationSeverity.WARNING,
                    actual_value=len(value),
                    expected=f"<= {schema['max_length']}",
                )

        # Custom validator
        if "validator" in schema:
            custom_result = schema["validator"](value, context)
            if custom_result is not True:
                result.add_issue(
                    field=field_name,
                    message=str(custom_result) if isinstance(custom_result, str) else f"Custom validation failed for '{field_name}'",
                    severity=ValidationSeverity.ERROR,
                    actual_value=value,
                )

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type."""
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        expected = type_map.get(expected_type)
        if expected:
            return isinstance(value, expected)
        return True


# Pre-defined schemas for common validations

OFFER_DECISION_SCHEMA = {
    "selected_offer": {
        "required": True,
        "type": "string",
        "enum": ["IU_BUSINESS", "IU_PREMIUM_ECONOMY", "MCE", "NONE"],
    },
    "offer_price": {
        "required": True,
        "type": "number",
        "min": 0,
        "max": 1000,
    },
    "discount_percent": {
        "required": True,
        "type": "number",
        "min": 0,
        "max": 30,  # No more than 30% discount allowed
    },
    "confidence": {
        "required": False,
        "type": "string",
        "enum": ["high", "medium", "low"],
    },
    "key_factors": {
        "required": False,
        "type": "array",
    },
    "reasoning": {
        "required": False,
        "type": "string",
        "max_length": 2000,
    },
}

PERSONALIZATION_SCHEMA = {
    "subject": {
        "required": True,
        "type": "string",
        "max_length": 100,
    },
    "body": {
        "required": True,
        "type": "string",
        "max_length": 1000,
    },
    "tone": {
        "required": False,
        "type": "string",
        "enum": ["professional", "friendly", "urgent", "casual"],
    },
    "cta_text": {
        "required": False,
        "type": "string",
        "max_length": 50,
    },
}


def validate_offer_decision(
    response: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> ValidationResult:
    """
    Validate an offer decision response from the Offer Orchestration agent.

    Args:
        response: The parsed LLM response
        context: Optional context with offer options, customer data

    Returns:
        ValidationResult
    """
    validator = LLMResponseValidator("offer_orchestration")

    # Build schema with context-aware validators
    schema = OFFER_DECISION_SCHEMA.copy()

    # Add guardrail validators based on context
    if context:
        offer_options = context.get("offer_options", [])
        offer_types = [opt["offer_type"] for opt in offer_options]

        if offer_types:
            schema["selected_offer"]["enum"] = offer_types + ["NONE"]

        # Add discount cap validator
        def validate_discount(value, ctx):
            if ctx and "max_discount_percent" in ctx:
                max_discount = ctx["max_discount_percent"]
                if value > max_discount:
                    return f"Discount {value}% exceeds guardrail max {max_discount}%"
            return True

        schema["discount_percent"]["validator"] = validate_discount

    result = validator.validate(response, schema, context)

    # Additional semantic validations
    if result.is_valid and context:
        _validate_ev_logic(result, response, context)

    return result


def _validate_ev_logic(
    result: ValidationResult,
    response: Dict[str, Any],
    context: Dict[str, Any],
):
    """Validate that the selected offer has reasonable EV."""
    selected = response.get("selected_offer")
    if selected == "NONE":
        return

    offer_options = context.get("offer_options", [])

    # Find the selected offer
    selected_opt = None
    for opt in offer_options:
        if opt["offer_type"] == selected:
            selected_opt = opt
            break

    if not selected_opt:
        result.add_issue(
            field="selected_offer",
            message=f"Selected offer '{selected}' not found in available options",
            severity=ValidationSeverity.WARNING,
        )
        return

    # Check if we selected a much lower EV option
    best_ev = max(opt.get("expected_value", 0) for opt in offer_options)
    selected_ev = selected_opt.get("expected_value", 0)

    if best_ev > 0 and selected_ev < best_ev * 0.5:
        result.add_issue(
            field="selected_offer",
            message=f"Selected offer EV (${selected_ev:.0f}) is less than half of best option (${best_ev:.0f})",
            severity=ValidationSeverity.WARNING,
            actual_value=selected_ev,
            expected=best_ev,
        )


def validate_personalization_response(
    response: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> ValidationResult:
    """
    Validate a personalization response from the Personalization agent.

    Args:
        response: The parsed LLM response
        context: Optional context with customer name, offer details

    Returns:
        ValidationResult
    """
    validator = LLMResponseValidator("personalization")
    result = validator.validate(response, PERSONALIZATION_SCHEMA, context)

    # Additional semantic validations
    if result.is_valid and context:
        _validate_personalization_content(result, response, context)

    return result


def _validate_personalization_content(
    result: ValidationResult,
    response: Dict[str, Any],
    context: Dict[str, Any],
):
    """Validate personalization content quality."""
    body = response.get("body", "")
    customer_name = context.get("customer_name", "")
    offer_type = context.get("offer_type", "")

    # Check if customer name is mentioned (if provided)
    if customer_name and customer_name.lower() not in body.lower():
        result.add_issue(
            field="body",
            message=f"Customer name '{customer_name}' not found in message body",
            severity=ValidationSeverity.WARNING,
        )

    # Check if offer is mentioned
    offer_keywords = {
        "IU_BUSINESS": ["business", "business class", "first class"],
        "IU_PREMIUM_ECONOMY": ["premium", "premium economy", "extra legroom"],
        "MCE": ["main cabin extra", "mce", "extra", "comfort"],
    }

    if offer_type in offer_keywords:
        keywords = offer_keywords[offer_type]
        if not any(kw.lower() in body.lower() for kw in keywords):
            result.add_issue(
                field="body",
                message=f"Offer type '{offer_type}' keywords not found in message",
                severity=ValidationSeverity.WARNING,
            )

    # Check for placeholder text
    placeholder_patterns = [
        r'\[.*?\]',  # [PLACEHOLDER]
        r'\{.*?\}',  # {PLACEHOLDER}
        r'<.*?>',    # <PLACEHOLDER>
        r'XXX',
        r'TODO',
    ]

    for pattern in placeholder_patterns:
        if re.search(pattern, body):
            result.add_issue(
                field="body",
                message=f"Message contains placeholder text matching pattern '{pattern}'",
                severity=ValidationSeverity.ERROR,
            )
            break
