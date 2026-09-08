#!/usr/bin/env python3
"""
Append ONE immutable coverage measurement to data/coverage_history.jsonl.

This is the only writer of history — it always APPENDS, never rewrites, so the
trend for each accelerator is preserved across re-checks.

Usage (a re-check produces these numbers):
  python3 scripts/record_measurement.py \
    --uuid <uuid> --name "HARDS" --method domain \
    --website 27 --linked 21 --unlinked 3 --absent 3 \
    --linkage 77.8 --company-low 88.9 --company-high 88.9 \
    --note "after Data Team linked 3 companies"

measured_at defaults to today. Only --uuid and --linkage are strictly required;
the rest are recorded when provided.
"""
import argparse, json, os, datetime

BASE = os.path.join(os.path.dirname(__file__), "..")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="brazil")
    ap.add_argument("--uuid", required=True)
    ap.add_argument("--name")
    ap.add_argument("--measured-at", default=datetime.date.today().isoformat())
    ap.add_argument("--method", default="name+country",
                    choices=["domain", "name+country", "manual"])
    ap.add_argument("--website", type=int)
    ap.add_argument("--linked", type=int)
    ap.add_argument("--unlinked", type=int)
    ap.add_argument("--absent", type=int)
    ap.add_argument("--linkage", type=float, required=True)
    ap.add_argument("--company-low", type=float)
    ap.add_argument("--company-high", type=float)
    ap.add_argument("--new-profiles", type=int, default=0,
                    help="profiles newly CREATED in Dealroom since the last check (not just linked)")
    ap.add_argument("--dealroom-portfolio", type=int, default=None,
                    help="the accelerator's TOTAL Dealroom portfolio count (production/MCP) at this check — the growth metric")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    HIST = os.path.join(BASE, "data", f"{a.region}_coverage_history.jsonl")

    rec = {
        "uuid": a.uuid, "name": a.name, "measured_at": a.measured_at,
        "method": a.method, "website_portfolio": a.website,
        "linked": a.linked, "present_unlinked": a.unlinked, "absent": a.absent,
        "linkage_coverage_pct": a.linkage,
        "company_coverage_low_pct": a.company_low,
        "company_coverage_high_pct": a.company_high,
        "new_profiles_created": a.new_profiles,
        "dealroom_portfolio": a.dealroom_portfolio,
        "note": a.note,
    }
    with open(HIST, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"appended to {os.path.basename(HIST)}:", json.dumps(rec, ensure_ascii=False))

if __name__ == "__main__":
    main()
