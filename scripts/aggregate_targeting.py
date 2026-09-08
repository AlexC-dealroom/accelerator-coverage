#!/usr/bin/env python3
"""
Aggregate the per-batch accelerator classifications into one ranked target list.

Reads:
  data/<region>_targeting_batch_*.json  (written by the classifier agents)
  data/<region>_accelerators.json       (Dealroom context: portfolio size, last round, domain)

Writes:
  data/<region>_targeting.json          (full merged + scored list)

Prioritisation aligned to the goal (discover early-stage companies to add):
  target = a genuine accelerator, currently ACTIVE, that we UNDER-cover.
  Activity is judged from the accelerator's own program signals (the agents),
  never from Dealroom's own data.

Run:  python3 scripts/aggregate_targeting.py --region colorado
"""
import json, glob, os, argparse

BASE = os.path.join(os.path.dirname(__file__), "..", "data")

ap = argparse.ArgumentParser()
ap.add_argument("--region", default="brazil")
REGION = ap.parse_args().region

def load(name):
    p = os.path.join(BASE, name)
    return json.load(open(p)) if os.path.exists(p) else None

# Dealroom context by uuid
ctx = {a["uuid"]: a for a in load(f"{REGION}_accelerators.json")}

# Accelerators we've already CHECKED (>=1 coverage-history record). Once mined, the
# findable participant pool is usually smaller than throughput implies, so the
# Target/Maintain line blurs — checked TARGETs default to MAINTAIN (an override can
# pin a genuine remaining gap back to TARGET).
def load_jsonl(name):
    p = os.path.join(BASE, name)
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []
# "checked" = actually WORKED (a coverage measurement / mining pass), NOT a mere
# read-only scout baseline — a baseline records the current gap without closing it,
# so those accelerators stay TARGET until the gap is worked.
checked = {m.get("uuid") for m in load_jsonl(f"{REGION}_coverage_history.jsonl")
           if m.get("method") != "baseline_scout"}

# Merge all batch files
rows = []
found_batches = []
for path in sorted(glob.glob(os.path.join(BASE, f"{REGION}_targeting_batch_*.json"))):
    found_batches.append(os.path.basename(path))
    for r in json.load(open(path)):
        c = ctx.get(r.get("uuid"), {})
        r["dealroom_portfolio"] = c.get("dealroom_portfolio")
        r["last_round_year"] = c.get("last_round_year")
        r["city"] = c.get("city")
        r["dealroom_url"] = c.get("dealroom_url")
        rows.append(r)

def tier(r):
    if not r.get("is_accelerator"):
        return "DROP: not an accelerator"
    if r.get("activity_status") == "defunct":
        return "DROP: defunct"
    if r.get("activity_status") in ("dormant", "unknown"):
        return "PARK: dormant/unknown"
    # active + genuine accelerator
    pf = r.get("dealroom_portfolio") or 0
    return "TARGET: active + under-covered" if pf <= 5 else "MAINTAIN: active + covered"

def gap_score(r):
    """Higher = bigger discovery opportunity."""
    if not (r.get("is_accelerator") and r.get("activity_status") == "active"):
        return -1
    thr = r.get("cohort_throughput_estimate")
    pf = r.get("dealroom_portfolio") or 0
    if isinstance(thr, (int, float)):
        return max(thr - pf, 0) + (thr * 0.1)   # gap, tie-broken by size
    # unknown throughput: rank by how little we cover (small pf = bigger presumed gap)
    return max(30 - pf, 0)

# optional manual overrides: {uuid: {"tier": "MAINTAIN", "note": "...", "no_due_date": true}}
overrides = load(f"{REGION}_overrides.json") or {}

for r in rows:
    r["priority_tier"] = tier(r)
    # checked TARGETs default down to MAINTAIN (findable gap smaller than it looks)
    if r.get("uuid") in checked and r["priority_tier"].startswith("TARGET"):
        r["priority_tier"] = "MAINTAIN: checked — findable gap smaller than throughput implies"
        r["checked_downgrade"] = True
    r["gap_score"] = round(gap_score(r), 1)
    ov = overrides.get(r.get("uuid"))
    if ov and ov.get("tier"):
        r["priority_tier"] = f'{ov["tier"]}: {ov.get("note", "manual override")}'
        r["tier_override"] = True

order = {"TARGET": 0, "MAINTAIN": 1, "PARK": 2, "DROP": 3}
rows.sort(key=lambda r: (order[r["priority_tier"].split(":")[0]], -r["gap_score"]))

json.dump(rows, open(os.path.join(BASE, f"{REGION}_targeting.json"), "w"),
          ensure_ascii=False, indent=2)

# ---- report ----
def count(pred): return sum(1 for r in rows if pred(r))
print(f"[{REGION}] Batches found: {found_batches}  ({len(rows)}/{len(ctx)} accelerators)")
print(f"\n  TARGET (active, under-covered): {count(lambda r: r['priority_tier'].startswith('TARGET'))}")
print(f"  MAINTAIN (active, covered):     {count(lambda r: r['priority_tier'].startswith('MAINTAIN'))}")
print(f"  PARK (dormant/unknown):         {count(lambda r: r['priority_tier'].startswith('PARK'))}")
print(f"  DROP (not-accel/defunct):       {count(lambda r: r['priority_tier'].startswith('DROP'))}")
print(f"  Stale/wrong website on file:    {count(lambda r: r.get('website_matches_dealroom') is False)}")

print(f"\n{'Accelerator':<26}{'Tier':<34}{'DR pf':>6}{'thr':>5}  activity")
print("-"*90)
for r in rows:
    thr = r.get("cohort_throughput_estimate")
    print(f"{r['name'][:25]:<26}{r['priority_tier']:<34}{str(r.get('dealroom_portfolio')):>6}{str(thr) if thr is not None else '-':>5}  {r.get('activity_status')}")
