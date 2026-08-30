"""Meridian Freight Breakdown-to-Resolution Platform.

Single-command unified launcher:
  python run.py

This starts both:
  1. FastAPI / Uvicorn Backend (http://127.0.0.1:8000)
  2. React / Vite Dispatch Frontend (http://localhost:5173)

Headless CLI Modes:
  python run.py --cli               # Run headless queue processor
  python run.py --approve-all       # Run pipeline & approve all drafts
  python run.py --query "question"  # Ask grounded questions with exact citations
  python run.py --surprise <path>   # Process surprise ticket file with drift adapter
  python run.py --test              # Run full 92-test automated verification suite
"""
import argparse
import os
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / "frontend"


def run_full_stack():
    """Concurrently launches the FastAPI backend and Vite frontend."""
    print("=" * 72)
    print("       MERIDIAN FREIGHT — UNIFIED PLATFORM LAUNCHER       ")
    print("=" * 72)
    print("\n[1/2] Starting FastAPI Backend on http://127.0.0.1:8000 ...")

    # Start FastAPI Backend via Uvicorn
    backend_cmd = [
        sys.executable, "-m", "uvicorn", "src.api.server:app",
        "--host", "127.0.0.1",
        "--port", "8000",
        "--log-level", "info"
    ]

    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=str(ROOT_DIR),
        shell=False
    )

    print("[2/2] Starting React / Vite Frontend on http://localhost:5173 ...")

    # Use npm on Windows / Unix
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    frontend_proc = subprocess.Popen(
        [npm_cmd, "run", "dev"],
        cwd=str(FRONTEND_DIR),
        shell=(sys.platform == "win32")
    )

    print("\n" + "-" * 72)
    print("🚀  MERIDIAN FREIGHT IS RUNNING LIVE:")
    print("    👉  Web Dispatch UI:   http://localhost:5173")
    print("    👉  Backend API:       http://127.0.0.1:8000")
    print("    👉  Interactive Docs:  http://127.0.0.1:8000/docs")
    print("-" * 72)
    print("Press Ctrl + C anytime to stop all services.\n")

    # Optional: open browser after 2 seconds
    time.sleep(2)
    try:
        webbrowser.open("http://localhost:5173")
    except Exception:
        pass

    def cleanup(signum=None, frame=None):
        print("\nShutting down Meridian Freight platform...")
        try:
            frontend_proc.terminate()
            backend_proc.terminate()
            if sys.platform == "win32":
                # Ensure child processes on Windows are terminated
                subprocess.call(["taskkill", "/F", "/T", "/PID", str(frontend_proc.pid)], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                subprocess.call(["taskkill", "/F", "/T", "/PID", str(backend_proc.pid)], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        while True:
            time.sleep(1)
            # Check if any process died unexpectedly
            if backend_proc.poll() is not None:
                print(f"[!] Backend stopped unexpectedly (exit code {backend_proc.returncode}).")
                cleanup()
            if frontend_proc.poll() is not None:
                print(f"[!] Frontend stopped unexpectedly (exit code {frontend_proc.returncode}).")
                cleanup()
    except KeyboardInterrupt:
        cleanup()


def run_headless_cli(args):
    """Handles CLI modes for testing, querying, and queue batch processing."""
    from src.pipeline.processor import BreakdownPipeline
    from src.ui.dashboard import ApprovalGate
    from src.query.engine import GroundedQueryEngine
    from src.surprise.drift_adapter import SurpriseDriftAdapter
    import json

    print("=" * 72)
    print("        MERIDIAN FREIGHT — HEADLESS DISPATCH PIPELINE        ")
    print("=" * 72)

    if args.test:
        import unittest
        loader = unittest.TestLoader()
        suite = loader.discover("tests")
        runner = unittest.TextTestRunner(verbosity=2)
        runner.run(suite)
        return

    if args.query:
        engine = GroundedQueryEngine()
        res = engine.query(args.query)
        print(f"\nQuestion:  {res['question']}")
        print(f"Answer:    {res['answer']}")
        print(f"Citations: {', '.join(res['citations']) if res['citations'] else 'None'}")
        print(f"Grounded:  {'YES' if res['is_sufficient'] else 'INSUFFICIENT DATA'}")
        return

    if args.surprise:
        surprise_path = Path(args.surprise)
        print(f"Processing surprise ticket file: {surprise_path}")
        records, alerts = SurpriseDriftAdapter.adapt_file(surprise_path)
        print(f"Detected {len(records)} records. Drift alerts: {alerts}")
        
        temp_path = ROOT_DIR / "data" / "temp_surprise.json"
        temp_path.write_text(json.dumps(records), encoding="utf-8")
        
        pipeline = BreakdownPipeline()
        res = pipeline.process_ticket_queue(temp_path)
        print(f"\nSurprise Processing Result: {res}")
        return

    # Default Headless Run
    pipeline = BreakdownPipeline()
    print("Processing breakdown tickets queue (tickets.json)...")
    res = pipeline.process_ticket_queue()
    total_q = res.get("total_tickets_in_queue") or res.get("total_in_queue", 0)
    valid_proc = res.get("unique_valid_tickets_processed") or res.get("valid_processed", 0)
    quar_count = res.get("quarantined_records_count") or res.get("quarantined", 0)
    wo_count = res.get("work_orders_generated", 0)
    comms_count = res.get("comms_pending_count") or res.get("comms_pending", 0)

    print(f"\nPipeline Run Completed Successfully:")
    print(f"  - Total Queue Records:     {total_q}")
    print(f"  - Valid Processed Tickets: {valid_proc}")
    print(f"  - Quarantined Records:     {quar_count}")
    print(f"  - Work Orders Generated:   {wo_count} -> outputs/work_orders.jsonl")
    print(f"  - Comms Drafted (Pending): {comms_count} -> outputs/comms_pending.jsonl")
    print(f"  - Audit Trail Updated:     -> audit/audit.jsonl")

    gate = ApprovalGate()
    if args.approve_all:
        print("\nAuto-approving pending communications...")
        approved = gate.approve_all(approved_by="dispatch_lead")
        print(f"  - Approved & Written:      {approved} -> outputs/comms_sent.jsonl")
    elif args.dashboard:
        gate.display_pending_summary()
        confirm = input("\nApprove all pending messages now? [y/N]: ").strip().lower()
        if confirm in ("y", "yes"):
            approved = gate.approve_all(approved_by="human_operator")
            print(f"Approved {approved} messages to outputs/comms_sent.jsonl.")


def main():
    parser = argparse.ArgumentParser(
        description="Meridian Freight Breakdown-to-Resolution Automation Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python run.py                     Launch full stack (Backend + Web UI)
  python run.py --cli               Run headless queue processor
  python run.py --approve-all       Run pipeline & approve all drafts
  python run.py --query "question"  Ask grounded questions with citations
  python run.py --surprise file.csv Ingest and process surprise ticket file
  python run.py --test              Run 92-test verification suite
"""
    )
    parser.add_argument("--cli", action="store_true", help="Run in headless CLI mode instead of launching web servers")
    parser.add_argument("--approve-all", action="store_true", help="Approve all pending client communications to comms_sent.jsonl")
    parser.add_argument("--query", type=str, help="Ask a grounded question with citations")
    parser.add_argument("--surprise", type=str, help="Process a surprise ticket file with schema drift adaptation")
    parser.add_argument("--dashboard", action="store_true", help="Launch interactive human approval dashboard in terminal")
    parser.add_argument("--test", action="store_true", help="Run automated verification test suite")

    args = parser.parse_args()

    # If any CLI-specific option is requested, run in headless mode
    if args.cli or args.approve_all or args.query or args.surprise or args.dashboard or args.test:
        run_headless_cli(args)
    else:
        run_full_stack()


if __name__ == "__main__":
    main()
