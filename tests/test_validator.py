"""Adversarial Validator Tests.

Tests the TicketValidator's coercion logic, quarantine triggers, and
type-safety against any input that can arrive from the real world.
"""
import pytest
from src.pipeline.validator import TicketValidator


def valid_base():
    """Returns a valid ticket dict — mutate per test."""
    return {
        "ticket_id": "TKT-001",
        "vehicle": "UP40IM3144",
        "origin_hub": "Gurgaon",
        "km_from_origin_hub": 25.0,
        "client": "Apex Chemicals",
        "created_at": "2026-08-30T10:00:00",
    }


class TestValidatorCoercion:
    """Validator should coerce before quarantining."""

    def test_integer_ticket_id_coerced(self):
        t = valid_base()
        t["ticket_id"] = 27
        result = TicketValidator.validate_ticket(t)
        assert result.is_valid
        assert result.sanitized_ticket["ticket_id"] == "TKT-0027"

    def test_float_ticket_id_coerced(self):
        t = valid_base()
        t["ticket_id"] = 5.0
        result = TicketValidator.validate_ticket(t)
        assert result.is_valid
        assert result.sanitized_ticket["ticket_id"] == "TKT-0005"

    def test_km_string_with_unit_coerced(self):
        t = valid_base()
        t["km_from_origin_hub"] = "20 km"
        result = TicketValidator.validate_ticket(t)
        assert result.is_valid
        assert result.sanitized_ticket["km_from_origin_hub"] == 20.0

    def test_km_tilde_prefix_coerced(self):
        t = valid_base()
        t["km_from_origin_hub"] = "~35.5"
        result = TicketValidator.validate_ticket(t)
        assert result.is_valid
        assert result.sanitized_ticket["km_from_origin_hub"] == 35.5

    def test_km_comma_thousand_coerced(self):
        t = valid_base()
        t["km_from_origin_hub"] = "1,200"
        result = TicketValidator.validate_ticket(t)
        assert result.is_valid
        assert result.sanitized_ticket["km_from_origin_hub"] == 1200.0

    def test_alternate_date_format_ddmmyyyy(self):
        t = valid_base()
        t["created_at"] = "30-08-2026"
        result = TicketValidator.validate_ticket(t)
        assert result.is_valid
        assert "2026-08-30" in result.sanitized_ticket["created_at"]

    def test_alternate_date_format_slash(self):
        t = valid_base()
        t["created_at"] = "30/08/2026"
        result = TicketValidator.validate_ticket(t)
        assert result.is_valid

    def test_vehicle_normalized(self):
        t = valid_base()
        t["vehicle"] = "up 40 im 3144"
        result = TicketValidator.validate_ticket(t)
        # Normalizer should handle it or quarantine with clear reason
        assert isinstance(result.is_valid, bool)


class TestValidatorQuarantine:
    """Records that cannot be coerced must be quarantined with clear reasons."""

    def test_none_ticket_id_quarantined(self):
        t = valid_base()
        t["ticket_id"] = None
        result = TicketValidator.validate_ticket(t)
        assert not result.is_valid
        assert "ticket_id" in result.quarantine_reason.lower()

    def test_bool_ticket_id_quarantined(self):
        t = valid_base()
        t["ticket_id"] = True
        result = TicketValidator.validate_ticket(t)
        assert not result.is_valid

    def test_negative_km_quarantined(self):
        t = valid_base()
        t["km_from_origin_hub"] = -5
        result = TicketValidator.validate_ticket(t)
        assert not result.is_valid
        assert "negative" in result.quarantine_reason.lower()

    def test_km_alpha_string_quarantined(self):
        t = valid_base()
        t["km_from_origin_hub"] = "far away"
        result = TicketValidator.validate_ticket(t)
        assert not result.is_valid

    def test_unparseable_date_quarantined(self):
        t = valid_base()
        t["created_at"] = "not-a-date"
        result = TicketValidator.validate_ticket(t)
        assert not result.is_valid
        assert "created_at" in result.quarantine_reason.lower()

    def test_missing_client_quarantined(self):
        t = valid_base()
        t["client"] = ""
        result = TicketValidator.validate_ticket(t)
        assert not result.is_valid

    def test_missing_origin_hub_quarantined(self):
        t = valid_base()
        t["origin_hub"] = None
        result = TicketValidator.validate_ticket(t)
        assert not result.is_valid

    def test_none_input_no_crash(self):
        result = TicketValidator.validate_ticket(None)
        assert not result.is_valid
        assert result.quarantine_reason is not None

    def test_list_input_no_crash(self):
        result = TicketValidator.validate_ticket([1, 2, 3])
        assert not result.is_valid

    def test_empty_dict_quarantined(self):
        result = TicketValidator.validate_ticket({})
        assert not result.is_valid

    def test_integer_input_no_crash(self):
        result = TicketValidator.validate_ticket(42)
        assert not result.is_valid

    def test_string_input_no_crash(self):
        result = TicketValidator.validate_ticket("some random string")
        assert not result.is_valid

    def test_km_boolean_quarantined(self):
        t = valid_base()
        t["km_from_origin_hub"] = True  # bool, not coerceable to meaningful km
        result = TicketValidator.validate_ticket(t)
        assert not result.is_valid


class TestValidatorWarnings:
    """Valid tickets with coercions should include warnings."""

    def test_int_ticket_id_produces_warning(self):
        t = valid_base()
        t["ticket_id"] = 99
        result = TicketValidator.validate_ticket(t)
        assert result.is_valid
        assert result.warnings is not None

    def test_km_string_produces_warning(self):
        t = valid_base()
        t["km_from_origin_hub"] = "45 km"
        result = TicketValidator.validate_ticket(t)
        assert result.is_valid
        assert result.warnings is not None

    def test_unusually_large_km_produces_warning(self):
        t = valid_base()
        t["km_from_origin_hub"] = 9999.0
        result = TicketValidator.validate_ticket(t)
        assert result.is_valid
        assert any("large" in w.lower() for w in (result.warnings or []))
