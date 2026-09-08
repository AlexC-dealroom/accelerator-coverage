#!/usr/bin/env python3
"""
Normalize a Scarlet scout run in ANY of the observed schema variants into the
canonical `accelerator_coverage.*.v1` shape that ingest_scarlet.py consumes, so a
single ingester handles every state.

Variants seen:
  - v1-native (Nebraska): already canonical (accelerators[] w/ dealroom_uuid, cohort_month,
    est_startups_per_year as number, website_status). Passed through.
  - v2-meta (Wyoming/Kansas): a meta{} block + accelerators[] with `dealroom_entity`
    string, `throughput_estimate` string, `latest_cohort_date`, no per-accel uuid,
    `verdict`; participants[] with dr_status/verdict and NO accelerator field.
  - flat (Delaware): top-level accelerators[] with real `dealroom_uuid`,
    `throughput_per_cohort` + `cohort_frequency`, `last_cohort_date`; participants[]
    with an accelerator field + dealroom_status.

Out-of-scope skips (accelerators): national-program UUIDs (gener8tor 94d58b92…,
Techstars), cohort_based==false, "OUT OF SCOPE" / "not assessed" in notes/entity.
Participants belonging to a skipped accelerator are dropped too.

Run:  python3 scripts/normalize_scarlet.py --state kansas \
        --accelerators <raw_acc.json> --participants <raw_part.json> --out-dir <dir>
Writes <dir>/<state>_norm_accelerators.json + _norm_participants.json, then:
  ingest_scarlet.py --region <state> --accelerators <..norm_acc> --participants <..norm_part>
"""
import argparse, json, os, re

NATIONAL_UUIDS = {
    "94d58b92-48f4-445b-8d5a-1562e65afa11",  # gener8tor (national)
}
UUID_RE = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})")
URL_RE = re.compile(r"(https://app\.dealroom\.co/[^\s)]+)")

ap = argparse.ArgumentParser()
ap.add_argument("--state", required=True)
ap.add_argument("--accelerators", required=True)
ap.add_argument("--participants", required=True)
ap.add_argument("--out-dir", required=True)
a = ap.parse_args()

acc_raw = json.load(open(a.accelerators))
part_raw = json.load(open(a.participants))

def city_of(location):
    if not location:
        return None
    return location.split("(")[0].split(",")[0].strip() or None

def first_int(s):
    m = re.search(r"(\d+)", str(s or ""))
    return int(m.group(1)) if m else None

def month_of(d):
    m = re.match(r"^(\d{4})-(\d{2})", str(d or ""))
    return int(m.group(2)) if m else None

def norm(s):
    s = re.sub(r"\(.*?\)", "", s or "")
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

meta = acc_raw.get("meta", {})
is_v2 = bool(meta)
read_only = meta.get("read_only", acc_raw.get("read_only", True))
run_date = meta.get("generated_on") or (acc_raw.get("generated_at") or "")[:10]

norm_accels, skipped = [], []
for x in acc_raw.get("accelerators", []):
    name = x.get("name")
    notes = (x.get("notes") or "")
    if is_v2:
        entity = x.get("dealroom_entity") or ""
        uu = UUID_RE.search(entity)
        uuid = uu.group(1) if uu else ""
        urlm = URL_RE.search(entity)
        prof = urlm.group(1) if urlm else ""
        pf = x.get("dealroom_portfolio_total")
        est = first_int(x.get("throughput_estimate"))
        cmonth = month_of(x.get("latest_cohort_date"))
        wstatus = x.get("website_status") or "live_and_relevant"
        evidence = notes or x.get("type")
        out_of_scope = (x.get("cohort_based") is False
                        or "out of scope" in notes.lower()
                        or "out of scope" in entity.lower()
                        or "not assessed" in entity.lower())
    else:  # flat (Delaware)
        uuid = x.get("dealroom_uuid") or ""
        prof = x.get("dealroom_profile_url") or ""
        pf = x.get("dealroom_portfolio_count")
        pf = None if pf in ("", None) else pf
        per = x.get("throughput_per_cohort")
        mult = 2 if "twice" in (x.get("cohort_frequency") or "").lower() else 1
        est = per * mult if isinstance(per, (int, float)) else None
        cmonth = month_of(x.get("last_cohort_date"))
        wstatus = "live_and_relevant"
        evidence = x.get("description")
        out_of_scope = False
    if uuid in NATIONAL_UUIDS or out_of_scope:
        skipped.append(name); continue
    norm_accels.append({
        "accelerator": name, "state": a.state.title(), "city": city_of(x.get("location")),
        "website": x.get("website"), "website_status": wstatus,
        "activity_status": x.get("activity_status") or "active",
        "est_startups_per_year": est, "dealroom_portfolio_count": pf,
        "cohort_month": cmonth, "cohort_timing_type": "cohort",
        "most_recent_cohort": x.get("latest_cohort") or x.get("last_cohort_name"),
        "dealroom_uuid": uuid, "dealroom_profile_url": prof,
        "evidence": evidence, "evidence_url": x.get("source_url"),
        "evidence_date": x.get("source_date"), "confidence": x.get("confidence"),
    })

