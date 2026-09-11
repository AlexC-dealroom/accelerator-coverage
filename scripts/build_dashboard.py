#!/usr/bin/env python3
"""
Build a self-contained, MULTI-REGION dashboard.html from the targeting + proof
outputs. Embeds every region's data inline so the file opens directly in a
browser (no server). A location dropdown at the top switches between regions,
plus an "All locations" option that pools them.

Regions are declared in data/regions.json:  [{"key","name","country"}, ...]
Each region <key> uses these files (all optional except targeting):
  data/<key>_targeting.json
  data/<key>_coverage_history.jsonl
  data/<key>_accelerator_tracking.json
  data/<key>_proof_summary.json

Run:  python3 scripts/build_dashboard.py
"""
import json, os, datetime
from collections import defaultdict

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data")

def load(name, default=None):
    p = os.path.join(DATA, name)
    return json.load(open(p)) if os.path.exists(p) else default

def load_jsonl(name):
    p = os.path.join(DATA, name)
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def build_coverage(history):
    """From an append-only history list, return (coverage_by_uuid, pooled_trend)."""
    byu = defaultdict(list)
    for m in history:
        byu[m["uuid"]].append(m)
    coverage = {}
    for u, ms in byu.items():
        ms = sorted(ms, key=lambda x: x["measured_at"])
        latest = ms[-1]
        prev = ms[-2] if len(ms) > 1 else None
        recs = []
        _pl = None
        for m in ms:
            lk = m.get("linkage_coverage_pct")
            recs.append({
                "date": m["measured_at"], "linkage": lk,
                "company_low": m.get("company_coverage_low_pct"),
                "company_high": m.get("company_coverage_high_pct"),
                "website": m.get("website_portfolio"), "linked": m.get("linked"),
                "new_profiles": m.get("new_profiles_created") or 0,
                "dealroom_portfolio": m.get("dealroom_portfolio"),
                "method": m.get("method"), "note": m.get("note", ""),
                "delta": round(lk - _pl, 1) if (lk is not None and _pl is not None) else None,
            })
            if lk is not None:
                _pl = lk
        _lpf = latest.get("dealroom_portfolio")
        _ppf = prev.get("dealroom_portfolio") if prev else None
        coverage[u] = {
            "records": recs,
            "latest_portfolio": _lpf,
            "portfolio_delta": (_lpf - _ppf) if (_lpf is not None and _ppf is not None) else None,
            "portfolio_series": [{"date": m["measured_at"], "count": m.get("dealroom_portfolio")} for m in ms],
            "series": [{"date": m["measured_at"], "linkage": m.get("linkage_coverage_pct"),
                        "method": m.get("method")} for m in ms],
            "latest_linkage": latest.get("linkage_coverage_pct"),
            "latest_date": latest["measured_at"],
            "latest_method": latest.get("method"),
            "delta": round(latest.get("linkage_coverage_pct") - prev.get("linkage_coverage_pct"), 1)
                     if (prev and latest.get("linkage_coverage_pct") is not None and prev.get("linkage_coverage_pct") is not None) else None,
            "website_portfolio": latest.get("website_portfolio"),
            "linked": latest.get("linked"),
            "company_low": latest.get("company_coverage_low_pct"),
            "company_high": latest.get("company_coverage_high_pct"),
            "new_profiles_total": sum((m.get("new_profiles_created") or 0) for m in ms),
        }
    # pooled linkage over time: at each date, pool each accelerator's latest-as-of-that-date
    pooled_trend = []
    for d in sorted({m["measured_at"] for m in history}):
        latest_as_of = {}
        for u, ms in byu.items():
            elig = [m for m in ms if m["measured_at"] <= d]
            if elig:
                latest_as_of[u] = sorted(elig, key=lambda x: x["measured_at"])[-1]
        tw = sum((m.get("website_portfolio") or 0) for m in latest_as_of.values())
        tl = sum((m.get("linked") or 0) for m in latest_as_of.values())
        tp = sum((m.get("dealroom_portfolio") or 0) for m in latest_as_of.values())
        pooled_trend.append({"date": d, "linkage_pct": round(tl / tw * 100, 1) if tw else 0,
                             "portfolio_total": tp, "measured_n": len(latest_as_of)})
    return coverage, pooled_trend


def region_payload(region):
    key, name = region["key"], region["name"]
    targeting = load(f"{key}_targeting.json", []) or []
    for t in targeting:
        t["_region"] = name
        t["_region_key"] = key
    history = load_jsonl(f"{key}_coverage_history.jsonl")
    tracking = load(f"{key}_accelerator_tracking.json", {}) or {}
    proof = load(f"{key}_proof_summary.json", {}) or {}
    coverage, pooled = build_coverage(history)
    return {"name": name, "targeting": targeting, "proof": proof,
            "coverage": coverage, "pooled_trend": pooled, "tracking": tracking}, history


regions = load("regions.json", []) or []

views = {}
all_targeting, all_history, all_tracking = [], [], {}
for r in regions:
    payload, history = region_payload(r)
    views[r["key"]] = payload
    all_targeting += payload["targeting"]
    all_history += history
    all_tracking.update(payload["tracking"])

# pooled "All locations" view
cov_all, pooled_all = build_coverage(all_history)
views["__all__"] = {"name": "All locations", "targeting": all_targeting, "proof": {},
                    "coverage": cov_all, "pooled_trend": pooled_all, "tracking": all_tracking}

payload = {
    "generated": datetime.date.today().isoformat(),
    "regions": [{"key": r["key"], "name": r["name"]} for r in regions],
    "default_view": "__all__",
    "views": views,
}

HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Accelerator Coverage</title>
<style>
  :root{
    --bg:#f7f8fa; --surface:#ffffff; --surface-2:#f0f2f5; --border:#e3e6ea;
    --ink:#11161c; --ink-2:#5a6470; --muted:#8a94a0;
    --target:#1f8f6b; --maintain:#2f6fdb; --park:#c98a1a; --drop:#9aa4b0;
    --danger:#c0453b; --ok:#1f8f6b; --shadow:0 1px 2px rgba(16,22,28,.06),0 2px 8px rgba(16,22,28,.05);
  }
  @media (prefers-color-scheme:dark){
    :root{ --bg:#0e1217; --surface:#161c24; --surface-2:#1d2530; --border:#28313d;
      --ink:#e7ecf2; --ink-2:#a3adba; --muted:#6b7684;
      --target:#37b98c; --maintain:#5a93f0; --park:#e0a63a; --drop:#5c6672; --danger:#e06a5f; --ok:#37b98c; }
  }
  :root[data-theme="dark"]{ --bg:#0e1217; --surface:#161c24; --surface-2:#1d2530; --border:#28313d;
    --ink:#e7ecf2; --ink-2:#a3adba; --muted:#6b7684;
    --target:#37b98c; --maintain:#5a93f0; --park:#e0a63a; --drop:#5c6672; --danger:#e06a5f; --ok:#37b98c; }
  :root[data-theme="light"]{ --bg:#f7f8fa; --surface:#ffffff; --surface-2:#f0f2f5; --border:#e3e6ea;
    --ink:#11161c; --ink-2:#5a6470; --muted:#8a94a0;
    --target:#1f8f6b; --maintain:#2f6fdb; --park:#c98a1a; --drop:#9aa4b0; --danger:#c0453b; --ok:#1f8f6b; }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
  .wrap{max-width:1120px;margin:0 auto;padding:28px 20px 80px}
  header.top{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:22px}
  h1{font-size:22px;margin:0 0 4px;letter-spacing:-.01em}
  .sub{color:var(--ink-2);font-size:13px;max-width:640px}
  .gen{color:var(--muted);font-size:12px;text-align:right}
  .headright{display:flex;flex-direction:column;align-items:flex-end;gap:8px}
  /* location dropdown */
  .locpick{display:flex;align-items:center;gap:8px}
  .locpick label{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:600}
  select#regionSel{appearance:none;-webkit-appearance:none;background:var(--surface);color:var(--ink);
    border:1px solid var(--border);border-radius:9px;padding:9px 34px 9px 13px;font-size:14px;font-weight:600;
    letter-spacing:-.01em;cursor:pointer;box-shadow:var(--shadow);min-width:180px;
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'><path d='M2 4l4 4 4-4' stroke='%238a94a0' stroke-width='1.6' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>");
    background-repeat:no-repeat;background-position:right 12px center}
  select#regionSel:hover{border-color:var(--muted)}
  section{margin-top:30px}
  h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-2);margin:0 0 12px;font-weight:600}
  h2 .scope{color:var(--muted);font-weight:600;text-transform:none;letter-spacing:0}
  h2.collapsible{cursor:pointer;user-select:none}
  .sec-toggle{display:inline-block;width:12px;color:var(--muted)}
  h2.collapsible:hover .sec-toggle{color:var(--ink)}
  /* tiles */
  .tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
  .tile{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow)}
  .tile .n{font-size:26px;font-weight:680;letter-spacing:-.02em;line-height:1.1}
  .tile .l{color:var(--ink-2);font-size:12px;margin-top:3px}
  .tile .d{color:var(--muted);font-size:11px;margin-top:6px}
  .tile.accent .n{color:var(--target)}
  /* funnel bar */
  .funnel{display:flex;height:34px;border-radius:9px;overflow:hidden;border:1px solid var(--border);box-shadow:var(--shadow)}
  .funnel span{display:flex;align-items:center;justify-content:center;color:#fff;font-size:12px;font-weight:600;min-width:34px}
  .legend{display:flex;gap:16px;flex-wrap:wrap;margin-top:10px;color:var(--ink-2);font-size:12px}
  .legend .dot{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:middle}
  /* controls */
  .controls{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px}
  .controls input{flex:1;min-width:180px;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:8px 11px;color:var(--ink);font-size:13px}
  .chip{border:1px solid var(--border);background:var(--surface);color:var(--ink-2);border-radius:20px;padding:6px 12px;font-size:12px;cursor:pointer;user-select:none}
  .chip.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
  /* table */
  .card{background:var(--surface);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow);overflow:hidden}
  .scroll{overflow-x:auto}
  table{border-collapse:collapse;width:100%;font-size:13px}
  th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);white-space:nowrap}
  th{color:var(--ink-2);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.04em;cursor:pointer;position:sticky;top:0;background:var(--surface)}
  td.name{white-space:normal;font-weight:600;min-width:150px}
  tr:last-child td{border-bottom:none}
  tr:hover td{background:var(--surface-2)}
  .num{text-align:right;font-variant-numeric:tabular-nums}
  .badge{display:inline-flex;align-items:center;gap:5px;padding:2px 9px;border-radius:20px;font-size:11px;font-weight:600;border:1px solid transparent}
  .b-target{color:#fff;background:var(--target)}
  .b-maintain{color:#fff;background:var(--maintain)}
  .b-park{color:#fff;background:var(--park)}
  .b-drop{color:var(--ink-2);background:var(--surface-2);border-color:var(--border)}
  .b-live{color:var(--ok);border-color:var(--ok);background:transparent}
  .b-bad{color:var(--danger);border-color:var(--danger);background:transparent}
  .region-tag{color:var(--ink-2);font-size:12px;white-space:nowrap}
  .cohort-mark{color:var(--maintain);font-size:12px;cursor:help}
  .conf{font-size:11px;color:var(--muted)}
  .ev{color:var(--ink-2);white-space:normal;min-width:420px;max-width:620px;font-size:12px}
  .ev a{color:var(--maintain);text-decoration:none}
  .ev a:hover{text-decoration:underline}
  .muted{color:var(--muted)}
  .barwrap{background:var(--surface-2);border-radius:6px;height:8px;overflow:hidden;margin-top:6px}
  .barwrap>i{display:block;height:100%;background:var(--maintain);border-radius:6px}
  .foot{color:var(--muted);font-size:12px;margin-top:8px}
  .paneldef{color:var(--ink-2);font-size:13px;margin:0 0 12px;max-width:860px}
  td.name a{color:var(--ink);text-decoration:none;border-bottom:1px dotted var(--muted)}
  td.name a:hover{color:var(--maintain);border-color:var(--maintain)}
  .defbar{color:var(--ink-2);font-size:12px;margin:2px 0 12px}
  .defbar b{color:var(--ink)}
  .caret{cursor:pointer;color:var(--muted);user-select:none;margin-right:5px;display:inline-block;width:9px;font-size:11px}
  .caret:hover{color:var(--ink)}
  tr.detrow > td{background:var(--surface-2);padding:0;white-space:normal}
  .detwrap{padding:14px 16px 16px}
  .detwrap .dettitle{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--ink-2);margin:0 0 8px;font-weight:600}
  .detchart{margin:0 0 14px}
  table.hist{width:auto;border-collapse:collapse;font-size:12px}
  table.hist th,table.hist td{padding:5px 12px;border-bottom:1px solid var(--border);white-space:nowrap;text-align:left}
  table.hist th{font-size:10px;text-transform:uppercase;letter-spacing:.04em;color:var(--ink-2);font-weight:600}
  table.hist tr:hover td{background:transparent}
  .hnote{white-space:normal;max-width:380px;color:var(--ink-2)}
  .empty{color:var(--muted);font-size:13px;padding:18px 4px}
  /* collapsible section bodies */
  .sec-body{margin-top:2px}
  /* re-check calendar */
  .tile.warn .n{color:var(--danger)}
  .monthstrip{display:flex;gap:9px;overflow-x:auto;padding:4px 2px 14px;margin-top:16px}
  .mcell{flex:0 0 auto;min-width:70px;background:var(--surface);border:1px solid var(--border);border-radius:11px;
    overflow:hidden;cursor:pointer;box-shadow:var(--shadow);text-align:center;display:flex;flex-direction:column;padding:0}
  .mcell:hover{border-color:var(--muted)}
  .mcell .mc-top{background:var(--surface-2);color:var(--ink-2);font-size:10px;font-weight:700;letter-spacing:.06em;
    text-transform:uppercase;padding:5px 12px;border-bottom:1px solid var(--border)}
  .mcell .mc-n{font-size:23px;font-weight:680;letter-spacing:-.02em;line-height:1.1;padding:9px 12px 0}
  .mcell .mc-sub{font-size:10px;color:var(--muted);padding:1px 12px 9px}
  .mcell.mc-over{border-color:var(--danger)}
  .mcell.mc-over .mc-top{background:var(--danger);color:#fff;border-bottom-color:var(--danger)}
  .mcell.mc-over .mc-n{color:var(--danger)}
  /* "future cohort checks" collapsible group in the agenda */
  .ag-more-btn{width:100%;text-align:left;background:var(--surface-2);border:1px solid var(--border);border-radius:10px;
    padding:11px 14px;color:var(--ink);font-size:13px;font-weight:600;cursor:pointer;display:flex;align-items:center;gap:9px}
  .ag-more-btn:hover{border-color:var(--muted)}
  .ag-more-btn .sec-toggle{width:11px;color:var(--muted)}
  .ag-more-btn .mc-count{color:var(--muted);font-weight:500}
  .ag-more-body{display:flex;flex-direction:column;gap:20px;margin-top:18px}
  .agenda{margin-top:6px;display:flex;flex-direction:column;gap:20px}
  .ag-h{font-size:12px;font-weight:700;letter-spacing:-.01em;color:var(--ink);margin:0 0 6px;padding-bottom:7px;border-bottom:1px solid var(--border)}
  .ag-over .ag-h{color:var(--danger)}
  .ag-item{display:flex;align-items:center;gap:13px;padding:8px 4px;border-bottom:1px solid var(--border)}
  .ag-item:last-child{border-bottom:none}
  .ag-date{flex:0 0 28px;text-align:center;font-variant-numeric:tabular-nums;font-weight:680;font-size:16px;color:var(--ink-2)}
  .ag-body{flex:1;min-width:0}
  .ag-name{font-weight:600}
  .ag-name a{color:var(--ink);text-decoration:none;border-bottom:1px dotted var(--muted)}
  .ag-name a:hover{color:var(--maintain);border-color:var(--maintain)}
  .ag-name .region-tag{margin-left:8px;font-weight:400}
  .ag-meta{color:var(--muted);font-size:12px;margin-top:2px;white-space:normal}
  .ag-rel{flex:0 0 auto;color:var(--ink-2);font-size:11px;font-weight:600;white-space:nowrap}
  .ag-over .ag-rel{color:var(--danger)}
  /* per-accelerator detail grid */
  td.ccell{width:26px;padding-right:0}
  .detgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:11px 24px}
  .detgrid .k{font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:600}
  .detgrid .v{font-size:13px;margin-top:1px}
  .detgrid .v a{color:var(--maintain);text-decoration:none}
  .detfull{margin-top:13px}
  .detfull .k{font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:600;margin-bottom:2px}
  .detfull .v{font-size:13px}
  .detfull .v a{color:var(--maintain);text-decoration:none}
  /* region column only shown in the pooled "All locations" view */
  .all-only{display:none}
  body.view-all .all-only{display:table-cell}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div>
      <h1>Accelerator Coverage</h1>
      <div class="sub">Targeting <b>active, under-covered</b> accelerators to discover early-stage companies.</div>
    </div>
    <div class="headright">
      <div class="locpick">
        <label for="regionSel">Location</label>
        <select id="regionSel"></select>
      </div>
      <div class="gen">Generated <span id="gen"></span></div>
    </div>
  </header>

  <section id="trend-sec">
    <h2>Dealroom portfolio growth <span class="scope" id="scope2"></span></h2>
    <div class="card" style="padding:16px">
      <div style="display:flex;gap:26px;align-items:center;flex-wrap:wrap">
        <div><div id="trendPooled" style="font-size:28px;font-weight:680;letter-spacing:-.02em"></div>
          <div style="color:var(--ink-2);font-size:12px">portfolio additions · <span id="trendN"></span> measured · <span id="trendCov"></span> pooled linkage</div></div>
        <div style="border-left:1px solid var(--border);padding-left:26px"><div id="trendCreated" style="font-size:28px;font-weight:680;letter-spacing:-.02em;color:var(--target)"></div>
          <div style="color:var(--ink-2);font-size:12px">new profiles created</div></div>
        <div class="foot" id="trendNote" style="margin:0;max-width:340px"></div>
      </div>
    </div>
  </section>

  <section id="cal-sec">
    <h2>Re-check calendar <span class="scope" id="scopeCal"></span></h2>
    <div class="defbar">When each accelerator's portfolio is next due for a re-check. Cadence follows activity — <b>⟳</b> cohort-aligned, <b>✎</b> manually set. Click a month to jump.</div>
    <div class="tiles" id="calTiles"></div>
    <div class="monthstrip" id="monthStrip"></div>
    <div class="agenda" id="agenda"></div>
  </section>

  <section id="kpis">
    <h2 class="collapsible" data-body="funnelBody" onclick="toggleSection(this)"><span class="sec-toggle">▸</span> Funnel — candidates to worklist <span class="scope" id="scope1"></span></h2>
    <div class="sec-body" id="funnelBody" style="display:none">
      <div class="tiles" id="tiles"></div>
      <div style="margin-top:16px"></div>
      <div class="funnel" id="funnel"></div>
      <div class="legend" id="legend"></div>
    </div>
  </section>

  <section id="proof-sec">
    <h2 class="collapsible" data-body="proofBody" onclick="toggleSection(this)"><span class="sec-toggle">▸</span> Portfolio coverage — measured accelerators <span class="scope" id="scope3"></span></h2>
    <div class="sec-body" id="proofBody" style="display:none">
    <p class="paneldef" id="proofdef"></p>
    <div class="card"><div class="scroll"><table id="proofTbl">
      <thead><tr>
        <th>Measured accelerator</th>
        <th class="all-only">Location</th>
        <th class="num">Web portfolio</th>
        <th class="num">Linked</th>
        <th class="num" title="Profiles newly created in Dealroom (cumulative), not just linked">New profiles</th>
        <th class="num" title="Linked ÷ website portfolio (blank when the official portfolio is unknown)">Linkage %</th>
        <th class="num">Company coverage</th>
        <th class="num" title="Total Dealroom portfolio size (production) at last check, with change since previous">DR portfolio</th>
        <th>Last checked</th>
      </tr></thead><tbody id="proofRows"></tbody>
    </table></div></div>
    <div class="foot" id="prooffoot"></div>
    </div>
  </section>

  <section>
    <h2>Accelerators <span class="scope" id="scope4"></span></h2>
    <div class="controls">
      <input id="q" placeholder="Search name, city, evidence…">
      <span class="chip on" data-f="all">All</span>
      <span class="chip" data-f="ACTIVE">✓ Active (target + maintain)</span>
      <span class="chip" data-f="TARGET">🎯 Target</span>
      <span class="chip" data-f="MAINTAIN">Maintain</span>
      <span class="chip" data-f="PARK">Park</span>
      <span class="chip" data-f="DROP">Drop</span>
      <span class="chip" data-f="STALE">⚠ Stale site</span>
    </div>
    <div class="defbar">🎯 <b>Target</b> = active &amp; under-covered · <b>⟳</b> next check = cohort-aligned · click any row to expand its full detail (city, activity, DR portfolio, throughput, evidence). Names link to Dealroom.</div>
    <div class="card"><div class="scroll"><table id="tbl">
      <thead><tr>
        <th></th>
        <th data-k="name">Accelerator</th>
        <th data-k="_region" class="all-only">Location</th>
        <th data-k="_tier">Tier</th>
        <th data-k="_cov" class="num" title="Latest measured linkage coverage (— if not yet measured)">Coverage</th>
        <th data-k="_due" title="Next scheduled portfolio re-check (cadence set by activity)">Next check</th>
        <th data-k="_site">Website</th>
      </tr></thead>
      <tbody id="rows"></tbody>
    </table></div></div>
    <div class="foot" id="count"></div>
  </section>
</div>

<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
const DATA = JSON.parse(document.getElementById('payload').textContent);
document.getElementById('gen').textContent = DATA.generated;

// ---- view state (reassigned by setView) ----
let VIEW, rows, COV, TRK, PT, VIEWKEY;
const tierKey = r => (r.priority_tier||'').split(':')[0];
const N = f => rows.filter(f).length;

// ---- date helpers (calendar) ----
const TODAY = DATA.generated;
const MON  = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const MONF = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const daysBetween = (a,b) => Math.round((new Date(b+'T00:00:00') - new Date(a+'T00:00:00'))/864e5);

// ---- helpers (read the current view via module-level COV/TRK) ----
function deltaChip(d){ if(d==null) return '<span class="muted">—</span>';
  if(d===0) return '<span class="muted">•0</span>';
  const c=d>0?'var(--ok)':'var(--danger)';
  return `<span style="color:${c};font-weight:600">${d>0?'▲':'▼'}${Math.abs(d)}pp</span>`; }
function dueCell(uuid){ const t=TRK[uuid];
  if(!t||!t.recommended_cadence_days) return '<span class="muted">—</span>';
  const overdue = t.next_due && t.next_due<=DATA.generated;
  const cohort = t.schedule_mode==='cohort';
  const title = (t.schedule_mode==='cadence') ? `every ${t.recommended_cadence_days}d — ${(t.cadence_basis||'')}` : (t.cadence_basis||'');
  const mark = cohort ? ` <span class="cohort-mark" title="${t.cadence_basis||''}">⟳</span>` : '';
  return `<span class="${overdue?'badge b-park':''}" title="${title}">${overdue?'due now':t.next_due}</span>${mark}`; }
function covCell(uuid){ const c=COV[uuid];
  if(!c) return '<span class="muted">–</span>';
  if(c.latest_linkage==null) return '<span class="muted">—</span>';
  return `${c.latest_linkage}% ${deltaChip(c.delta)}`; }
function histTable(recs){
  const rowsH=recs.slice().reverse().map(r=>`<tr>`+
    `<td>${r.date}</td><td class="num">${r.dealroom_portfolio==null?'—':r.dealroom_portfolio}</td>`+
    `<td class="num">${r.linkage==null?'—':r.linkage+'%'}</td><td class="num">${r.delta==null?'—':deltaChip(r.delta)}</td>`+
    `<td class="num">${r.website==null?'—':r.website}</td><td class="num">${r.linked==null?'—':r.linked}</td>`+
    `<td class="num">${r.new_profiles||0}</td><td class="muted">${r.method||''}</td><td class="hnote">${r.note||''}</td></tr>`).join('');
  return `<table class="hist"><thead><tr><th>Date</th><th class="num">DR pf</th><th class="num">Linkage</th><th class="num">Δ</th><th class="num">Web pf</th><th class="num">Linked</th><th class="num">New</th><th>Method</th><th>Note</th></tr></thead><tbody>${rowsH}</tbody></table>`;
}
window.toggleDet=function(u){var el=document.getElementById('det-'+u);if(!el)return;var open=el.style.display!=='none';el.style.display=open?'none':'table-row';var c=document.getElementById('car-'+u);if(c)c.textContent=open?'▸':'▾';};
window.toggleAccDet=function(u){var el=document.getElementById('acc-det-'+u);if(!el)return;var open=el.style.display!=='none';el.style.display=open?'none':'table-row';var c=document.getElementById('acc-car-'+u);if(c)c.textContent=open?'▸':'▾';};
window.toggleSection=function(h2){var b=document.getElementById(h2.dataset.body);if(!b)return;var c=h2.querySelector('.sec-toggle');var open=b.style.display!=='none';b.style.display=open?'none':'';if(c)c.textContent=open?'▸':'▾';};
window.toggleFuture=function(btn){var b=btn.parentNode.querySelector('.ag-more-body');if(!b)return;var c=btn.querySelector('.sec-toggle');var open=b.style.display!=='none';b.style.display=open?'none':'';if(c)c.textContent=open?'▸':'▾';};
window.scrollToMonth=function(mk){var el=document.getElementById('agm-'+mk);if(!el)return;var body=el.closest('.ag-more-body');if(body&&body.style.display==='none'){var btn=body.parentNode.querySelector('.ag-more-btn');if(btn)btn.click();}el.scrollIntoView({behavior:'smooth',block:'start'});};
function sparkVals(vals,w=70,h=18,maxv){
  vals=vals.filter(v=>v!=null); if(!vals.length) return '';
  const mx=maxv||Math.max(...vals,1), y=v=>h-2-(h-4)*Math.max(0,v)/mx;
  if(vals.length===1) return `<svg width="${w}" height="${h}" style="vertical-align:middle"><circle cx="5" cy="${y(vals[0])}" r="2.6" fill="var(--maintain)"/></svg>`;
  const step=(w-8)/(vals.length-1), pts=vals.map((v,i)=>`${4+i*step},${y(v)}`).join(' ');
  return `<svg width="${w}" height="${h}" style="vertical-align:middle"><polyline points="${pts}" fill="none" stroke="var(--maintain)" stroke-width="1.6"/><circle cx="${4+(vals.length-1)*step}" cy="${y(vals[vals.length-1])}" r="2.4" fill="var(--maintain)"/></svg>`;
}
function pfDelta(d){ if(d==null||d===0) return ''; const c=d>0?'var(--ok)':'var(--danger)';
  return ` <span style="color:${c};font-weight:600;font-size:11px">${d>0?'▲':'▼'}${Math.abs(d)}</span>`; }
function portfolioChart(recs){
  const rs=recs.filter(r=>r.dealroom_portfolio!=null);
  if(!rs.length) return '<div class="muted" style="font-size:12px">No Dealroom portfolio counts recorded yet.</div>';
  const W=560,H=190,pl=40,pr=14,pt=12,pb=28, iw=W-pl-pr, ih=H-pt-pb;
  const T=d=>new Date(d+'T00:00:00').getTime();
  const times=rs.map(r=>T(r.date)), tmin=Math.min(...times), tmax=Math.max(...times);
  const maxc=Math.max(...rs.map(r=>r.dealroom_portfolio),1), top=Math.max(Math.ceil(maxc/5)*5,5);
  const xf=t=>(rs.length<2||tmax===tmin)?pl+iw/2:pl+(t-tmin)/(tmax-tmin)*iw;
  const yf=v=>pt+(top-Math.max(0,v))/top*ih;
  let g=''; [0,Math.round(top/2),top].forEach(v=>{const y=yf(v);g+=`<line x1="${pl}" y1="${y}" x2="${W-pr}" y2="${y}" stroke="var(--border)"/><text x="${pl-6}" y="${y+3}" text-anchor="end" font-size="10" fill="var(--muted)">${v}</text>`;});
  const pts=rs.map(r=>[xf(T(r.date)),yf(r.dealroom_portfolio),r]);
  const line=rs.length<2?'':`<polyline points="${pts.map(p=>p[0]+','+p[1]).join(' ')}" fill="none" stroke="var(--maintain)" stroke-width="2"/>`;
  const dots=pts.map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="3.6" fill="var(--maintain)"><title>${p[2].date}: ${p[2].dealroom_portfolio} companies${p[2].note?' — '+String(p[2].note).replace(/"/g,"'"):''}</title></circle>`).join('');
  const xlab=`<text x="${xf(tmin)}" y="${H-9}" font-size="10" fill="var(--muted)">${rs[0].date}</text>`+(rs.length>1?`<text x="${xf(tmax)}" y="${H-9}" font-size="10" fill="var(--muted)" text-anchor="end">${rs[rs.length-1].date}</text>`:'');
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px;height:auto">${g}${line}${dots}${xlab}<text x="${pl-6}" y="${pt-1}" text-anchor="end" font-size="10" fill="var(--muted)"># cos</text></svg>`;
}

// ---- re-check calendar ----
function agItem(x){
  const nm = x.url ? `<a href="${x.url}" target="_blank" rel="noopener">${x.name}</a>` : x.name;
  const reg = x.region ? `<span class="region-tag">${x.region}</span>` : '';
  const icon = x.mode==='cohort' ? '⟳ ' : (x.mode==='override' ? '✎ ' : '');
  const meta = (icon + (x.basis || (x.cadence ? `every ${x.cadence} days` : 'scheduled'))) +
               (x.last ? ` · last checked ${x.last}` : '');
  const rel = x.d < 0 ? `${-x.d}d ago` : (x.d===0 ? 'due today' : (x.d<=30 ? `in ${x.d}d` : ''));
  return `<div class="ag-item"><div class="ag-date">${x.due.slice(8,10)}</div>`+
    `<div class="ag-body"><div class="ag-name">${nm}${reg}</div><div class="ag-meta">${meta}</div></div>`+
    (rel ? `<div class="ag-rel">${rel}</div>` : '') + `</div>`;
}
function renderCalendar(){
  const items = rows.map(r=>{ const t=TRK[r.uuid];
    if(!t || !t.next_due) return null;
    return {uuid:r.uuid, name:r.name, url:r.dealroom_url, region:r._region, due:t.next_due,
            d:daysBetween(TODAY, t.next_due), mode:t.schedule_mode, basis:t.cadence_basis||'',
            cadence:t.recommended_cadence_days, last:t.last_checked};
  }).filter(Boolean).sort((a,b)=>a.due.localeCompare(b.due));

  const overdue  = items.filter(x=>x.d<=0);
  const upcoming = items.filter(x=>x.d>0);
  const in30 = upcoming.filter(x=>x.d<=30).length;
  const in90 = upcoming.filter(x=>x.d<=90).length;
  const unsched = rows.filter(r=>{ const k=tierKey(r);
    if(k!=='TARGET' && k!=='MAINTAIN') return false;
    const t=TRK[r.uuid]; return !t || !t.next_due; }).length;

  const tiles=[
    {n:overdue.length, l:'Overdue / due now', d:'past their re-check date', warn:overdue.length>0},
    {n:in30, l:'Next 30 days', d:'coming up'},
    {n:in90, l:'Next 90 days', d:'on the horizon'},
    {n:items.length, l:'Scheduled', d:'have a re-check date', accent:true},
    {n:unsched, l:'Active, no date', d:'target/maintain, unscheduled'},
  ];
  document.getElementById('calTiles').innerHTML = tiles.map(t=>
    `<div class="tile ${t.accent?'accent':''} ${t.warn?'warn':''}"><div class="n">${t.n}</div><div class="l">${t.l}</div><div class="d">${t.d}</div></div>`).join('');

  // month strip — one cell per upcoming month, plus an overdue cell
  const byMonth={};
  upcoming.forEach(x=>{ (byMonth[x.due.slice(0,7)] = byMonth[x.due.slice(0,7)]||[]).push(x); });
  const months=Object.keys(byMonth).sort();
  const mcell = (cls,top,n,sub,tgt)=>
    `<button class="mcell ${cls}" onclick="scrollToMonth('${tgt}')"><span class="mc-top">${top}</span><span class="mc-n">${n}</span><span class="mc-sub">${sub}</span></button>`;
  const overCell = overdue.length ? mcell('mc-over','Overdue',overdue.length,'due','overdue') : '';
  const strip = overCell + months.map(mk=>{ const [y,m]=mk.split('-');
    return mcell('', `${MON[+m-1]} '${y.slice(2)}`, byMonth[mk].length, 'due', mk);
  }).join('');
  document.getElementById('monthStrip').innerHTML = (overdue.length||months.length)
    ? strip : '<div class="empty">Nothing scheduled in this view.</div>';

  // agenda — overdue + next two months stay open; the rest fold into "Future cohort checks"
  const monthGroup = mk => { const [y,m]=mk.split('-');
    return `<div class="ag-month" id="agm-${mk}"><div class="ag-h">${MONF[+m-1]} ${y} · ${byMonth[mk].length} due</div>`+
           byMonth[mk].map(agItem).join('') + `</div>`; };
  const near = months.slice(0,2), future = months.slice(2);
  let html='';
  if(overdue.length){
    html += `<div class="ag-month ag-over" id="agm-overdue"><div class="ag-h">Overdue / due now · ${overdue.length}</div>`+
            overdue.map(agItem).join('') + `</div>`;
  }
  html += near.map(monthGroup).join('');
  if(future.length){
    const fN = future.reduce((s,mk)=>s+byMonth[mk].length,0);
    html += `<div class="ag-more"><button class="ag-more-btn" onclick="toggleFuture(this)">`+
            `<span class="sec-toggle">▸</span> Future cohort checks <span class="mc-count">· ${fN} across ${future.length} later months</span></button>`+
            `<div class="ag-more-body" style="display:none">${future.map(monthGroup).join('')}</div></div>`;
  }
  document.getElementById('agenda').innerHTML = html || '<div class="empty">No re-checks scheduled for this location yet.</div>';
}

// ---- section renderers ----
function renderTiles(){
  const tiles = [
    {n:rows.length, l:'Candidates', d:'non-closed accelerators'},
    {n:N(r=>tierKey(r)==='TARGET'), l:'🎯 Targets', d:'active + under-covered', accent:true},
    {n:N(r=>tierKey(r)==='MAINTAIN'), l:'Maintain', d:'active + well-covered'},
    {n:N(r=>tierKey(r)==='PARK'), l:'Park', d:'dormant / unverified'},
    {n:N(r=>tierKey(r)==='DROP'), l:'Drop', d:'not-accelerator / defunct'},
    {n:N(r=>r.website_matches_dealroom===false), l:'⚠ Stale websites', d:'wrong URL on file'},
  ];
  document.getElementById('tiles').innerHTML = tiles.map(t=>
    `<div class="tile ${t.accent?'accent':''}"><div class="n">${t.n}</div><div class="l">${t.l}</div><div class="d">${t.d}</div></div>`).join('');
}
function renderFunnel(){
  const seg=[['TARGET','var(--target)'],['MAINTAIN','var(--maintain)'],['PARK','var(--park)'],['DROP','var(--drop)']];
  document.getElementById('funnel').innerHTML = seg.map(([k,c])=>{
    const n=N(r=>tierKey(r)===k); if(!n) return '';
    return `<span style="background:${c};flex:${n}" title="${k}: ${n}">${n}</span>`;
  }).join('');
  document.getElementById('legend').innerHTML = seg.map(([k,c])=>
    `<span><span class="dot" style="background:${c}"></span>${k[0]+k.slice(1).toLowerCase()}</span>`).join('');
}
function renderTrend(){
  const sec=document.getElementById('trend-sec');
  if(PT.length){
    sec.style.display='';
    const last=PT[PT.length-1];
    const growth=Object.values(COV).reduce((s,c)=>{const rs=(c.records||[]).filter(r=>r.dealroom_portfolio!=null);return rs.length?s+(c.latest_portfolio-rs[0].dealroom_portfolio):s;},0);
    document.getElementById('trendPooled').textContent=(growth>=0?'+':'')+growth;
    document.getElementById('trendN').textContent=last.measured_n;
    document.getElementById('trendCov').textContent=last.linkage_pct+'%';
    document.getElementById('trendCreated').textContent=Object.values(COV).reduce((s,c)=>s+(c.new_profiles_total||0),0);
    document.getElementById('trendNote').innerHTML='Net companies added to Dealroom portfolios since each accelerator’s baseline — jumps as portfolios are worked.';
  } else { sec.style.display='none'; }
}
const meta = {};
function renderProof(){
  const sec=document.getElementById('proof-sec');
  Object.keys(meta).forEach(k=>delete meta[k]);
  rows.forEach(t=>meta[t.uuid]={name:t.name,url:t.dealroom_url,region:t._region});
  const covEntries=Object.entries(COV);
  if(!covEntries.length){ sec.style.display='none'; return; }
  sec.style.display='';
  document.getElementById('proofdef').innerHTML =
    `Each measured accelerator's <b>own-website portfolio</b> compared against its <b>Dealroom portfolio</b>. `+
    `<b>Linkage coverage</b> = share of website companies linked to that accelerator in Dealroom; `+
    `<b>company coverage</b> = share that exist anywhere in Dealroom. Δ and the trend update each re-check.`;
  let sw=0,sl=0,scl=0,sch=0,snp=0,spf=0;
  const rowsH=covEntries.map(([u,c])=>{
    const m=meta[u]||{name:u};
    const nm=m.url?`<a href="${m.url}" target="_blank" rel="noopener">${m.name}</a>`:m.name;
    if(c.website_portfolio!=null){ sw+=c.website_portfolio; sl+=c.linked||0;
      scl+=(c.company_low||0)*c.website_portfolio/100; sch+=(c.company_high||0)*c.website_portfolio/100; }
    snp+=c.new_profiles_total||0; spf+=c.latest_portfolio||0;
    return `<tr><td class="name"><span class="caret" id="car-${u}" onclick="toggleDet('${u}')">▸</span>${nm}</td>`+
      `<td class="all-only region-tag">${m.region||''}</td>`+
      `<td class="num">${c.website_portfolio==null?'—':c.website_portfolio}</td><td class="num">${c.linked==null?'—':c.linked}</td>`+
      `<td class="num">${c.new_profiles_total||0}</td>`+
      `<td class="num">${c.latest_linkage==null?'—':c.latest_linkage+'%'}</td>`+
      `<td class="num">${c.company_low==null?'—':c.company_low+'–'+c.company_high+'%'}</td>`+
      `<td class="num">${c.latest_portfolio==null?'—':c.latest_portfolio}${pfDelta(c.portfolio_delta)}</td>`+
      `<td class="muted">${c.latest_date}</td></tr>`+
      `<tr class="detrow" id="det-${u}" style="display:none"><td colspan="9"><div class="detwrap">`+
        `<div class="dettitle">Dealroom portfolio growth — ${(meta[u]||{}).name||''}</div>`+
        `<div class="detchart">${portfolioChart(c.records)}</div>${histTable(c.records)}</div></td></tr>`;
  }).join('');
  const pl=sw?Math.round(sl/sw*1000)/10:0, plo=sw?Math.round(scl/sw*1000)/10:0, phi=sw?Math.round(sch/sw*1000)/10:0;
  const pooledH=`<tr style="font-weight:700"><td class="name">Pooled (${covEntries.length})</td>`+
    `<td class="all-only"></td>`+
    `<td class="num">${sw}</td><td class="num">${sl}</td><td class="num">${snp}</td><td class="num">${pl}%</td>`+
    `<td class="num">${plo}–${phi}%</td><td class="num">${spf}</td><td></td></tr>`;
  document.getElementById('proofRows').innerHTML=rowsH+pooledH;
  document.getElementById('prooffoot').innerHTML =
    `The gap is mostly <b>missing links, not missing companies</b> — most website companies already exist in Dealroom, just unlinked. `+
    `Method <b>domain</b> = exact website-domain match (high precision); <b>name+country</b> = fuzzy (company coverage shown as a band).`;
}

// ---- accelerators table ----
let filter='all', sortK='_gap', sortDir=-1;
const tierBadge=r=>{const k=tierKey(r);const m={TARGET:'b-target',MAINTAIN:'b-maintain',PARK:'b-park',DROP:'b-drop'};
  return `<span class="badge ${m[k]}">${k[0]+k.slice(1).toLowerCase()}</span>`;};
const siteBadge=r=> r.website_matches_dealroom===false
  ? `<span class="badge b-bad" title="${r.website_status||''}">⚠ ${(r.website_status||'stale').replace(/_/g,' ')}</span>`
  : `<span class="badge b-live">live</span>`;
const gap=r=>{ if(tierKey(r)!=='TARGET')return -1; const t=r.cohort_throughput_estimate; const pf=r.dealroom_portfolio||0;
  return (typeof t==='number')? Math.max(t-pf,0)+t*0.1 : Math.max(30-pf,0); };

function accDetail(x){
  const t=TRK[x.uuid]||{};
  const ev=x.evidence||'';
  const evl=x.evidence_url? ` <a href="${x.evidence_url}" target="_blank" rel="noopener">↗ source${x.evidence_date?' · '+x.evidence_date:''}</a>`:'';
  const pairs=[
    ['City', x.city||'—'],
    ['Activity', x.activity_status||'—'],
    ['Priority tier', x.priority_tier||'—'],
    ['DR portfolio', x.dealroom_portfolio==null?'—':x.dealroom_portfolio],
    ['Startups / yr', x.cohort_throughput_estimate==null?'—':x.cohort_throughput_estimate],
    ['Confidence', x.confidence||'—'],
    ['Next check', t.next_due? (t.next_due+(t.schedule_mode?` · ${t.schedule_mode}`:'')) : '—'],
    ['Cadence basis', t.cadence_basis||'—'],
    ['Last checked', t.last_checked||'—'],
  ];
  const grid=pairs.map(([k,v])=>`<div><div class="k">${k}</div><div class="v">${v}</div></div>`).join('');
  const evi=(ev||evl)? `<div class="detfull"><div class="k">Evidence</div><div class="v">${ev}${evl}</div></div>`:'';
  const notes=t.notes? `<div class="detfull"><div class="k">Scheduling notes</div><div class="v">${t.notes}</div></div>`:'';
  return `<div class="detwrap"><div class="detgrid">${grid}</div>${evi}${notes}</div>`;
}
function render(){
  const tb=document.getElementById('rows'), q=document.getElementById('q');
  const term=q.value.trim().toLowerCase();
  let r=rows.filter(x=>{
    let pass;
    if(filter==='STALE') pass = x.website_matches_dealroom===false;
    else if(filter==='ACTIVE') pass = tierKey(x)==='TARGET'||tierKey(x)==='MAINTAIN';
    else if(filter==='all') pass = true;
    else pass = tierKey(x)===filter;
    if(!pass) return false;
    if(term){ return (x.name+' '+(x.city||'')+' '+(x._region||'')+' '+(x.evidence||'')).toLowerCase().includes(term); }
    return true;
  });
  r.sort((a,b)=>{
    let va,vb;
    if(sortK==='_gap'){va=gap(a);vb=gap(b);}
    else if(sortK==='_tier'){const o={TARGET:0,MAINTAIN:1,PARK:2,DROP:3};va=o[tierKey(a)];vb=o[tierKey(b)];}
    else if(sortK==='_site'){va=a.website_matches_dealroom===false?0:1;vb=b.website_matches_dealroom===false?0:1;}
    else if(sortK==='_cov'){va=(COV[a.uuid]||{}).latest_linkage; vb=(COV[b.uuid]||{}).latest_linkage;}
    else if(sortK==='_due'){va=(TRK[a.uuid]||{}).next_due||'9999-99'; vb=(TRK[b.uuid]||{}).next_due||'9999-99';}
    else {va=a[sortK]; vb=b[sortK];}
    if(va==null)va=-Infinity; if(vb==null)vb=-Infinity;
    if(typeof va==='string')return sortDir*va.localeCompare(vb);
    return sortDir*(va-vb);
  });
  tb.innerHTML = r.map(x=>{
    const nm = x.dealroom_url?`<a href="${x.dealroom_url}" target="_blank" rel="noopener">${x.name}</a>`:x.name;
    return `<tr>
      <td class="ccell"><span class="caret" id="acc-car-${x.uuid}" onclick="toggleAccDet('${x.uuid}')">▸</span></td>
      <td class="name">${nm}</td>
      <td class="all-only region-tag">${x._region||''}</td>
      <td>${tierBadge(x)}</td>
      <td class="num">${covCell(x.uuid)}</td>
      <td>${dueCell(x.uuid)}</td>
      <td>${siteBadge(x)}</td>
    </tr>
    <tr class="detrow" id="acc-det-${x.uuid}" style="display:none"><td colspan="7">${accDetail(x)}</td></tr>`;}).join('');
  document.getElementById('count').textContent = `${r.length} shown · sorted by ${sortK==='_gap'?'opportunity':sortK.replace('_','')} · click a row for full detail`;
}

// ---- view switch ----
function renderAll(){ renderTrend(); renderCalendar(); renderTiles(); renderFunnel(); renderProof(); render(); }
function setView(key){
  VIEWKEY=key; VIEW=DATA.views[key]||DATA.views[DATA.default_view];
  rows=VIEW.targeting; COV=VIEW.coverage||{}; TRK=VIEW.tracking||{}; PT=VIEW.pooled_trend||[];
  document.body.classList.toggle('view-all', key==='__all__');
  const scope = key==='__all__' ? 'across all locations' : VIEW.name;
  document.getElementById('scope1').textContent='· '+scope;
  document.getElementById('scope2').textContent='· '+scope;
  document.getElementById('scope3').textContent='· '+scope;
  document.getElementById('scope4').textContent='· '+scope;
  document.getElementById('scopeCal').textContent='· '+scope;
  renderAll();
}

// ---- wire up dropdown + controls ----
(function init(){
  const sel=document.getElementById('regionSel');
  let opts='';
  if(DATA.regions.length>1) opts+=`<option value="__all__">All locations</option>`;
  opts+=DATA.regions.map(r=>`<option value="${r.key}">${r.name}</option>`).join('');
  sel.innerHTML=opts;
  const initial = (DATA.regions.length>1) ? DATA.default_view : (DATA.regions[0]||{}).key;
  sel.value=initial;
  sel.addEventListener('change',()=>setView(sel.value));

  document.getElementById('q').addEventListener('input',render);
  document.querySelectorAll('.chip').forEach(c=>c.addEventListener('click',()=>{
    document.querySelectorAll('.chip').forEach(x=>x.classList.remove('on'));
    c.classList.add('on'); filter=c.dataset.f;
    sortK=(filter==='all'||filter==='TARGET'||filter==='ACTIVE')?'_gap':'_tier'; sortDir=-1; render();
  }));
  document.querySelectorAll('#tbl th').forEach(th=>th.addEventListener('click',()=>{
    const k=th.dataset.k; if(!k) return;
    if(sortK===k)sortDir*=-1; else{sortK=k;sortDir=(k==='name'||k==='city'||k==='_region'||k==='_due')?1:-1;} render();
  }));
  setView(initial);
})();
</script>
</body>
</html>"""

out = HTML.replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False))
open(os.path.join(BASE, "dashboard.html"), "w").write(out)
n_regions = len(regions)
n_accel = sum(len(v["targeting"]) for k, v in views.items() if k != "__all__")
print(f"Wrote dashboard.html  ({n_regions} regions, {n_accel} accelerators total)")
