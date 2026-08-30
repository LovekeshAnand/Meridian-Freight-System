"""Ticket Queue Validator and Quarantine Filter — Hardened Edition.

Philosophy: coerce first, quarantine only when coercion is impossible.
- Integer ticket_id (27) -> "TKT-0027"
- String distances ("20 km") -> 20.0
- Alternate date formats ("30-08-2026") -> "2026-08-30T00:00:00"
- Non-string fields -> str() coercion where semantically safe
- Only truly unrecoverable records are quarantined

Never crashes on any input type.
"""
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.entity.normalizer import normalize_vehicle_reg, normalize_hub_name
from src.observability import logger as log

# All date formats we attempt to parse
_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%YT%H:%M:%S",
    "%d-%m-%Y %H:%M:%S",
    "%Y/%m/%d",
    "%d %b %Y",
    "%d %B %Y",
]

_MAX_FIELD_LENGTH = 500  # Truncate absurdly long values


@dataclass
class ValidationResult:
    is_valid: bool
    quarantine_reason: Optional[str] = None
    sanitized_ticket: Optional[Dict[str, Any]] = None
    warnings: Optional[List[str]] = None  # Non-fatal issues noted but not quarantined


def _coerce_ticket_id(val: Any) -> Optional[str]:
    """Coerces any ticket_id to a string. Int 27 -> 'TKT-0027'."""
    if val is None:
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return f"TKT-{int(val):04d}"
    s = str(val).strip()
    return s if s and s.lower() not in ("none", "null", "nan", "") else None


def _coerce_km(val: Any) -> Tuple[Optional[float], Optional[str]]:
    """
    Extracts numeric km from any value.
    "20 km" -> 20.0, 20 -> 20.0, "~20.5" -> 20.5
    Returns (float_value, warning_or_none)
    """
    if val is None:
        return None, None
    if isinstance(val, bool):
        return None, "Boolean value for km_from_origin_hub"
    if isinstance(val, (int, float)):
        return float(val), None
    s = str(val).strip()
    match = re.match(r"^[~±≈]?\s*([\d,]+\.?\d*)", s)
    if match:
        try:
            num = float(match.group(1).replace(",", ""))
            warn = f"Coerced km from '{s}' -> {num}" if s != str(num) else None
            return num, warn
        except ValueError:
            pass
    return None, f"Cannot parse km_from_origin_hub: '{s}'"


