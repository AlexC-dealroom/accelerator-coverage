#!/usr/bin/env python3
"""
Seed / refresh data/<region>_cohort_schedule.json — the per-accelerator recurring
cohort month used for cohort-aligned re-check scheduling.

For every ACTIVE accelerator (tier TARGET or MAINTAIN) with estimated throughput
>= --min-throughput, it tries to infer the month a cohort/application cycle recurs,
from (in priority order):
  1. month-precise dates in the discovery log's cohort_source (e.g. "…2025-02",
     "Demoday 20-Aug-2024") — the most frequent month wins,
  2. the targeting evidence_date when it is month-precise ("YYYY-MM").
Year-only signals are ignored (no reliable month → left unscheduled, falls back to
the fixed cadence).

MERGES into any existing file: entries with "manual": true are never overwritten,
so you can hand-correct a month and re-run this freely.

Run:  python3 scripts/seed_cohort_schedule.py --region brazil
"""
import argparse, json, os, re
from collections import Counter

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data")
MONTHS = ["", "January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
ABBR = {m[:3].lower(): i for i, m in enumerate(MONTHS) if m}
ABBR.update({"sept": 9})

ap = argparse.ArgumentParser()
ap.add_argument("--region", default="brazil")
ap.add_argument("--min-throughput", type=float, default=10.0)
a = ap.parse_args()
REGION = a.region

def load(name, default=None):
    p = os.path.join(DATA, name)
    return json.load(open(p)) if os.path.exists(p) else default
def load_jsonl(name):
    p = os.path.join(DATA, name)
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []

def months_in(text):
    """Extract month numbers from a free-text date-ish string."""
    out = []
    if not text:
        return out
    for _y, mm in re.findall(r"\b20\d\d[-/](\d{1,2})\b", text):
        if 1 <= int(mm) <= 12:
            out.append(int(mm))
    for mm, _y in re.findall(r"\b(\d{1,2})[-/]20\d\d\b", text):
        if 1 <= int(mm) <= 12:
            out.append(int(mm))
    for tok in re.findall(r"[A-Za-z]{3,9}", text):
        if tok.lower() in ABBR:
            out.append(ABBR[tok.lower()])
    return out

targeting = load(f"{REGION}_targeting.json", []) or []
discovery = load_jsonl(f"{REGION}_discovery_log.jsonl")
existing = load(f"{REGION}_cohort_schedule.json", {}) or {}

coh_by_uuid = {}
for d in discovery:
    coh_by_uuid.setdefault(d.get("accelerator_uuid"), []).append(d.get("cohort") or "")

out = dict(existing)
seeded = []
for r in targeting:
    u = r["uuid"]
    tier = (r.get("priority_tier") or "").split(":")[0]
    thr = r.get("cohort_throughput_estimate")
    if tier not in ("TARGET", "MAINTAIN"):
        continue
    if not (isinstance(thr, (int, float)) and thr >= a.min_throughput):
        continue
    if existing.get(u, {}).get("manual"):
        continue  # respect hand-edited entries
    # 1) discovery cohort_source months
    cand = []
    for cs in coh_by_uuid.get(u, []):
        cand += months_in(cs)
    basis = None
    month = None
    if cand:
        month = Counter(cand).most_common(1)[0][0]
        basis = f"discovery cohort_source (months seen: {sorted(set(cand))})"
    else:
        ed = r.get("evidence_date") or ""
        mm = re.match(r"^20\d\d-(\d{2})$", str(ed))
        if mm:
            month = int(mm.group(1))
            basis = f"evidence_date {ed}"
    if not month:
        continue  # year-only / no signal -> leave to fixed cadence
    out[u] = {"name": r.get("name"), "cohort_month": month,
              "basis": basis, "manual": False}
    seeded.append(f'{r.get("name")}: {MONTHS[month]}')

json.dump(out, open(os.path.join(DATA, f"{REGION}_cohort_schedule.json"), "w"),
          ensure_ascii=False, indent=2)
print(f"[{REGION}] cohort schedule: {len(out)} entries ({len(seeded)} auto-seeded this run)")
for s in sorted(seeded):
    print("   ", s)
