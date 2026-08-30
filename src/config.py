"""Configuration and constants for Meridian Freight Automation Platform."""
import os
from pathlib import Path

# Base Paths
PROJECT_ROOT = Path("d:/meridian")
BUNDLE_DIR = PROJECT_ROOT / "candidate_bundle"

OUTPUTS_DIR = PROJECT_ROOT / "outputs"
AUDIT_DIR = PROJECT_ROOT / "audit"
DATA_DIR = PROJECT_ROOT / "data"

# Ensure output directories exist
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Standard Output File Paths
WORK_ORDERS_FILE = OUTPUTS_DIR / "work_orders.jsonl"
COMMS_PENDING_FILE = OUTPUTS_DIR / "comms_pending.jsonl"
COMMS_SENT_FILE = OUTPUTS_DIR / "comms_sent.jsonl"
QUARANTINE_FILE = OUTPUTS_DIR / "quarantine.jsonl"
AUDIT_FILE = AUDIT_DIR / "audit.jsonl"

# Input Assets
TICKETS_FILE = BUNDLE_DIR / "tickets.json"
FLEET_MASTER_FILE = BUNDLE_DIR / "fleet_master.csv"
DRIVERS_ROSTER_FILE = BUNDLE_DIR / "drivers_roster.csv"
MAINTENANCE_LOG_FILE = BUNDLE_DIR / "maintenance_log.xlsx"
TRIPS_FILE = BUNDLE_DIR / "meridian_trips.csv"
EMAILS_DIR = BUNDLE_DIR / "emails"
DISPATCHER_INTERVIEW_FILE = BUNDLE_DIR / "dispatcher_interview.txt"

# Hub Coordinates (Latitude, Longitude) for North India Network
HUB_COORDINATES = {
    "Delhi": (28.6139, 77.2090),
    "Gurgaon": (28.4595, 77.0266),
    "Ambala": (30.3782, 76.7767),
    "Chandigarh": (30.7333, 76.7794),
    "Ludhiana": (30.9010, 75.8573),
    "Jaipur": (26.9124, 75.7873),
    "Lucknow": (26.8467, 80.9462),
    "Kanpur": (26.4499, 80.3319),
    "Rudrapur": (28.9835, 79.4005),
}

# Highway Road Distance Matrix (km) between North India Hubs
HUB_ROAD_DISTANCES = {
    ("Delhi", "Gurgaon"): 32,
    ("Delhi", "Ambala"): 205,
    ("Delhi", "Chandigarh"): 245,
    ("Delhi", "Ludhiana"): 315,
    ("Delhi", "Jaipur"): 270,
    ("Delhi", "Lucknow"): 530,
    ("Delhi", "Kanpur"): 485,
    ("Delhi", "Rudrapur"): 235,

    ("Gurgaon", "Ambala"): 235,
    ("Gurgaon", "Chandigarh"): 275,
    ("Gurgaon", "Ludhiana"): 345,
    ("Gurgaon", "Jaipur"): 240,
    ("Gurgaon", "Lucknow"): 555,
    ("Gurgaon", "Kanpur"): 510,
    ("Gurgaon", "Rudrapur"): 265,

    ("Ambala", "Chandigarh"): 45,
    ("Ambala", "Ludhiana"): 115,
    ("Ambala", "Jaipur"): 440,
    ("Ambala", "Lucknow"): 620,
    ("Ambala", "Kanpur"): 675,
    ("Ambala", "Rudrapur"): 310,

    ("Chandigarh", "Ludhiana"): 100,
    ("Chandigarh", "Jaipur"): 485,
    ("Chandigarh", "Lucknow"): 660,
    ("Chandigarh", "Kanpur"): 715,
    ("Chandigarh", "Rudrapur"): 345,

    ("Ludhiana", "Jaipur"): 520,
    ("Ludhiana", "Lucknow"): 745,
    ("Ludhiana", "Kanpur"): 800,
    ("Ludhiana", "Rudrapur"): 430,

    ("Jaipur", "Lucknow"): 570,
    ("Jaipur", "Kanpur"): 515,
    ("Jaipur", "Rudrapur"): 460,

    ("Lucknow", "Kanpur"): 85,
    ("Lucknow", "Rudrapur"): 325,

    ("Kanpur", "Rudrapur"): 375,
}

def get_hub_distance(hub1: str, hub2: str) -> float:
    """Returns road distance between two hubs in km."""
    if not hub1 or not hub2:
        return 9999.0
    h1, h2 = hub1.strip().title(), hub2.strip().title()
    if h1 == h2:
        return 0.0
    if (h1, h2) in HUB_ROAD_DISTANCES:
        return HUB_ROAD_DISTANCES[(h1, h2)]
    if (h2, h1) in HUB_ROAD_DISTANCES:
        return HUB_ROAD_DISTANCES[(h2, h1)]
    return 500.0  # fallback approximate distance

# Delhi NCR Hubs / Regions
DELHI_NCR_REGIONS = {"Delhi", "Gurgaon", "Faridabad", "Noida", "Ghaziabad"}

# Hill Route Hubs / Destinations
HILL_REGIONS = {"Rudrapur", "Nainital", "Haldwani", "Almora", "Pantnagar"}

# Monsoon Months (July, August, September)
MONSOON_MONTHS = {7, 8, 9}

# Winter Months (October, November, December, January, February)
WINTER_MONTHS_DELHI = {10, 11, 12, 1, 2}
WINTER_MONTHS_HILLS = {11, 12, 1, 2}