def _coerce_date(val: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Attempts to parse val as a datetime using all known formats.
    Returns (iso_string, warning_or_none)
    """
    if val is None:
        return None, None
    s = str(val).strip()
    if not s or s.lower() in ("none", "null", "nan"):
        return None, None

    # Already looks like ISO
    if re.match(r"\d{4}-\d{2}-\d{2}", s):
        try:
            dt = datetime.fromisoformat(s[:19])
            return dt.isoformat(), None
        except ValueError:
            pass

    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(s[:len(fmt) + 5], fmt)
            return dt.isoformat(), f"Date '{s}' parsed via format '{fmt}'"
        except ValueError:
            continue

    return None, f"Unparseable created_at: '{s}'"


def _safe_str(val: Any, max_len: int = _MAX_FIELD_LENGTH) -> str:
    """Safely converts any value to a truncated string."""
    if val is None:
        return ""
    return str(val).strip()[:max_len]


class TicketValidator:
    """
    Validates and sanitizes breakdown ticket records with maximum coercion
    before quarantining. Only records that are genuinely unrecoverable are
    written to quarantine.
    """

    CRITICAL_FIELDS = ["ticket_id", "vehicle", "origin_hub", "km_from_origin_hub", "client", "created_at"]

    @classmethod
    def validate_ticket(cls, raw_ticket: Any) -> ValidationResult:
        """Validates a single ticket record."""
        warnings: List[str] = []

        # Guard: input must be a dict
        if not isinstance(raw_ticket, dict):
            return ValidationResult(
                is_valid=False,
                quarantine_reason=f"Record is not a dict: got {type(raw_ticket).__name__}",
            )

        # ── ticket_id ──────────────────────────────────────────────────────────
        raw_id = raw_ticket.get("ticket_id")
        ticket_id = _coerce_ticket_id(raw_id)
        if not ticket_id:
            return ValidationResult(
                is_valid=False,
                quarantine_reason="Missing or uncoerceable ticket_id",
            )
        if ticket_id != str(raw_id).strip() if raw_id is not None else False:
            warnings.append(f"ticket_id coerced from {repr(raw_id)} -> {repr(ticket_id)}")

        # ── vehicle registration ────────────────────────────────────────────────
        raw_veh = _safe_str(raw_ticket.get("vehicle"))
        if not raw_veh:
            return ValidationResult(
                is_valid=False,
                quarantine_reason="Missing vehicle registration",
            )
        norm_veh, is_valid_reg = normalize_vehicle_reg(raw_veh)
        if not norm_veh or not is_valid_reg:
            return ValidationResult(
                is_valid=False,
                quarantine_reason=f"Invalid vehicle registration: '{raw_veh}'",
            )

        # ── origin_hub ─────────────────────────────────────────────────────────
        raw_hub = _safe_str(raw_ticket.get("origin_hub"))
        if not raw_hub:
            return ValidationResult(
                is_valid=False,
                quarantine_reason="Missing origin_hub",
            )
        norm_hub = normalize_hub_name(raw_hub) or raw_hub  # Keep raw if not in known hubs

        # ── km_from_origin_hub ─────────────────────────────────────────────────
        km_float, km_warn = _coerce_km(raw_ticket.get("km_from_origin_hub"))
        if km_warn:
            warnings.append(km_warn)
        if km_float is None:
            return ValidationResult(
                is_valid=False,
                quarantine_reason=f"Cannot determine km_from_origin_hub from: {repr(raw_ticket.get('km_from_origin_hub'))}",
            )
        if km_float < 0:
            return ValidationResult(
                is_valid=False,
                quarantine_reason=f"Negative km_from_origin_hub: {km_float}",
            )
        if km_float > 5000:
            warnings.append(f"Unusually large km_from_origin_hub: {km_float} — possible data error")

        # ── client ─────────────────────────────────────────────────────────────
        raw_client = _safe_str(raw_ticket.get("client"))
        if not raw_client:
            return ValidationResult(
                is_valid=False,
                quarantine_reason="Missing client",
            )

        # ── created_at ─────────────────────────────────────────────────────────
        iso_date, date_warn = _coerce_date(raw_ticket.get("created_at"))
        if date_warn:
            warnings.append(date_warn)
        if not iso_date:
            return ValidationResult(
                is_valid=False,
                quarantine_reason=f"Cannot parse created_at: {repr(raw_ticket.get('created_at'))}",
            )
        # Warn on far-future dates (possible test data or data error)
        try:
            parsed_dt = datetime.fromisoformat(iso_date)
            if parsed_dt.year > datetime.now().year + 1:
                warnings.append(f"Far-future date in created_at: {iso_date}")
        except Exception:
            pass

        # ── Build sanitized ticket ─────────────────────────────────────────────
        sanitized = dict(raw_ticket)
        sanitized["ticket_id"] = ticket_id
        sanitized["vehicle"] = norm_veh
        sanitized["km_from_origin_hub"] = km_float
        sanitized["origin_hub"] = norm_hub
        sanitized["destination"] = normalize_hub_name(_safe_str(raw_ticket.get("destination"))) or _safe_str(raw_ticket.get("destination"))
        sanitized["created_at"] = iso_date
        sanitized["client"] = raw_client
        sanitized["issue"] = _safe_str(raw_ticket.get("issue")) or "unspecified malfunction"
        sanitized["severity"] = _safe_str(raw_ticket.get("severity")) or "UNKNOWN"
        sanitized["driver_id"] = _safe_str(raw_ticket.get("driver_id"))
        sanitized["status"] = _safe_str(raw_ticket.get("status")) or "OPEN"

        if warnings:
            log.warn(
                f"Ticket {ticket_id} validated with {len(warnings)} warning(s)",
                ticket_id=ticket_id,
                warnings=warnings,
            )

        return ValidationResult(
            is_valid=True,
            sanitized_ticket=sanitized,
            warnings=warnings if warnings else None,
        )