in_scope_names = {norm(x["accelerator"]) for x in norm_accels}

# primary accelerator for v2 (participants carry no accelerator field)
primary = None
if is_v2 and norm_accels:
    scanned = norm(meta.get("cohort_scanned", ""))
    for x in norm_accels:
        if norm(x["accelerator"]) and (norm(x["accelerator"]) in scanned or scanned.startswith(norm(x["accelerator"]))):
            primary = x["accelerator"]; break
    primary = primary or norm_accels[0]["accelerator"]

VERDICT = {  # dr_status/dealroom_status -> (dealroom_verdict, proposed_action)
    "in_dr_linked": ("in_dr_linked", "none"),
    "in_dr_unlinked": ("in_dr_unlinked", "link_existing"),
    "absent": ("absent", "create_new"),
    "unknown": ("ambiguous", "review"),
    "": ("ambiguous", "review"),
}

norm_parts, dropped_parts = [], 0
for p in part_raw.get("participants", []):
    accel = p.get("accelerator") or primary
    if norm(accel) not in in_scope_names:  # participant of a skipped accelerator
        dropped_parts += 1; continue
    if is_v2:
        status = p.get("dr_status", "")
        website = ("https://" + p["domain"]) if p.get("domain") else ""
        cohort = meta.get("cohort_scanned", "")
    else:
        status = p.get("dealroom_status", "")
        website = p.get("website") or ""
        cohort = p.get("cohort") or ""
    verdict, action = VERDICT.get(status, ("ambiguous", "review"))
    # honor an explicit review verdict from the source
    if (p.get("verdict") or p.get("proposed_action")) == "review":
        action = "review"
    norm_parts.append({
        "accelerator": accel, "company_name": p.get("company") or p.get("name"),
        "website": website, "linkedin": p.get("linkedin", ""),
        "dealroom_verdict": verdict, "proposed_action": action,
        "dealroom_url": (f"https://app.dealroom.co/companies/{p['dealroom_path']}"
                         if p.get("dealroom_path") else ""),
        "cohort_source": cohort, "confidence": p.get("confidence", ""),
        "notes": p.get("note") or p.get("notes", ""),
    })

os.makedirs(a.out_dir, exist_ok=True)
accf = os.path.join(a.out_dir, f"{a.state}_norm_accelerators.json")
parf = os.path.join(a.out_dir, f"{a.state}_norm_participants.json")
json.dump({"schema": "accelerator_coverage.accelerators.v1", "state": a.state.title(),
           "run_date": run_date, "read_only": read_only, "accelerators": norm_accels},
          open(accf, "w"), ensure_ascii=False, indent=2)
json.dump({"schema": "accelerator_coverage.participants.v1", "state": a.state.title(),
           "run_date": run_date, "read_only": read_only, "participants": norm_parts},
          open(parf, "w"), ensure_ascii=False, indent=2)

print(f"[{a.state}] schema={'v2-meta' if is_v2 else 'flat'} read_only={read_only} run_date={run_date}")
print(f"  in-scope accelerators: {len(norm_accels)} -> " + "; ".join(
    f"{x['accelerator'][:30]} (pf={x['dealroom_portfolio_count']},~{x['est_startups_per_year']}/yr,m{x['cohort_month']})" for x in norm_accels))
print(f"  skipped (out-of-scope/national): {skipped or 'none'}")
print(f"  participants: {len(norm_parts)} in-scope ({dropped_parts} dropped as out-of-scope)")
print(f"  wrote {accf}\n         {parf}")
