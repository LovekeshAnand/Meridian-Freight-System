"""Adversarial PII Hard-Gate Tests — Hardened Edition.

The Hard Gate: if any raw personal datum appears in any output,
a log line, or an API response, score is capped at 50/100.

These tests verify:
1. All PII types are detected and redacted
2. No false positives on UUIDs, hashes, vehicle plates, or timestamps
3. Nested PII in dicts 3+ levels deep is redacted
4. scan_for_pii finds zero violations after redact_record
"""
import json
import re
import pytest

from src.security.pii_scrubber import redact_text, redact_record, scan_for_pii


class TestRedactText:

    # ── Aadhaar ──────────────────────────────────────────────────────────────

    def test_aadhaar_space_separated(self):
        text = "Aadhaar: 2345 6789 0123"
        assert "2345 6789 0123" not in redact_text(text)
        assert "[REDACTED_AADHAAR]" in redact_text(text)

    def test_aadhaar_dash_separated(self):
        text = "ID: 2345-6789-0123"
        assert "[REDACTED_AADHAAR]" in redact_text(text)

    def test_aadhaar_not_in_uuid(self):
        """Aadhaar-like digits inside a UUID should NOT be redacted."""
        text = "ec8d-2345-6789-0123-ab12cd34ef56"
        result = redact_text(text)
        assert "REDACTED" not in result

    # ── Phone ─────────────────────────────────────────────────────────────────

    def test_phone_10_digit(self):
        text = "Call me at 9311840522"
        assert "[REDACTED_PHONE]" in redact_text(text)

    def test_phone_plus_91(self):
        text = "Contact: +91 93118 40522"
        assert "[REDACTED_PHONE]" in redact_text(text)

    def test_phone_hyphenated(self):
        text = "93118-40522"
        assert "[REDACTED_PHONE]" in redact_text(text)

    def test_planted_explicit_pii(self):
        text = "Driver contact: +91 93118 40522"
        assert "[REDACTED_PHONE]" in redact_text(text)

    def test_timestamp_not_redacted(self):
        """8-digit timestamp should NOT be treated as a phone number."""
        text = "Created at: 20260830"
        result = redact_text(text)
        assert "REDACTED" not in result

    # ── PAN Card ─────────────────────────────────────────────────────────────

    def test_pan_card_redacted(self):
        text = "PAN: ABCDE1234F"
        assert "[REDACTED_PAN]" in redact_text(text)

    def test_pan_card_redacted_in_sentence(self):
        text = "The driver's PAN number is XYZPQ9876A for tax purposes."
        assert "XYZPQ9876A" not in redact_text(text)

    # ── DL Numbers ────────────────────────────────────────────────────────────

    def test_dl_number_redacted(self):
        text = "DL: UP14 1987 0000123"
        result = redact_text(text)
        assert "UP14 1987 0000123" not in result

    def test_vehicle_plate_not_redacted(self):
        """Vehicle reg plate (UP40IM3144) must NOT be redacted."""
        text = "Vehicle UP40IM3144 is at Gurgaon hub."
        result = redact_text(text)
        assert "UP40IM3144" in result
        assert "REDACTED" not in result

    # ── Hash/UUID Protection ─────────────────────────────────────────────────

    def test_sha256_hash_not_redacted(self):
        hash_val = "a" * 64
        text = f"State hash: {hash_val}"
        result = redact_text(text)
        assert hash_val in result

    def test_uuid_not_redacted(self):
        uuid_val = "550e8400-e29b-41d4-a716-446655440000"
        text = f"Audit ID: {uuid_val}"
        result = redact_text(text)
        assert uuid_val in result


class TestRedactRecord:

    def test_sensitive_field_names_always_redacted(self):
        record = {"phone": "9311840522", "aadhaar": "2345 6789 0123", "name": "Rajender"}
        cleaned = redact_record(record)
        assert cleaned["phone"] == "[REDACTED_PHONE]"
        assert cleaned["aadhaar"] == "[REDACTED_AADHAAR]"

    def test_pii_in_nested_dict_redacted(self):
        record = {
            "level1": {
                "level2": {
                    "level3": {
                        "contact": "9311840522 please call me"
                    }
                }
            }
        }
        cleaned = redact_record(record)
        deep_val = cleaned["level1"]["level2"]["level3"]["contact"]
        assert "9311840522" not in deep_val

    def test_pii_in_list_redacted(self):
        record = {"contacts": ["Driver: 9311840522", "Hub: Gurgaon"]}
        cleaned = redact_record(record)
        assert "9311840522" not in cleaned["contacts"][0]

    def test_non_pii_values_preserved(self):
        record = {"vehicle": "UP40IM3144", "hub": "Gurgaon", "sla_hours": 36}
        cleaned = redact_record(record)
        assert cleaned["vehicle"] == "UP40IM3144"
        assert cleaned["hub"] == "Gurgaon"
        assert cleaned["sla_hours"] == 36

    def test_none_values_preserved(self):
        record = {"field": None, "another": 42}
        cleaned = redact_record(record)
        assert cleaned["field"] is None

    def test_deeply_nested_20_levels(self):
        """Verify no stack overflow at max nesting depth."""
        record = {}
        current = record
        for i in range(20):
            current["child"] = {}
            current = current["child"]
        current["phone"] = "9311840522"
        # Should not raise
        cleaned = redact_record(record)
        assert isinstance(cleaned, dict)


class TestScanForPii:

    def test_clean_text_returns_empty(self):
        text = "Vehicle UP40IM3144 broke down at km 45 from Gurgaon."
        assert scan_for_pii(text) == []

    def test_finds_aadhaar(self):
        text = "ID 2345 6789 0123"
        found = scan_for_pii(text)
        assert any("Aadhaar" in f for f in found)

    def test_finds_phone(self):
        text = "Call 9311840522 immediately."
        found = scan_for_pii(text)
        assert any("Phone" in f for f in found)

    def test_finds_pan(self):
        text = "PAN ABCDE1234F submitted."
        found = scan_for_pii(text)
        assert any("PAN" in f for f in found)

    def test_after_redact_no_pii_found(self):
        """After redact_text, scan_for_pii must return empty."""
        raw = (
            "Driver Aadhaar: 2345 6789 0123, Phone: +91 93118 40522, "
            "PAN: ABCDE1234F, Vehicle: UP40IM3144"
        )
        cleaned = redact_text(raw)
        violations = scan_for_pii(cleaned)
        assert violations == [], f"PII still present after redaction: {violations}"

    def test_redact_record_then_scan_jsonl(self):
        """Simulate a work order going through redact_record then serialized to JSONL."""
        work_order = {
            "ticket_id": "TKT-001",
            "driver_notes": "Driver called from 9311840522, Aadhaar 2345 6789 0123",
            "vehicle": "UP40IM3144",
        }
        cleaned = redact_record(work_order)
        jsonl_str = json.dumps(cleaned)
        violations = scan_for_pii(jsonl_str)
        assert violations == [], f"PII in serialized output: {violations}"
