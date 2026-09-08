#!/usr/bin/env python3
"""
Ingest a Scarlet scout run into a region's pipeline files. Handles two run types,
distinguished by the `read_only` flag in the participants (or accelerators) JSON:

  READ-ONLY BASELINE run  (accelerators + participants, read_only:true)
    - rebuilds the frame (<key>_accelerators.json, _targeting_batch_A.json,
      _cohort_schedule.json)
    - records a `baseline_scout` coverage row per accelerator w/ a DR entity
      (current DR portfolio + still-open sampled gap; linkage null)
    - discovery worklist of PROPOSED actions (to_link / to_add)
    - accelerators stay TARGET (gap open); baseline_scout is excluded from the
      "checked ⇒ Maintain" rule.

  WORKED run  (participants only, read_only:false — Scarlet wrote to Dealroom)
    - --accelerators may be omitted; the existing frame is loaded and its portfolio
      counts are bumped by the companies actually attached this run
    - records a `scarlet_write` coverage row (dealroom_portfolio=after, linked=joined,
      new_profiles_created=created) — counts as WORKED, so those accelerators flip to
      MAINTAIN via the aggregate rule
    - discovery rows of EXECUTED actions (created / linked)
  Idempotent: coverage rows keyed on (uuid, run_date); the portfolio bump is applied
  only when that worked row is newly added, so re-running is safe.

Run (baseline):  python3 scripts/ingest_scarlet.py --region nebraska \
                   --accelerators data/nebraska_accelerators_2026-08-27.json \
                   --participants data/nebraska_participants_2026-08-27.json
Run (worked):    python3 scripts/ingest_scarlet.py --region nebraska \
                   --participants data/nebraska_participants_2026-08-28.json
Then: aggregate_targeting.py --region <key> ; update_tracking.py --region <key> ; build_dashboard.py
"""
import argparse, json, os, re
from collections import defaultdict
from urllib.parse import urlparse

BASE = os.path.join(os.path.dirname(__file__), "..", "data")

ap = argparse.ArgumentParser()
ap.add_argument("--region", required=True)
ap.add_argument("--accelerators")
ap.add_argument("--participants")
a = ap.parse_args()
REGION = a.region

def slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
def norm(s):
    s = re.sub(r"\(.*?\)", "", s or "")
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
def domain_of(url):
    if not url: return None
    try:
        h = urlparse(url if url.startswith("http") else "https://" + url).hostname or ""
        return h.replace("www.", "") or None
    except Exception:
        return None
def fix_dealroom_url(url):
    if url and "/companies/" in url:   # accelerators are investors in Dealroom
        return url.replace("/companies/", "/investors/")
    return url or None
def load(name, default=None):
    p = os.path.join(BASE, name)
    return json.load(open(p)) if os.path.exists(p) else default
def write_json(name, obj):
    json.dump(obj, open(os.path.join(BASE, name), "w"), ensure_ascii=False, indent=2)
def load_jsonl(name):
    p = os.path.join(BASE, name)
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []
def append_jsonl(name, rows, key_fields):
    path = os.path.join(BASE, name)
    have = {tuple(r.get(k) for k in key_fields) for r in load_jsonl(name)}
    n = 0
    with open(path, "a") as f:
        for r in rows:
            k = tuple(r.get(kf) for kf in key_fields)
            if k in have: continue
            have.add(k); f.write(json.dumps(r, ensure_ascii=False) + "\n"); n += 1
    return n

parts_doc = json.load(open(a.participants)) if a.participants else {}
parts = parts_doc.get("participants", [])
acc_doc = json.load(open(a.accelerators)) if a.accelerators else {}
read_only = parts_doc.get("read_only", acc_doc.get("read_only", True))
run_date = parts_doc.get("run_date") or acc_doc.get("run_date")

def key_for(x):
    return x.get("dealroom_uuid") or f"noid-{slug(x['accelerator'])}"

# ---------- FRAME ----------
skipped_scope = []
if a.accelerators:
    accels = [x for x in acc_doc.get("accelerators", [])
              if not (x.get("national_tracked") or x.get("in_scope") is False)]
    skipped_scope = [x["accelerator"] for x in acc_doc.get("accelerators", [])
                     if x.get("national_tracked") or x.get("in_scope") is False]
    accelerators_json, batch, cohort_sched = [], [], {}
    for x in accels:
        uuid = key_for(x); website = x.get("website") or None
        accelerators_json.append({
            "uuid": uuid, "name": x["accelerator"], "city": x.get("city"),
            "website": website, "domain": domain_of(website), "hq_country": "United States",
            "dealroom_portfolio": x.get("dealroom_portfolio_count"), "last_round_year": None,
            "investor_types": ["accelerator"], "dealroom_url": fix_dealroom_url(x.get("dealroom_profile_url")),
        })
        batch.append({
            "name": x["accelerator"], "uuid": uuid, "website": website,
            "website_status": x.get("website_status"), "is_accelerator": True,
            "activity_status": x.get("activity_status") or "active",
            "cohort_throughput_estimate": x.get("est_startups_per_year"),
            "website_matches_dealroom": x.get("website_status") == "live_and_relevant",
            "evidence": x.get("evidence"), "evidence_url": x.get("evidence_url"),
            "evidence_date": x.get("evidence_date"), "confidence": x.get("confidence"),
        })
        if x.get("cohort_month"):
            cohort_sched[uuid] = {"name": x["accelerator"], "cohort_month": int(x["cohort_month"]),
                                  "basis": f"scarlet scout ({x.get('cohort_timing_type','?')})", "manual": False}
    write_json(f"{REGION}_accelerators.json", accelerators_json)
    write_json(f"{REGION}_targeting_batch_A.json", batch)
    write_json(f"{REGION}_cohort_schedule.json", cohort_sched)
