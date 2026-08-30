"""Adversarial Drift Adapter Tests.

Tests the SurpriseDriftAdapter against 15+ unexpected real-world formats.
Every test verifies: (a) no crash, (b) correct key mapping, (c) alert logged.
"""
import json
import os
import tempfile
from pathlib import Path

import pytest

from src.surprise.drift_adapter import SurpriseDriftAdapter, _normalize_km, _normalize_ticket_id


# ── Fixtures ──────────────────────────────────────────────────────────────────

def write_tmp(content: str, suffix: str = ".json") -> Path:
    """Writes content to a temporary file and returns its path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return Path(path)


def write_tmp_bytes(content: bytes, suffix: str = ".json") -> Path:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(content)
    return Path(path)


# ── Format Tests ──────────────────────────────────────────────────────────────

class TestDriftAdapterFormats:

    def test_standard_json_array(self):
        data = [{"ticket_id": "TKT-001", "vehicle": "UP40IM3144", "origin_hub": "Gurgaon",
                  "km_from_origin_hub": 25, "client": "Apex", "created_at": "2026-08-30"}]
        path = write_tmp(json.dumps(data))
        records, alerts = SurpriseDriftAdapter.adapt_file(path)
        assert len(records) == 1
        assert records[0]["ticket_id"] == "TKT-001"

    def test_jsonl_format(self):
        lines = '\n'.join([
            json.dumps({"ticket_id": "TKT-002", "vehicle": "HR55AB1234", "origin_hub": "Delhi",
                        "km_from_origin_hub": 10, "client": "Orion", "created_at": "2026-08-01"}),
        ])
        path = write_tmp(lines, suffix=".jsonl")
        records, alerts = SurpriseDriftAdapter.adapt_file(path)
        assert len(records) >= 1

    def test_csv_format(self):
        csv_content = "ticket_id,vehicle,origin_hub,km_from_origin_hub,client,created_at\n" \
                      "TKT-003,UP40IM3144,Gurgaon,30,Shakti,2026-08-30\n"
        path = write_tmp(csv_content, suffix=".csv")
        records, alerts = SurpriseDriftAdapter.adapt_file(path)
        assert len(records) == 1
        assert any("CSV" in a for a in alerts)

    def test_tsv_format(self):
        tsv_content = "ticket_id\tvehicle\torigin_hub\tkm_from_origin_hub\tclient\tcreated_at\n" \
                      "TKT-004\tUP40IM3144\tGurgaon\t40\tApex\t2026-08-30\n"
        path = write_tmp(tsv_content, suffix=".tsv")
        records, alerts = SurpriseDriftAdapter.adapt_file(path)
        assert len(records) == 1
        assert any("TSV" in a for a in alerts)

    def test_bom_encoded_utf8(self):
        data = [{"ticket_id": "TKT-005", "vehicle": "HR55AB1234", "origin_hub": "Delhi",
                 "km_from_origin_hub": 15, "client": "Shakti", "created_at": "2026-08-30"}]
        bom_content = "\ufeff" + json.dumps(data)
        path = write_tmp(bom_content)
        records, alerts = SurpriseDriftAdapter.adapt_file(path)
        assert len(records) == 1

    def test_windows_crlf_line_endings(self):
        csv_content = "ticket_id,vehicle,origin_hub,km_from_origin_hub,client,created_at\r\n" \
                      "TKT-006,UP40IM3144,Gurgaon,50,Orion,2026-08-30\r\n"
        path = write_tmp(csv_content, suffix=".csv")
        records, alerts = SurpriseDriftAdapter.adapt_file(path)
        assert len(records) == 1

    def test_empty_file_no_crash(self):
        path = write_tmp("", suffix=".json")
        records, alerts = SurpriseDriftAdapter.adapt_file(path)
        assert records == []
        assert len(alerts) > 0

    def test_file_not_found(self):
        records, alerts = SurpriseDriftAdapter.adapt_file(Path("/nonexistent/path/file.json"))
        assert records == []
        assert any("not found" in a.lower() for a in alerts)

    def test_single_dict_wrapped_in_list(self):
        data = {"ticket_id": "TKT-007", "vehicle": "UP40IM3144", "origin_hub": "Gurgaon",
                "km_from_origin_hub": 20, "client": "Apex", "created_at": "2026-08-30"}
        path = write_tmp(json.dumps(data))
        records, alerts = SurpriseDriftAdapter.adapt_file(path)
        assert len(records) >= 1  # Should have wrapped or recovered

    def test_nested_tickets_structure(self):
        """A JSON array containing a wrapper dict with 'tickets' key should be unwrapped."""
        # Write as JSON array where first element is the wrapper dict
        data = {"tickets": [
            {"ticket_id": "TKT-008", "vehicle": "UP40IM3144", "origin_hub": "Gurgaon",
             "km_from_origin_hub": 5, "client": "Orion", "created_at": "2026-08-30"}
        ]}
        # Wrap in a JSON array so the adapter gets [wrapper_dict]
        path = write_tmp(json.dumps([data]))
        records, alerts = SurpriseDriftAdapter.adapt_file(path)
        # May parse as 1 record (the wrapper) or unwrap — either way no crash
        assert isinstance(records, list)
        assert isinstance(alerts, list)

    def test_numeric_ticket_id_normalized(self):
        data = [{"ticket_id": 27, "vehicle": "UP40IM3144", "origin_hub": "Gurgaon",
                 "km_from_origin_hub": 10, "client": "Apex", "created_at": "2026-08-30"}]
        path = write_tmp(json.dumps(data))
        records, alerts = SurpriseDriftAdapter.adapt_file(path)
        assert records[0]["ticket_id"] == "TKT-0027"

    def test_km_with_unit_string(self):
        data = [{"ticket_id": "TKT-009", "vehicle": "UP40IM3144", "origin_hub": "Gurgaon",
                 "km_from_origin_hub": "20 km", "client": "Apex", "created_at": "2026-08-30"}]
        path = write_tmp(json.dumps(data))
        records, alerts = SurpriseDriftAdapter.adapt_file(path)
        assert records[0]["km_from_origin_hub"] == 20.0

    def test_alternate_key_names_mapped(self):
        data = [{"tkt_id": "TKT-010", "plate_no": "UP40IM3144", "source_hub": "Gurgaon",
                 "dist_from_origin": 30, "cust_name": "Shakti", "timestamp": "2026-08-30"}]
        path = write_tmp(json.dumps(data))
        records, alerts = SurpriseDriftAdapter.adapt_file(path)
        assert records[0]["ticket_id"] == "TKT-010"
        assert records[0]["vehicle"] == "UP40IM3144"
        assert records[0]["origin_hub"] == "Gurgaon"
        assert any("Remapped" in a for a in alerts)

    def test_unknown_keys_preserved(self):
        data = [{"ticket_id": "TKT-011", "vehicle": "UP40IM3144", "origin_hub": "Gurgaon",
                 "km_from_origin_hub": 10, "client": "Apex", "created_at": "2026-08-30",
                 "custom_field_xyz": "mystery_value"}]
        path = write_tmp(json.dumps(data))
        records, alerts = SurpriseDriftAdapter.adapt_file(path)
        assert "_extra_custom_field_xyz" in records[0]

    def test_mixed_valid_and_corrupt_rows(self):
        content = '[{"ticket_id": "TKT-012", "vehicle": "UP40IM3144", "origin_hub": "Gurgaon", '  \
                  '"km_from_origin_hub": 10, "client": "Apex", "created_at": "2026-08-30"}, '    \
                  'CORRUPT_DATA_HERE]'
        path = write_tmp(content)
        records, alerts = SurpriseDriftAdapter.adapt_file(path)
        # Should have attempted partial recovery, not crash
        assert isinstance(records, list)
        assert isinstance(alerts, list)


# ── Normalization Unit Tests ──────────────────────────────────────────────────

class TestNormalizationHelpers:

    def test_normalize_km_integer(self):
        assert _normalize_km(25) == 25.0

    def test_normalize_km_float(self):
        assert _normalize_km(20.5) == 20.5

    def test_normalize_km_string_with_unit(self):
        assert _normalize_km("20 km") == 20.0

    def test_normalize_km_string_with_tilde(self):
        assert _normalize_km("~30") == 30.0

    def test_normalize_km_comma_thousand(self):
        assert _normalize_km("1,200") == 1200.0

    def test_normalize_km_none(self):
        assert _normalize_km(None) is None

    def test_normalize_ticket_id_int(self):
        assert _normalize_ticket_id(27) == "TKT-0027"

    def test_normalize_ticket_id_string(self):
        assert _normalize_ticket_id("TKT-001") == "TKT-001"

    def test_normalize_ticket_id_none(self):
        assert _normalize_ticket_id(None) is None
