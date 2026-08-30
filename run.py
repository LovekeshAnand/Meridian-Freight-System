"""Meridian Freight Breakdown-to-Resolution Automation Platform.

One documented command to run the entire system:
  python run.py

Options:
  python run.py                     # Run end-to-end breakdown pipeline
  python run.py --approve-all       # Run pipeline & approve all client communications
  python run.py --query "question"  # Ask grounded questions with exact citations
  python run.py --surprise <path>   # Process surprise ticket file with drift adapter
  python run.py --dashboard         # Open interactive human approval dashboard
  python run.py --test              # Run full verification test suite
"""
import argparse
import json
import sys
from pathlib import Path

from src.pipeline.processor import BreakdownPipeline
from src.ui.dashboard import ApprovalGate
from src.query.engine import GroundedQueryEngine
from src.surprise.drift_adapter import SurpriseDriftAdapter

def main():
    parser = argparse.ArgumentParser(description="Meridian Freight Breakdown-to-Resolution Automation")
    parser.add_argument("--approve-all", action="store_true", help="Approve all pending client communications to comms_sent.jsonl")
    parser.add_argument("--query", type=str, help="Ask a grounded question with citations")
    parser.add_argument("--surprise", type=str, help="Process a surprise ticket file with schema drift adaptation")
    parser.add_argument("--dashboard", action="store_true", help="Launch interactive human approval dashboard")
    parser.add_argument("--test", action="store_true", help="Run automated verification test suite")

    args = parser.parse_args()

    print("===================================================================")
    print("        MERIDIAN FREIGHT - BREAKDOWN RESOLUTION AUTOMATION        ")
    print("===================================================================")

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
        print(f"\nQuestion: {res['question']}")
        print(f"Answer:   {res['answer']}")
        print(f"Citations: {', '.join(res['citations']) if res['citations'] else 'None'}")
        print(f"Grounded: {'YES' if res['is_sufficient'] else 'INSUFFICIENT DATA'}")
        return

    if args.surprise:
        surprise_path = Path(args.surprise)
        print(f"Processing surprise ticket file: {surprise_path}")
        records, alerts = SurpriseDriftAdapter.adapt_file(surprise_path)
        print(f"Detected {len(records)} records. Drift alerts: {alerts}")
        
        # Save temp normalized JSON
        temp_path = Path("d:/meridian/data/temp_surprise.json")
        temp_path.write_text(json.dumps(records), encoding="utf-8")
        
        pipeline = BreakdownPipeline()
        res = pipeline.process_ticket_queue(temp_path)
        print(f"\nSurprise Processing Result: {res}")
        return

    # Default: Run Main Pipeline
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
    else:
        print("\nNote: Draft messages queued in outputs/comms_pending.jsonl.")
        print("To review & approve communications to outputs/comms_sent.jsonl, run:")
        print("  python run.py --approve-all   OR   python run.py --dashboard")

if __name__ == "__main__":
    main()