else:
    accelerators_json = load(f"{REGION}_accelerators.json", [])
    if not accelerators_json:
        raise SystemExit(f"No frame found (data/{REGION}_accelerators.json). Provide --accelerators for the first run.")

frame = {x["uuid"]: x for x in accelerators_json}
norm_to_key = {norm(x["name"]): x["uuid"] for x in accelerators_json}
def match_key(nm):
    n = norm(nm)
    if n in norm_to_key: return norm_to_key[n]
    for kn, key in norm_to_key.items():
        if n and (kn.startswith(n) or n.startswith(kn)): return key
    return None

by_key = defaultdict(list)
for p in parts:
    mk = match_key(p.get("accelerator", ""))
    (by_key[mk] if mk else print("  ! participant unmatched:", p.get("accelerator"))) and None
    if mk: by_key[mk].append(p)

# ---------- COVERAGE + DISCOVERY ----------
hist_have = {(m.get("uuid"), m.get("measured_at")) for m in load_jsonl(f"{REGION}_coverage_history.jsonl")}
history_rows, discovery_rows = [], []
BASE_ACT = {"link_existing": "to_link", "create_new": "to_add", "none": "already_present", "review": "to_add"}
WORK_ACT = {"created": "created", "in_dr_linked_round": "linked", "in_dr_unlinked": "linked", "round_added": "linked"}

if read_only:
    for uuid, x in frame.items():
        pf = x.get("dealroom_portfolio")
        rows = by_key.get(uuid, [])
        n_unlinked = sum(1 for p in rows if p.get("dealroom_verdict") == "in_dr_unlinked")
        n_absent = sum(1 for p in rows if p.get("dealroom_verdict") == "absent")
        if pf is not None and (uuid, run_date) not in hist_have:
            note = f"read-only scout baseline (Scarlet). DR portfolio {pf}."
            if rows: note += f" Recent cohort sample: {n_unlinked} in-DR-unlinked + {n_absent} absent, pending."
            history_rows.append({"uuid": uuid, "name": x["name"], "measured_at": run_date,
                "method": "baseline_scout", "website_portfolio": None, "linked": None,
                "present_unlinked": n_unlinked or None, "absent": n_absent or None,
                "linkage_coverage_pct": None, "company_coverage_low_pct": None,
                "company_coverage_high_pct": None, "new_profiles_created": 0,
                "dealroom_portfolio": pf, "note": note})
        for p in rows:
            discovery_rows.append({"date": run_date, "accelerator_uuid": uuid, "accelerator": x["name"],
                "company": p.get("company_name"), "domain": domain_of(p.get("website")),
                "action": BASE_ACT.get(p.get("proposed_action"), "to_add"),
                "cohort": p.get("cohort_source"), "dealroom_url": p.get("dealroom_url") or None})
else:
    for uuid, rows in by_key.items():
        x = frame.get(uuid)
        if not x: continue
        created = sum(1 for p in rows if p.get("dealroom_verdict") == "created")
        joined = sum(1 for p in rows if p.get("support_program_round")
                     or p.get("dealroom_verdict") in ("created", "in_dr_linked_round"))
        before = x.get("dealroom_portfolio") or 0
        after = before + joined
        if (uuid, run_date) not in hist_have:
            x["dealroom_portfolio"] = after   # bump frame (persisted below)
            history_rows.append({"uuid": uuid, "name": x["name"], "measured_at": run_date,
                "method": "scarlet_write", "website_portfolio": None, "linked": joined,
                "present_unlinked": None, "absent": None, "linkage_coverage_pct": None,
                "company_coverage_low_pct": None, "company_coverage_high_pct": None,
                "new_profiles_created": created, "dealroom_portfolio": after,
                "note": f"Scarlet write run: +{created} profiles created, {joined} companies attached ({before}->{after})."})
        for p in rows:
            discovery_rows.append({"date": run_date, "accelerator_uuid": uuid, "accelerator": x["name"],
                "company": p.get("company_name"), "domain": domain_of(p.get("website")),
                "action": WORK_ACT.get(p.get("dealroom_verdict"), "linked"),
                "cohort": p.get("cohort_source"), "dealroom_url": p.get("dealroom_url") or None})
    write_json(f"{REGION}_accelerators.json", accelerators_json)  # persist portfolio bumps

nh = append_jsonl(f"{REGION}_coverage_history.jsonl", history_rows, ("uuid", "measured_at"))
nd = append_jsonl(f"{REGION}_discovery_log.jsonl", discovery_rows, ("accelerator_uuid", "company", "date"))

mode = "READ-ONLY baseline" if read_only else "WORKED (post-write)"
print(f"[{REGION}] ingested Scarlet {mode} run {run_date}: {len(frame)} accelerators in frame, {len(parts)} participants")
print(f"  coverage rows appended: {nh} ({'baseline_scout' if read_only else 'scarlet_write'}); discovery rows appended: {nd}")
if not read_only:
    for uuid, rows in by_key.items():
        x = frame.get(uuid)
        if x: print(f"    {x['name'][:34]:<35} DR pf -> {x.get('dealroom_portfolio')}")
if skipped_scope: print("  skipped (national-tracked/out-of-scope): " + "; ".join(skipped_scope))
for e in (acc_doc.get("excluded") or []): print(f"  excluded by Scarlet: {e['accelerator']}")
for h in (parts_doc.get("held_no_domain") or []): print(f"  held (no domain): {h['company_name']} [{h['accelerator']}]")
