"""Unified Context Store and Entity Resolution Engine for Meridian Freight.

Resilient asset loading — each source file is wrapped independently.
A missing or corrupt file logs an alert and continues; the system
never crashes because one asset is unavailable.

Precedence rules for conflicting data are documented in src/entity/precedence.py.
"""
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import pandas as pd

from src.config import (
    DISPATCHER_INTERVIEW_FILE,
    DRIVERS_ROSTER_FILE,
    EMAILS_DIR,
    FLEET_MASTER_FILE,
    MAINTENANCE_LOG_FILE,
    TRIPS_FILE,
)
from src.entity.normalizer import (
    normalize_client_name,
    normalize_driver_id,
    normalize_hub_name,
    normalize_vehicle_reg,
)
from src.security.pii_scrubber import redact_record, redact_text
from src.observability import logger as log

# Column synonyms for drivers_roster.csv (handles schema drift in static files too)
_DRIVER_COL_SYNONYMS = {
    "driver_id": ["driver_id", "drv_id", "id", "employee_id"],
    "name": ["name", "driver_name", "full_name"],
    "phone": ["phone", "mobile", "contact"],
    "dl_number": ["dl_number", "driving_license", "dl_no", "license_number"],
    "aadhaar": ["aadhaar", "aadhar", "uid", "aadhaar_number"],
    "joining_date": ["joining_date", "date_of_joining", "doj", "joined_on"],
    "home_hub": ["home_hub", "base_hub", "hub", "station"],
}

def _resolve_col(df: pd.DataFrame, synonyms: List[str]) -> Optional[str]:
    """Returns the first column name found in df from a synonym list."""
    for s in synonyms:
        if s in df.columns:
            return s
    return None


