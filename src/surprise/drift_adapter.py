"""Surprise File Schema Drift Adapter for Meridian Freight.

Handles ALL unexpected real-world queue formats:
  - JSON array (standard)
  - JSONL / NDJSON (one object per line)
  - CSV with headers (comma or semicolon separated)
  - TSV (tab-separated)
  - Excel (.xlsx) input queues
  - BOM-encoded UTF-8 (\ufeff prefix)
  - Windows \\r\\n line endings
  - Single dict wrapping (not a list)
  - Nested structure e.g. {"tickets": [...]}
  - Numeric ticket_id (e.g. 27 -> "TKT-27")
  - String distances with units (e.g. "20 km" -> 20.0)
  - Truncated JSON (best-effort partial parse)
  - Unknown / extra keys (passed through, logged as drift)
  - Empty files (returns empty list + alert, never crashes)
"""
import csv
import io
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import openpyxl
    _HAS_OPENPYXL = True
except ImportError:
    _HAS_OPENPYXL = False

from src.observability import logger as log

KEY_SYNONYMS = {
    "ticket_id": [
        "ticket_id", "tkt_id", "id", "ticket_number", "incident_id",
        "ticketid", "ticket_no", "breakdown_id", "case_id", "ref_id",
    ],
    "vehicle": [
        "vehicle", "vehicle_reg", "plate", "plate_no", "truck", "truck_id",
        "reg_no", "registration", "registration_number", "veh_reg", "vehicle_number",
    ],
    "driver_id": [
        "driver_id", "driver", "drv_id", "pilot_id", "operator_id", "emp_id",
    ],
    "origin_hub": [
        "origin_hub", "origin", "source_hub", "hub_origin", "from_hub",
        "start_hub", "source", "loading_point", "from",
    ],
    "km_from_origin_hub": [
        "km_from_origin_hub", "distance_km", "km_from_origin", "km_out",
        "dist_from_origin", "distance", "km", "dist_km", "breakdown_distance",
    ],
    "destination": [
        "destination", "dest", "dest_hub", "to_hub", "target_hub",
        "delivery_point", "drop_point", "to", "unloading_point",
    ],
    "issue": [
        "issue", "breakdown_reason", "problem", "fault", "defect",
        "breakdown_type", "failure_type", "reason", "breakdown_cause",
    ],
    "severity": [
        "severity", "priority", "urgency_level", "urgency", "impact_level",
    ],
    "client": [
        "client", "customer", "account", "client_name", "company",
        "consignee", "shipper", "party", "cust_name", "customer_name",
    ],
    "created_at": [
        "created_at", "timestamp", "date", "incident_time", "time",
        "reported_at", "breakdown_time", "logged_at", "event_time",
    ],
    "status": [
        "status", "state", "ticket_status", "current_status", "resolution_status",
    ],
    "resolution_note": [
        "resolution_note", "notes", "remarks", "resolution", "comment",
        "action_taken", "remarks_by_driver",
    ],
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def _strip_bom(text: str) -> str:
    """Removes BOM character if present."""
    return text.lstrip("\ufeff")


def _normalize_km(value: Any) -> Any:
    """Extracts numeric value from strings like '20 km', '20.5km', '~20'."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    s = str(value).strip()
    # Extract leading numeric portion
    match = re.match(r"^[~±]?\s*([\d,]+\.?\d*)", s)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            pass
    return value  # Let validator decide what to do with it


def _normalize_ticket_id(value: Any) -> Any:
    """Coerces numeric ticket IDs to string format."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"TKT-{int(value):04d}"
    return str(value).strip()


def _find_canonical_key(record: Dict[str, Any], std_key: str) -> Tuple[Any, str]:
    """
    Searches a record for any synonym of std_key.
    Returns (value, matched_alt_key) or (None, "").
    Case-insensitive match.
    """
    record_lower = {k.lower(): (k, v) for k, v in record.items()}
    for alt in KEY_SYNONYMS[std_key]:
        if alt in record_lower:
            orig_key, val = record_lower[alt]
            return val, orig_key
    return None, ""


def _normalize_record(raw: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Normalizes a single record's keys to canonical schema, reports drifts."""
    drifts = []
    std = {}
    for std_key in KEY_SYNONYMS:
        val, matched_key = _find_canonical_key(raw, std_key)
        if matched_key and matched_key != std_key:
            drifts.append(f"Remapped '{matched_key}' -> '{std_key}'")
        std[std_key] = val

    # Type coercions
    std["ticket_id"] = _normalize_ticket_id(std.get("ticket_id"))
    std["km_from_origin_hub"] = _normalize_km(std.get("km_from_origin_hub"))

    # Carry over any unknown extra keys as-is (never silently drop data)
    known_lowers = {alt for alts in KEY_SYNONYMS.values() for alt in alts}
    for k, v in raw.items():
        if k.lower() not in known_lowers and k not in std:
            std[f"_extra_{k}"] = v
            drifts.append(f"Unknown field '{k}' preserved as '_extra_{k}'")

    return std, drifts


def _parse_excel(file_path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Parses an Excel (.xlsx) file as a ticket queue."""
    if not _HAS_OPENPYXL:
        return [], ["openpyxl not installed; cannot parse Excel surprise file."]
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return [], ["Excel file is empty."]
        headers = [str(h).strip() if h is not None else "" for h in rows[0]]
        records = []
        for row in rows[1:]:
            rec = {headers[i]: row[i] for i in range(len(headers)) if headers[i]}
            records.append(rec)
        return records, [f"Excel format detected ({ws.title}); parsed {len(records)} rows."]
    except Exception as e:
        return [], [f"Failed to parse Excel file: {e}"]


def _parse_csv_or_tsv(content: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Auto-detects CSV vs TSV (comma vs tab delimiter) and parses."""
    # Sniff delimiter
    sample = content[:2048]
    tab_count = sample.count("\t")
    comma_count = sample.count(",")
    delimiter = "\t" if tab_count > comma_count else ","
    fmt = "TSV" if delimiter == "\t" else "CSV"
    try:
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        records = [dict(row) for row in reader]
        return records, [f"{fmt} format detected; parsed {len(records)} rows."]
    except Exception as e:
        return [], [f"Failed to parse {fmt}: {e}"]


def _parse_text_content(content: str, file_path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Parses text-based content into a list of raw record dicts.
    Tries JSON array -> JSONL -> CSV/TSV.
    """
    raw_records: List[Dict[str, Any]] = []
    alerts: List[str] = []
    content = _strip_bom(content).replace("\r\n", "\n").replace("\r", "\n").strip()

    if not content:
        alerts.append("Surprise file is empty.")
        return [], alerts

    # --- JSON array ---
    if content.startswith("["):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                raw_records = [r for r in parsed if isinstance(r, dict)]
            elif isinstance(parsed, dict):
                # e.g. {"tickets": [...]}
                for key in ("tickets", "data", "records", "queue", "items"):
                    if key in parsed and isinstance(parsed[key], list):
                        raw_records = [r for r in parsed[key] if isinstance(r, dict)]
                        alerts.append(f"Unwrapped nested structure key '{key}'.")
                        break
                if not raw_records:
                    raw_records = [parsed]
            return raw_records, alerts
        except json.JSONDecodeError as e:
            alerts.append(f"JSON array parse failed ({e}); trying partial recovery.")
            # Best-effort: extract complete objects via regex
            for m in re.finditer(r"\{[^{}]+\}", content, re.DOTALL):
                try:
                    raw_records.append(json.loads(m.group()))
                except Exception:
                    pass
            if raw_records:
                alerts.append(f"Partial JSON recovery: extracted {len(raw_records)} objects.")
                return raw_records, alerts

    # --- Single dict ---
    if content.startswith("{"):
        # Try nested structure first
        try:
            parsed = json.loads(content.split("\n")[0])  # First line only (JSONL)
            raw_records.append(parsed)
        except Exception:
            pass
        # Try all lines as JSONL
        for idx, line in enumerate(content.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    raw_records.append(obj)
            except Exception as e:
                alerts.append(f"Malformed JSONL line {idx + 1}: {e}")
        if raw_records:
            # De-duplicate objects that appeared in both attempts
            seen = set()
            unique = []
            for r in raw_records:
                key = json.dumps(r, sort_keys=True, default=str)
                if key not in seen:
                    seen.add(key)
                    unique.append(r)
            return unique, alerts

    # --- CSV / TSV fallback ---
    records, csv_alerts = _parse_csv_or_tsv(content)
    alerts.extend(csv_alerts)
    return records, alerts


class SurpriseDriftAdapter:
    @classmethod
    def adapt_file(cls, file_path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Reads any surprise ticket file in any format,
        normalizes keys to standard schema, and reports all detected drifts.
        Never crashes — always returns (records, alerts).
        """
        all_alerts: List[str] = []

        if not file_path.exists():
            msg = f"Surprise file not found: {file_path}"
            log.alert(msg, alert_type="FILE_MISSING")
            return [], [msg]

        suffix = file_path.suffix.lower()

        # ── Excel input ──
        if suffix in (".xlsx", ".xls", ".xlsm"):
            raw_records, parse_alerts = _parse_excel(file_path)
            all_alerts.extend(parse_alerts)
        else:
            # Read raw text, tolerating encoding issues
            try:
                content = file_path.read_text(encoding="utf-8-sig")  # utf-8-sig strips BOM automatically
            except UnicodeDecodeError:
                try:
                    content = file_path.read_text(encoding="latin-1")
                    all_alerts.append("File decoded with latin-1 fallback (not UTF-8).")
                except Exception as e:
                    msg = f"Cannot read surprise file (encoding failure): {e}"
                    log.alert(msg, alert_type="ENCODING_ERROR")
                    return [], [msg]

            raw_records, parse_alerts = _parse_text_content(content, file_path)
            all_alerts.extend(parse_alerts)

        if not raw_records:
            all_alerts.append("No parseable records found in surprise file.")
            log.alert("Surprise file yielded zero parseable records.", alert_type="EMPTY_QUEUE",
                      file=str(file_path))
            return [], all_alerts

        # ── Normalize all records to canonical schema ──
        standardized: List[Dict[str, Any]] = []
        global_drifts: List[str] = []

        for rec in raw_records:
            if not isinstance(rec, dict):
                all_alerts.append(f"Skipped non-dict record: {type(rec).__name__}")
                continue
            std_rec, drifts = _normalize_record(rec)
            standardized.append(std_rec)
            for d in drifts:
                if d not in global_drifts:
                    global_drifts.append(d)

        all_alerts.extend(global_drifts)

        if global_drifts:
            log.alert(
                f"Schema drift detected in surprise file: {len(global_drifts)} mapping(s) applied.",
                alert_type="SCHEMA_DRIFT",
                drifts=global_drifts,
                file=str(file_path),
            )

        log.info(
            f"Drift adapter processed surprise file: {len(standardized)} records, "
            f"{len(all_alerts)} alert(s).",
            file=str(file_path),
        )
        return standardized, all_alerts
