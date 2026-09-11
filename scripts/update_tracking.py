#!/usr/bin/env python3
"""
Maintain data/accelerator_tracking.json — the DURABLE, per-accelerator tracking
state (recommended checking cadence + next-due), keyed by UUID.

- Suggests a default cadence from tier + activity + throughput (fixed-days).
- MERGES into any existing file: never clobbers an entry whose "manual_override"
  is true, and preserves owner/status/notes fields.
- Recomputes next_due = last measured date (from coverage_history.jsonl) + cadence;
  if never measured, next_due = today (i.e. due for a baseline).

Run:  python3 scripts/update_tracking.py --region colorado
"""
import json, os, datetime, calendar, argparse

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data")
TODAY = datetime.date.today()
MONTHS = ["", "January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]

ap = argparse.ArgumentParser()
ap.add_argument("--region", default="brazil")
ap.add_argument("--cohort-min-throughput", type=float, default=10.0,
                help="active accelerators at/above this throughput use cohort-aligned dates when a cohort month is known")
args = ap.parse_args()
REGION = args.region

def next_cohort_due(anchor, month):
    """First end-of-<month> strictly after `anchor` (a date)."""
    for yy in (anchor.year, anchor.year + 1, anchor.year + 2):
        end = datetime.date(yy, month, calendar.monthrange(yy, month)[1])
        if end > anchor:
            return end.isoformat()

def load(name, default):
    p = os.path.join(DATA, name)
    return json.load(open(p)) if os.path.exists(p) else default

def load_jsonl(name):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p) if l.strip()]

targeting = load(f"{REGION}_targeting.json", [])
history = load_jsonl(f"{REGION}_coverage_history.jsonl")
existing = load(f"{REGION}_accelerator_tracking.json", {})
overrides = load(f"{REGION}_overrides.json", {})  # {uuid: {no_due_date, note, ...}}
cohort_sched = load(f"{REGION}_cohort_schedule.json", {})  # {uuid: {cohort_month, basis, ...}}

# latest measurement date per uuid
last_by = {}
for m in history:
    u = m.get("uuid")
    d = m.get("measured_at")
    if u and d and d > last_by.get(u, ""):
        last_by[u] = d

def tier_of(r):
    return (r.get("priority_tier") or "").split(":")[0]

def suggest(r):
    """Return (cadence_days_or_None, basis)."""
    t = tier_of(r)
    if t == "DROP":
        return None, "not tracked (dropped)"
    if t == "PARK":
        return None, "dormant — not re-checked"
    if t == "MAINTAIN":
        return 180, "active + already covered — semiannual light check"
    # TARGET
    thr = r.get("cohort_throughput_estimate")
    if not isinstance(thr, (int, float)):
        return 180, "active target, throughput unknown — semiannual default"
    if thr >= 100:
        return 90, f"very high throughput (~{thr}/yr) — quarterly"
    if thr >= 30:
        return 120, f"high throughput (~{thr}/yr) — every 4 months"
    if thr >= 10:
        return 180, f"moderate throughput (~{thr}/yr) — semiannual"
    return 365, f"low throughput (~{thr}/yr) — annual"

def add_days(d_iso, days):
    y, m, dd = map(int, d_iso.split("-"))
    return (datetime.date(y, m, dd) + datetime.timedelta(days=days)).isoformat()

out = {}
for r in targeting:
    u = r["uuid"]
    prev = existing.get(u, {})
    cad, basis = suggest(r)
    # respect a manual cadence override
    if prev.get("manual_override") and prev.get("recommended_cadence_days") is not None:
        cad = prev["recommended_cadence_days"]
        basis = prev.get("cadence_basis", basis) + " (manual)"
    last = last_by.get(u)
    if cad is None:
        next_due = None
        status = prev.get("status", "not_tracked")
    elif last:
        next_due = add_days(last, cad)
        status = prev.get("status", "measured")
    else:
        next_due = TODAY.isoformat()          # due for a baseline measurement
        status = prev.get("status", "unmeasured")
    schedule_mode = "none" if cad is None else "cadence"
    # cohort-aligned scheduling: active, higher-throughput sources with a known
    # recurring cohort month get checked at that month's end (next occurrence)
    # instead of a flat cadence, catching the freshly-named cohort to mine.
    thr = r.get("cohort_throughput_estimate")
    cmonth = (cohort_sched.get(u) or {}).get("cohort_month")
    if (cmonth and cad is not None and tier_of(r) in ("TARGET", "MAINTAIN")
            and isinstance(thr, (int, float)) and thr >= args.cohort_min_throughput):
        anchor = TODAY
        if last:  # don't reschedule into a cohort month we just checked in
            ly, lm, ld = map(int, last.split("-"))
            anchor = max(TODAY, datetime.date(ly, lm, ld) + datetime.timedelta(days=60))
        next_due = next_cohort_due(anchor, int(cmonth))
        basis = f"cohort-aligned: end of {MONTHS[int(cmonth)]} (~{int(thr)}/yr cohort cycle)"
        schedule_mode = "cohort"
        status = prev.get("status", "scheduled")
    # an explicit next_due_override wins over the cadence-derived date
    override = prev.get("next_due_override")
    if override:
        next_due = override
        status = prev.get("status", "scheduled")
        basis = f"manually scheduled for {override}"
        schedule_mode = "override"
    # a manual "no_due_date" override (e.g. low-activity, maintenance only) wins outright
    ov = overrides.get(u)
    if ov and ov.get("no_due_date"):
        cad = None
        next_due = None
        override = None
        basis = ov.get("note", "maintenance only — no re-check schedule")
        status = "maintenance"
        schedule_mode = "none"
    out[u] = {
        "uuid": u,
        "name": r.get("name"),
        "recommended_cadence_days": cad,
        "cadence_basis": basis,
        "schedule_mode": schedule_mode,
        "last_checked": last,
        "next_due": next_due,
        "next_due_override": override,
        "status": status,
        "owner": prev.get("owner"),
        "notes": prev.get("notes"),
        "manual_override": prev.get("manual_override", False),
    }

json.dump(out, open(os.path.join(DATA, f"{REGION}_accelerator_tracking.json"), "w"),
          ensure_ascii=False, indent=2)

tracked = [v for v in out.values() if v["recommended_cadence_days"]]
overdue = [v for v in tracked if v["next_due"] and v["next_due"] <= TODAY.isoformat()]
print(f"[{REGION}] Tracking {len(tracked)} accelerators; {len(overdue)} due/overdue as of {TODAY}.")
from collections import Counter
c = Counter(v["recommended_cadence_days"] for v in tracked)
print("Cadence distribution (days):", dict(sorted(c.items())))
cohort = [v for v in out.values() if v.get("schedule_mode") == "cohort"]
if cohort:
    print(f"Cohort-aligned schedules ({len(cohort)}):")
    for v in sorted(cohort, key=lambda x: x["next_due"]):
        print(f'   {v["name"][:26]:<27} {v["next_due"]}  — {v["cadence_basis"]}')
