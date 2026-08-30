"""Multilingual Hinglish Mechanic Notes Parser and Translator.

Translates free-text mechanic notes in Hindi-English into structured
maintenance records and extracts critical signals (jugaad, brake work, components).
"""
import re
from typing import Any, Dict

# Hinglish semantic translation mappings
HINGLISH_DICTIONARY = {
    "smoke aa raha tha": "smoke was emitting",
    "band kiya": "stopped/closed",
    "jugaad se": "using temporary patch (jugaad)",
    "jugaad": "temporary fix",
    "jugad": "temporary fix",
    "permanent fix baaki hai": "permanent repair is pending",
    "awaaz aa rahi thi": "unusual noise was observed",
    "weld kiya": "welded",
    "pickup kam ho gayi thi": "engine pickup/power was reduced",
    "gear slip kar raha tha": "gear was slipping",
    "naya lagwaya": "new part installed/replaced",
    "theek kiya": "repaired",
    "chalu kiya": "made operational",
    "gaadi khadi thi": "vehicle was halted",
    "pe": "at",
    "me dikkat thi": "had malfunction",
}

COMPONENT_KEYWORDS = {
    "brake": ["brake", "pad", "drum", "liner", "booster"],
    "battery": ["battery", "charging", "terminal"],
    "clutch": ["clutch", "pressure plate", "flywheel"],
    "turbo": ["turbo", "turbocharger"],
    "tyre": ["tyre", "tire", "puncture", "wheel"],
    "engine": ["engine", "oil", "overheating", "gasket"],
    "fuel": ["fuel", "diesel", "fuel line", "injector", "leak"],
    "radiator": ["radiator", "coolant", "fan belt"],
    "gearbox": ["gearbox", "gear", "transmission"],
    "suspension": ["suspension", "leaf spring", "shock"]
}

def translate_hinglish_to_english(notes_text: str) -> str:
    """Translates Hinglish mechanic notes into clear English description."""
    if not notes_text or not isinstance(notes_text, str):
        return ""

    translated = notes_text
    for hinglish, english in HINGLISH_DICTIONARY.items():
        translated = re.sub(re.escape(hinglish), english, translated, flags=re.IGNORECASE)

    return translated.strip()

def parse_maintenance_note(notes_text: str, mechanic_name: str = "") -> Dict[str, Any]:
    """Parses raw mechanic note into structured health indicators."""
    notes_lower = notes_text.lower() if notes_text else ""
    translated = translate_hinglish_to_english(notes_text)

    # Detect temporary fix / jugaad
    is_jugaad = any(term in notes_lower for term in ["jugaad", "jugad", "temporary fix", "temporary", "band kiya jugaad"]) or "guddu" in mechanic_name.lower()
    
    # Detect brake work
    is_brake_work = any(term in notes_lower for term in COMPONENT_KEYWORDS["brake"])

    # Detect affected component
    detected_component = "general"
    for comp, keywords in COMPONENT_KEYWORDS.items():
        if any(kw in notes_lower for kw in keywords):
            detected_component = comp
            break

    requires_permanent_repair = is_jugaad or "permanent repair" in translated.lower() or "baaki hai" in notes_lower

    return {
        "raw_note": notes_text,
        "translated_note": translated,
        "detected_component": detected_component,
        "is_jugaad": is_jugaad,
        "is_brake_work": is_brake_work,
        "requires_permanent_repair": requires_permanent_repair,
    }
