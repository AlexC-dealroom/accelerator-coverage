#!/usr/bin/env python3
"""
Append company-level discovery / portfolio-work rows to data/discovery_log.jsonl
(append-only — one row per company action per accelerator). This is where the
itemized work lives for any accelerator, measured or not (e.g. Inovativa's demoday
companies), independent of whether we can compute a coverage %.

Single row via flags, or bulk via --json-file (a JSON array of row objects).

Row shape:
  {date, accelerator_uuid, accelerator, company, domain, action, cohort, dealroom_url}
  action ∈ created | linked | already_present | to_add | to_link

Examples:
  python3 scripts/record_discovery.py --accelerator-uuid ae4744d1... --accelerator "Inovativa Brasil" \
    --company "Work Resíduos" --action to_add --cohort "Ciclo 2025 demoday"
  python3 scripts/record_discovery.py --json-file /tmp/inovativa_rows.json
"""
import argparse, json, os, datetime

BASE = os.path.join(os.path.dirname(__file__), "..")
ACTIONS = ["created", "linked", "already_present", "to_add", "to_link"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="brazil")
    ap.add_argument("--json-file", help="JSON array of row objects to append (bulk)")
    ap.add_argument("--accelerator-uuid")
    ap.add_argument("--accelerator")
    ap.add_argument("--company")
    ap.add_argument("--domain", default=None)
    ap.add_argument("--action", choices=ACTIONS)
    ap.add_argument("--cohort", default=None)
    ap.add_argument("--dealroom-url", default=None)
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    a = ap.parse_args()
    LOG = os.path.join(BASE, "data", f"{a.region}_discovery_log.jsonl")

    if a.json_file:
        rows = json.load(open(a.json_file))
        for r in rows:
            r.setdefault("date", a.date)
            if r.get("action") not in ACTIONS:
                ap.error(f"invalid action {r.get('action')!r}; must be one of {ACTIONS}")
    else:
        if not (a.accelerator_uuid and a.company and a.action):
            ap.error("need --accelerator-uuid, --company and --action (or --json-file)")
        rows = [{
            "date": a.date, "accelerator_uuid": a.accelerator_uuid, "accelerator": a.accelerator,
            "company": a.company, "domain": a.domain, "action": a.action,
            "cohort": a.cohort, "dealroom_url": a.dealroom_url,
        }]

    with open(LOG, "a") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"appended {len(rows)} row(s) to {os.path.basename(LOG)}")

if __name__ == "__main__":
    main()
