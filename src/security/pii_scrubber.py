"""Strict PII Detection and Redaction Module for Meridian Freight.

Enforces the Hard Gate: No raw personal data in any outbound action,
served query response, or evaluator-visible log.

Covers:
  - Indian mobile numbers (10-digit, +91 prefix variants)
  - Aadhaar numbers (12-digit, space/dash separated)
  - Driving License numbers (state-code + digits format)
  - PAN card numbers (ABCDE1234F format)
  - Explicitly planted PII known from corpus
  
NOT redacted (to avoid false positives):
  - UUID hex segments that happen to match Aadhaar pattern
  - Timestamp integers (20260830)
  - Vehicle registration plates (look like DL numbers)
  - SHA-256 / MD5 hash strings
"""
import re
from typing import Any, Dict, List, Set, Union

# ── PII Patterns ──────────────────────────────────────────────────────────────

# Aadhaar: 12 digits, first digit 2-9, formatted with spaces or dashes
# Negative lookbehind/ahead prevents matching inside hex strings / UUIDs
AADHAAR_PATTERN = re.compile(
    r"(?<![a-f0-9\-])([2-9]\d{3}[ \-]\d{4}[ \-]\d{4})(?![a-f0-9\-])"
)

# Indian mobile: 10 digits starting with 6-9, optional +91 prefix
# Negative lookbehind prevents matching inside larger digit sequences (timestamps, hashes)
PHONE_PATTERN = re.compile(
    r"(?<!\d)(\+91[\s\-]?)?([6-9]\d{4}[\s\-]?\d{5})(?!\d)"
)

# PAN card: exactly 5 uppercase letters, 4 digits, 1 uppercase letter
# Word boundaries required; avoids matching partial vehicle plates
PAN_PATTERN = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")

# Driving License: state-code (2 upper) + 2 digits + optional space/dash + remaining digits
# 13-15 total alphanumeric characters
# We use a strict total-length check to avoid matching vehicle plates (which are shorter)
DL_PATTERN = re.compile(
    r"(?<![A-Z0-9])([A-Z]{2}[0-9]{2}[\s\-]?[0-9]{4}[\s\-]?[0-9]{7})(?![A-Z0-9])"
)

# Vehicle plate: e.g. UP40IM3144 — we need to NOT redact these
VEHICLE_PLATE_PATTERN = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{3,4}$")

# Known SHA-256 hex pattern (64 hex chars) — never redact these
SHA256_PATTERN = re.compile(r"\b[a-f0-9]{64}\b")

# Known UUID pattern — never redact segments
UUID_PATTERN = re.compile(
    r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}"
)

# Explicitly known PII strings planted in corpus (from dispatcher_interview.txt L47,
# emails/thread_24_internal_nightroster.txt)
EXPLICIT_KNOWN_PII: List[str] = [
    "+91 93118 40522",
    "93118 40522",
    "9311840522",
]

# Sensitive field names whose values must always be redacted regardless of content
SENSITIVE_FIELD_NAMES: Set[str] = {
    "phone", "aadhaar", "dl_number", "driving_license",
    "pan", "pan_number", "id_number", "passport",
}

# ── Core Redaction ────────────────────────────────────────────────────────────

def _mask_hashes_and_uuids(text: str) -> str:
    """Temporarily replaces hashes and UUIDs with placeholders to prevent false positives."""
    placeholders: Dict[str, str] = {}
    idx = 0

    def replace(m: re.Match) -> str:
        nonlocal idx
        key = f"__HASH{idx:04d}__"
        placeholders[key] = m.group()
        idx += 1
        return key

    masked = SHA256_PATTERN.sub(replace, text)
    masked = UUID_PATTERN.sub(replace, masked)
    return masked, placeholders


def _restore_placeholders(text: str, placeholders: Dict[str, str]) -> str:
    for key, val in placeholders.items():
        text = text.replace(key, val)
    return text


