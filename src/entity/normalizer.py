"""Entity Normalization and Resolution Module.

Normalizes vehicle registrations, client names, hubs, and driver IDs across
all disparate inputs and formats into canonical representations.
"""
import re
from typing import Optional, Tuple

# Canonical Indian commercial vehicle plate format: e.g. UP40IM3144, DL33CT2113, HR26A1234
CANONICAL_PLATE_REGEX = re.compile(r'^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$')

CLIENT_SYNONYMS = {
    "shakti": "Shakti Cement",
    "shakti cement": "Shakti Cement",
    "shakticement": "Shakti Cement",
    "apex": "Apex Chemicals",
    "apex chemicals": "Apex Chemicals",
    "apexchem": "Apex Chemicals",
    "vertex": "Vertex Retail",
    "vertex retail": "Vertex Retail",
    "vertexretail": "Vertex Retail",
    "orion": "Orion Pharma",
    "orion pharma": "Orion Pharma",
    "orionpharma": "Orion Pharma",
    "internal": "Internal",
}

HUB_SYNONYMS = {
    "delhi": "Delhi",
    "gurgaon": "Gurgaon",
    "gurugram": "Gurgaon",
    "ambala": "Ambala",
    "chandigarh": "Chandigarh",
    "ludhiana": "Ludhiana",
    "jaipur": "Jaipur",
    "lucknow": "Lucknow",
    "kanpur": "Kanpur",
    "rudrapur": "Rudrapur",
    "nainital": "Rudrapur",
    "pantnagar": "Rudrapur",
}

def normalize_vehicle_reg(raw_reg: Optional[str]) -> Tuple[Optional[str], bool]:
    """
    Normalizes raw vehicle registration into canonical form.
    Returns: (canonical_reg, is_valid)
    Examples:
      'UP-40-IM-3144' -> ('UP40IM3144', True)
      'dl33ct2113'    -> ('DL33CT2113', True)
      'hr??unknown'   -> (None, False)
    """
    if not raw_reg or not isinstance(raw_reg, str):
        return None, False

    # Remove all spaces, dashes, dots, underscores
    cleaned = re.sub(r'[\s\-_.]+', '', raw_reg).upper().strip()

    if not cleaned:
        return None, False

    # Check against canonical plate regex
    if CANONICAL_PLATE_REGEX.match(cleaned):
        return cleaned, True

    # If it contains wildcard/question marks or is too short/long
    if '?' in cleaned or len(cleaned) < 8 or len(cleaned) > 11:
        return None, False

    return cleaned, False

def normalize_client_name(raw_client: Optional[str]) -> Optional[str]:
    """Normalizes client name string to canonical company name."""
    if not raw_client or not isinstance(raw_client, str):
        return None

    cleaned = raw_client.strip().lower()
    if cleaned in CLIENT_SYNONYMS:
        return CLIENT_SYNONYMS[cleaned]

    for syn_key, canonical in CLIENT_SYNONYMS.items():
        if syn_key in cleaned:
            return canonical

    return raw_client.strip().title()

def normalize_hub_name(raw_hub: Optional[str]) -> Optional[str]:
    """Normalizes hub name to canonical title."""
    if not raw_hub or not isinstance(raw_hub, str):
        return None

    cleaned = raw_hub.strip().lower()
    if cleaned in HUB_SYNONYMS:
        return HUB_SYNONYMS[cleaned]

    for syn_key, canonical in HUB_SYNONYMS.items():
        if syn_key in cleaned:
            return canonical

    return raw_hub.strip().title()

def normalize_driver_id(raw_driver: Optional[str]) -> Optional[str]:
    """Normalizes driver identifier to DRV-XXX standard."""
    if not raw_driver or not isinstance(raw_driver, str):
        return None
    cleaned = raw_driver.strip().upper()
    match = re.match(r'^(?:DRV[-_]?)?(\d+)$', cleaned)
    if match:
        num = int(match.group(1))
        return f"DRV-{num:03d}"
    return cleaned