class ContextStore:
    def __init__(self):
        self.vehicles: Dict[str, Dict[str, Any]] = {}
        self.drivers: Dict[str, Dict[str, Any]] = {}
        self.maintenance_records: Dict[str, List[Dict[str, Any]]] = {}
        self.trips: List[Dict[str, Any]] = []
        self.emails: List[Dict[str, Any]] = []
        self.dispatcher_rules_text: str = ""
        self.apex_incident_vehicles: Set[str] = set()
        self.load_warnings: List[str] = []
        self.is_loaded: bool = False

    def load_all(self):
        """Loads all client assets. Partial loads are accepted; errors are logged."""
        for loader_name, loader_fn in [
            ("fleet_master", self._load_fleet_master),
            ("drivers_roster", self._load_drivers_roster),
            ("maintenance_log", self._load_maintenance_log),
            ("trips", self._load_trips),
            ("emails", self._load_emails),
            ("dispatcher_transcript", self._load_dispatcher_transcript),
        ]:
            try:
                loader_fn()
            except Exception as exc:
                msg = f"Asset '{loader_name}' failed to load: {exc}"
                self.load_warnings.append(msg)
                log.error(msg, exc=exc)

        self.is_loaded = True
        log.info(
            f"ContextStore loaded: vehicles={len(self.vehicles)}, "
            f"drivers={len(self.drivers)}, "
            f"maintenance_vehicles={len(self.maintenance_records)}, "
            f"trips={len(self.trips)}, emails={len(self.emails)}, "
            f"warnings={len(self.load_warnings)}"
        )

    def _load_fleet_master(self):
        """Loads and resolves duplicate fleet records into canonical vehicle store."""
        if not FLEET_MASTER_FILE.exists():
            log.warn("fleet_master.csv not found — vehicle store will be empty.")
            return

        try:
            df = pd.read_csv(FLEET_MASTER_FILE)
        except Exception as e:
            log.error(f"Cannot read fleet_master.csv: {e}", exc=e)
            return

        skipped = 0
        for idx, row in df.iterrows():
            try:
                raw_reg = str(row.get("registration_number", ""))
                norm_reg, _ = normalize_vehicle_reg(raw_reg)
                if not norm_reg:
                    skipped += 1
                    continue

                vehicle_id = row.get("vehicle_id")
                if pd.isna(vehicle_id) or str(vehicle_id).strip().lower() in ("", "nan"):
                    vehicle_id = None
                else:
                    vehicle_id = str(vehicle_id).strip()

                model = str(row.get("model", "Unknown")).strip() if pd.notna(row.get("model")) else "Unknown"
                year = int(row.get("year", 2020)) if pd.notna(row.get("year")) else 2020
                bs_stage = str(row.get("bs_stage", "BS4")).strip().upper() if pd.notna(row.get("bs_stage")) else "BS4"
                engine_heater = "Yes" if str(row.get("engine_heater", "No")).strip().lower() in ("yes", "true", "y", "1") else "No"
                home_hub = normalize_hub_name(str(row.get("home_hub", "")).strip()) or "Gurgaon"
                capacity = float(row.get("capacity_tonnes", 31.0)) if pd.notna(row.get("capacity_tonnes")) else 31.0
                status = str(row.get("status", "Active")).strip().capitalize() if pd.notna(row.get("status")) else "Active"

                if norm_reg in self.vehicles:
                    existing = self.vehicles[norm_reg]
                    if not existing.get("vehicle_id") and vehicle_id:
                        existing["vehicle_id"] = vehicle_id
                    if existing.get("engine_heater") == "No" and engine_heater == "Yes":
                        existing["engine_heater"] = "Yes"
                else:
                    self.vehicles[norm_reg] = {
                        "canonical_reg": norm_reg,
                        "vehicle_id": vehicle_id or f"MF-GEN-{norm_reg[-4:]}",
                        "raw_reg": raw_reg,
                        "model": model,
                        "year": year,
                        "bs_stage": bs_stage,
                        "engine_heater": engine_heater,
                        "home_hub": home_hub,
                        "capacity_tonnes": capacity,
                        "status": status,
                        "citation": f"fleet_master.csv:row_{idx + 2}",
                    }
            except Exception as row_err:
                log.warn(f"Skipped fleet_master row {idx + 2}: {row_err}")
                skipped += 1

        if skipped:
            log.warn(f"fleet_master: skipped {skipped} rows during load.")

    def _load_drivers_roster(self):
        """Loads driver roster with PII masked at ingestion. Tolerates column renames."""
        if not DRIVERS_ROSTER_FILE.exists():
            log.warn("drivers_roster.csv not found — driver store will be empty.")
            return

        try:
            df = pd.read_csv(DRIVERS_ROSTER_FILE)
        except Exception as e:
            log.error(f"Cannot read drivers_roster.csv: {e}", exc=e)
            return

        # Resolve column names via synonyms
        col = {std: _resolve_col(df, syns) for std, syns in _DRIVER_COL_SYNONYMS.items()}
        drifts = [f for f, c in col.items() if c and c != f]
        if drifts:
            log.alert(f"drivers_roster.csv column drift detected: {drifts}", alert_type="SCHEMA_DRIFT")

        skipped = 0
        for idx, row in df.iterrows():
            try:
                raw_id = str(row.get(col.get("driver_id") or "driver_id", ""))
                driver_id = normalize_driver_id(raw_id)
                if not driver_id:
                    skipped += 1
                    continue

                joining_raw = str(row.get(col.get("joining_date") or "joining_date", "")).strip()
                home_raw = str(row.get(col.get("home_hub") or "home_hub", "")).strip()

                self.drivers[driver_id] = {
                    "driver_id": driver_id,
                    "name": redact_text(str(row.get(col.get("name") or "name", ""))),
                    "phone": "[REDACTED_PHONE]",
                    "dl_number": "[REDACTED_DL]",
                    "aadhaar": "[REDACTED_AADHAAR]",
                    "joining_date": joining_raw,
                    "home_hub": normalize_hub_name(home_raw),
                    "citation": f"drivers_roster.csv:row_{idx + 2}",
                }
            except Exception as row_err:
                log.warn(f"Skipped drivers_roster row {idx + 2}: {row_err}")
                skipped += 1

        if skipped:
            log.warn(f"drivers_roster: skipped {skipped} rows during load.")

    def _load_maintenance_log(self):
        """Loads maintenance records with Hinglish jugaad/brake detection. Auto-detects sheet name."""
        if not MAINTENANCE_LOG_FILE.exists():
            log.warn("maintenance_log.xlsx not found — maintenance store will be empty.")
            return

        # Auto-detect sheet name
        sheet_name = "Maintenance Log"
        try:
            xl = pd.ExcelFile(MAINTENANCE_LOG_FILE)
            available = xl.sheet_names
            if sheet_name not in available:
                # Best-effort: pick the first sheet and log drift
                sheet_name = available[0]
                log.alert(
                    f"maintenance_log.xlsx sheet 'Maintenance Log' not found; "
                    f"using '{sheet_name}' instead. Available: {available}",
                    alert_type="SCHEMA_DRIFT",
                )
        except Exception as e:
            log.error(f"Cannot open maintenance_log.xlsx: {e}", exc=e)
            return

        try:
            df = pd.read_excel(MAINTENANCE_LOG_FILE, sheet_name=sheet_name)
        except Exception as e:
            log.error(f"Cannot read maintenance sheet '{sheet_name}': {e}", exc=e)
            return

        skipped = 0
        for idx, row in df.iterrows():
            try:
                raw_vehicle = str(row.get("vehicle", ""))
                norm_reg, _ = normalize_vehicle_reg(raw_vehicle)
                if not norm_reg:
                    skipped += 1
                    continue

                date_str = str(row.get("date", "")).split()[0]
                odometer = int(row.get("odometer_km", 0)) if pd.notna(row.get("odometer_km")) else 0
                mechanic = str(row.get("mechanic", "")).strip()
                notes = str(row.get("notes", "")).strip()
                notes_lower = notes.lower()

                is_brake_work = any(t in notes_lower for t in ["brake", "pad", "drum", "liner", "booster"])
                is_jugaad = (
                    any(t in notes_lower for t in ["jugaad", "jugad", "temporary fix", "temporary", "chalu kiya"])
                    or "guddu" in mechanic.lower()
                )

                entry = {
                    "date": date_str,
                    "odometer_km": odometer,
                    "mechanic": mechanic,
                    "notes": notes,
                    "is_brake_work": is_brake_work,
                    "is_jugaad": is_jugaad,
                    "citation": f"maintenance_log.xlsx:{sheet_name}:row_{idx + 2}",
                }
                self.maintenance_records.setdefault(norm_reg, []).append(entry)
            except Exception as row_err:
                log.warn(f"Skipped maintenance row {idx + 2}: {row_err}")
                skipped += 1

        for reg in self.maintenance_records:
            self.maintenance_records[reg].sort(key=lambda x: str(x["date"]), reverse=True)

        if skipped:
            log.warn(f"maintenance_log: skipped {skipped} rows during load.")

    def _load_trips(self):
        """Loads historical trip records and tracks Apex incident vehicles."""
        if not TRIPS_FILE.exists():
            log.warn("meridian_trips.csv not found — trip history will be empty.")
            return

        try:
            df = pd.read_csv(TRIPS_FILE)
        except Exception as e:
            log.error(f"Cannot read meridian_trips.csv: {e}", exc=e)
            return

        skipped = 0
        for idx, row in df.iterrows():
            try:
                raw_reg = str(row.get("vehicle_reg", ""))
                norm_reg, _ = normalize_vehicle_reg(raw_reg)
                client = normalize_client_name(str(row.get("client", "")))
                status = str(row.get("status", "")).strip().upper()

                trip_dict = {
                    "trip_id": str(row.get("trip_id", "")),
                    "created_at": str(row.get("created_at", "")),
                    "route_type": str(row.get("route_type", "")),
                    "origin_name": str(row.get("origin_name", "")),
                    "dest_name": str(row.get("dest_name", "")),
                    "vehicle_reg": norm_reg,
                    "driver_id": normalize_driver_id(str(row.get("driver_id", ""))),
                    "client": client,
                    "status": status,
                    "billed_amount": float(row.get("billed_amount", 0.0)) if pd.notna(row.get("billed_amount")) else 0.0,
                }
                self.trips.append(trip_dict)

                if client == "Apex Chemicals" and status in ("CANCELLED", "BREAKDOWN"):
                    if norm_reg:
                        self.apex_incident_vehicles.add(norm_reg)
            except Exception as row_err:
                log.warn(f"Skipped trips row {idx + 2}: {row_err}")
                skipped += 1

        if skipped:
            log.warn(f"meridian_trips: skipped {skipped} rows during load.")

    def _load_emails(self):
        """Loads and sanitizes client email threads. Skips unreadable files."""
        if not EMAILS_DIR.exists():
            log.warn("emails/ directory not found — email context will be empty.")
            return

        loaded = 0
        for fname in sorted(os.listdir(EMAILS_DIR)):
            if not fname.endswith(".txt"):
                continue
            fpath = EMAILS_DIR / fname
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
                sanitized = redact_text(content)
                self.emails.append({"filename": fname, "content": sanitized, "citation": f"emails/{fname}"})
                loaded += 1

                if "apex_rotation" in fname:
                    for norm_reg, v in self.vehicles.items():
                        if norm_reg in sanitized or v.get("raw_reg", "") in content:
                            self.apex_incident_vehicles.add(norm_reg)
            except Exception as e:
                log.warn(f"Cannot read email file '{fname}': {e}")

        log.info(f"Loaded {loaded} email threads from emails/.")

    def _load_dispatcher_transcript(self):
        """Loads and sanitizes the veteran dispatcher's interview transcript."""
        if not DISPATCHER_INTERVIEW_FILE.exists():
            log.warn("dispatcher_interview.txt not found — rules engine runs on hardcoded rules only.")
            return

        try:
            raw_text = DISPATCHER_INTERVIEW_FILE.read_text(encoding="utf-8", errors="replace")
            self.dispatcher_rules_text = redact_text(raw_text)
        except Exception as e:
            log.error(f"Cannot read dispatcher_interview.txt: {e}", exc=e)

    # ── Query Methods ─────────────────────────────────────────────────────────

    def get_vehicle(self, vehicle_str: str) -> Optional[Dict[str, Any]]:
        norm_reg, _ = normalize_vehicle_reg(vehicle_str)
        return self.vehicles.get(norm_reg) if norm_reg else None

    def get_driver(self, driver_id: str) -> Optional[Dict[str, Any]]:
        norm_id = normalize_driver_id(driver_id)
        return self.drivers.get(norm_id) if norm_id else None

    def get_maintenance_summary(self, vehicle_str: str, current_date_str: str = "2026-08-30") -> Dict[str, Any]:
        norm_reg, _ = normalize_vehicle_reg(vehicle_str)
        records = self.maintenance_records.get(norm_reg, []) if norm_reg else []

        try:
            curr_date = datetime.strptime(current_date_str.split("T")[0], "%Y-%m-%d")
        except Exception:
            curr_date = datetime(2026, 8, 30)

        latest_service_date = None
        brake_work_in_last_30d = False
        has_active_jugaad = False
        jugaad_date = None

        for rec in records:
            try:
                rec_date = datetime.strptime(rec["date"].split()[0], "%Y-%m-%d")
            except Exception:
                continue

            days_diff = (curr_date - rec_date).days
            if latest_service_date is None:
                latest_service_date = rec["date"]
            if rec.get("is_brake_work") and 0 <= days_diff <= 30:
                brake_work_in_last_30d = True
            if rec.get("is_jugaad") and 0 <= days_diff <= 7:
                has_active_jugaad = True
                jugaad_date = rec["date"]

        is_overdue = False
        if latest_service_date:
            try:
                rec_date = datetime.strptime(latest_service_date.split()[0], "%Y-%m-%d")
                if (curr_date - rec_date).days > 150:
                    is_overdue = True
            except Exception:
                pass

        return {
            "canonical_reg": norm_reg,
            "latest_service_date": latest_service_date,
            "brake_work_in_last_30d": brake_work_in_last_30d,
            "has_active_jugaad": has_active_jugaad,
            "jugaad_date": jugaad_date,
            "is_overdue": is_overdue,
            "records_count": len(records),
            "citation": records[0]["citation"] if records else "maintenance_log.xlsx",
        }

    def get_eligible_vehicles_at_hub(self, hub_name: str) -> List[Dict[str, Any]]:
        norm_hub = normalize_hub_name(hub_name)
        if not norm_hub:
            return []
        return [
            v for v in self.vehicles.values()
            if v.get("status") == "Active" and normalize_hub_name(v.get("home_hub")) == norm_hub
        ]