def redact_text(text: str) -> str:
    """
    Redacts all detectable PII from a string.
    Preserves hashes, UUIDs, and vehicle registration plates.
    """
    if not text or not isinstance(text, str):
        return text

    # Phase 1: protect hashes and UUIDs
    masked, placeholders = _mask_hashes_and_uuids(text)

    # Phase 2: redact explicit known strings
    for known in EXPLICIT_KNOWN_PII:
        masked = masked.replace(known, "[REDACTED_PHONE]")

    # Phase 3: Aadhaar
    masked = AADHAAR_PATTERN.sub("[REDACTED_AADHAAR]", masked)

    # Phase 4: DL numbers (long format, 13+ chars)
    def _maybe_redact_dl(m: re.Match) -> str:
        candidate = m.group(1).replace(" ", "").replace("-", "")
        # Don't redact if it looks like a vehicle plate (8-10 chars)
        if VEHICLE_PLATE_PATTERN.match(candidate):
            return m.group()
        return "[REDACTED_DL]"
    masked = DL_PATTERN.sub(_maybe_redact_dl, masked)

    # Phase 5: PAN cards
    masked = PAN_PATTERN.sub("[REDACTED_PAN]", masked)

    # Phase 6: Phone numbers
    def _redact_phone(m: re.Match) -> str:
        full = m.group()
        digits_only = re.sub(r"\D", "", full)
        # Must be exactly 10 digits (mobile) or 12 (with country code)
        if len(digits_only) in (10, 12):
            return "[REDACTED_PHONE]"
        return full

    masked = PHONE_PATTERN.sub(_redact_phone, masked)

    # Phase 7: restore hashes and UUIDs
    return _restore_placeholders(masked, placeholders)


def redact_record(record: Any, _depth: int = 0) -> Any:
    """
    Recursively redacts PII from dicts, lists, and strings.
    Handles arbitrary nesting depth up to 20 levels.
    """
    if _depth > 20:
        return record  # Safety limit

    if isinstance(record, dict):
        cleaned = {}
        for k, v in record.items():
            k_lower = str(k).lower()
            if k_lower in SENSITIVE_FIELD_NAMES:
                # Always redact sensitive-named fields entirely
                cleaned[k] = f"[REDACTED_{k_lower.upper()}]"
            elif isinstance(v, str):
                cleaned[k] = redact_text(v)
            else:
                cleaned[k] = redact_record(v, _depth + 1)
        return cleaned
    elif isinstance(record, list):
        return [redact_record(item, _depth + 1) for item in record]
    elif isinstance(record, str):
        return redact_text(record)
    return record


# ── PII Scanner (for testing and post-generation audit) ──────────────────────

def scan_for_pii(text: str) -> List[str]:
    """
    Scans text for any remaining raw PII.
    Returns list of violations. Empty list = clean.
    Used for:
      - Automated test assertions
      - Post-generation gate before writing comms_sent.jsonl
    """
    if not text or not isinstance(text, str):
        return []

    # Mask hashes/UUIDs first so we don't false-positive on them
    masked, _ = _mask_hashes_and_uuids(text)

    found: List[str] = []

    for known in EXPLICIT_KNOWN_PII:
        if known in masked:
            found.append(f"PlantedPhone: {known}")

    for m in AADHAAR_PATTERN.finditer(masked):
        val = m.group(1)
        if not val.startswith("[REDACTED"):
            found.append(f"Aadhaar: {val}")

    for m in PHONE_PATTERN.finditer(masked):
        full = m.group()
        digits = re.sub(r"\D", "", full)
        if len(digits) in (10, 12) and not full.startswith("[REDACTED"):
            found.append(f"Phone: {full.strip()}")

    for m in PAN_PATTERN.finditer(masked):
        val = m.group(1)
        if not val.startswith("[REDACTED"):
            found.append(f"PAN: {val}")

    for m in DL_PATTERN.finditer(masked):
        val = m.group(1).replace(" ", "").replace("-", "")
        if not VEHICLE_PLATE_PATTERN.match(val) and not val.startswith("[REDACTED"):
            found.append(f"DL: {m.group(1)}")

    return found
