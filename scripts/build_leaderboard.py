#!/usr/bin/env python3
"""
Prototype "US Accelerator Coverage" leaderboard (new dashboard direction).
Ranks all US accelerators by CURRENT PORTFOLIO VALUE (the exportable proxy for
VC invested), flags VC-backed ones, and overlays the two headline metrics we
generate by working an accelerator: portfolio-size increase + new profiles.

Reads:  data/us_accelerators_2026-09-16.csv   (the 1,466-row Dealroom export)
        data/us_accelerators_vc_backed.json   (VC-round-filtered slugs)
        data/us_worked_deltas.json            (our worked deltas, by Dealroom slug)
Writes: leaderboard.html   (self-contained)
Run:    python3 scripts/build_leaderboard.py
"""
import csv, json, os, glob, datetime

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data")

# VC-backed flag matched on the canonical Dealroom numeric ID (slug forms vary
# between the /investors and /investors-top exports). Note the two exports use
# slightly different filters, so only the IDs that fall inside the 1,466 master
# get flagged (~433) — the rest of the 884 are outside this universe.
vc_ids = set(json.load(open(os.path.join(DATA, "us_accelerators_vc_backed_ids.json"))))
worked = json.load(open(os.path.join(DATA, "us_worked_deltas.json")))

def num(s):
    s = (s or "").strip().replace(",", "")
    try: return float(s)
    except: return None

rows = []
with open(os.path.join(DATA, "us_accelerators_2026-09-16.csv")) as f:
    rd = csv.reader(f)
    header_seen = False
    for r in rd:
        if not header_seen:
            if "Dealroom URL" in r and "Portfolio size" in r:
                header_seen = True
            continue
        if len(r) < 16 or not r[0].strip():
            continue
        rid = r[0].strip()
        url = r[2].strip()
        slug = url.split("/investors/")[-1].rstrip("/") if "/investors/" in url else None
        w = worked.get(slug)
        rows.append({
            "n": r[4].strip(), "u": url, "city": r[7].strip(), "country": r[6].strip(),
            "sec": [s for s in (r[8] or "").split(";") if s][:2],
            "yr": r[9].strip(), "lr": r[10].strip(),
            "pf": int(num(r[11])) if num(r[11]) is not None else None,
            "val": num(r[15]), "ex": num(r[13]),
            "vc": rid in vc_ids,
            "dpf": w["delta"] if w else None,
            "np": w["new_profiles"] if w else None,
        })

rows.sort(key=lambda x: (x["val"] is None, -(x["val"] or 0)))
for i, x in enumerate(rows):
    x["rank"] = i + 1

n_total = len(rows)
n_vc = sum(1 for x in rows if x["vc"])
matched = [x for x in rows if x["dpf"] is not None]
add_total = sum(x["dpf"] for x in matched)
np_total = sum(x["np"] or 0 for x in matched)

# ---- cohort calendar: re-check schedules from our regional tracking ----
row_by_slug = {}
for x in rows:
    s = x["u"].split("/investors/")[-1].rstrip("/") if x["u"] else None
    if s:
        row_by_slug[s] = x
cal = []
for tf in glob.glob(os.path.join(DATA, "*_accelerator_tracking.json")):
    region = os.path.basename(tf).split("_accelerator")[0]
    accf = os.path.join(DATA, f"{region}_accelerators.json")
    urlmap = {}
    if os.path.exists(accf):
        for a in json.load(open(accf)):
            u = a.get("dealroom_url") or ""
            urlmap[a["uuid"]] = u.split("/investors/")[-1].rstrip("/") if "/investors/" in u else None
    for uuid, t in json.load(open(tf)).items():
        due = t.get("next_due")
        if not due or t.get("schedule_mode") == "none":
            continue
        r = row_by_slug.get(urlmap.get(uuid))
        cal.append({"n": t.get("name"), "u": (r["u"] if r else (t.get("dealroom_url") or None)),
                    "due": due, "mode": t.get("schedule_mode"), "basis": t.get("cadence_basis") or "",
                    "region": region.replace("_", " ").title(),
                    "val": (r["val"] if r else None), "vc": (r["vc"] if r else False),
                    "dpf": (r["dpf"] if r else None)})
cal.sort(key=lambda x: x["due"])

# ---- application-deadline calendar (structure ready; filled in as we go) ----
appf = os.path.join(DATA, "cohort_application_deadlines.json")
app_deadlines = []
if os.path.exists(appf):
    doc = json.load(open(appf))
    for d in doc.get("deadlines", []):
        r = row_by_slug.get((d.get("dealroom_url") or "").split("/investors/")[-1].rstrip("/"))
        app_deadlines.append({"n": d.get("accelerator"), "u": d.get("dealroom_url") or (r["u"] if r else None),
                              "due": d.get("application_close"), "cohort": d.get("cohort_name") or "",
                              "apply": d.get("apply_url") or "", "region": d.get("region") or "",
                              "val": (r["val"] if r else None)})
app_deadlines = [d for d in app_deadlines if d["due"]]
app_deadlines.sort(key=lambda x: x["due"])

payload = {"generated": "2026-09-16", "today": datetime.date.today().isoformat(),
           "n_total": n_total, "n_vc": n_vc, "n_worked": len(matched),
           "add_total": add_total, "np_total": np_total, "n_scheduled": len(cal),
           "rows": rows, "calendar": cal, "app_deadlines": app_deadlines}

HTML = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>US Accelerator Coverage</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#f6f7f9; --surface:#ffffff; --ink:#16192c; --ink-2:#5b6172; --muted:#8b90a0;
    --border:#e7e9ee; --line:#eef0f4; --blue:#2f5bff; --blue-soft:#eef2ff;
    --green:#12a06a; --green-soft:#e7f7f0; --amber:#b7791f; --row-hover:#f8f9fc;
    --danger:#d6455f; --danger-soft:#fdeef1;
    --shadow:0 1px 2px rgba(20,25,45,.05),0 1px 3px rgba(20,25,45,.06);
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:14px/1.45 "Source Sans 3",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
  a{color:inherit;text-decoration:none}
  .top{background:var(--surface);border-bottom:1px solid var(--border);padding:14px 24px;display:flex;align-items:center;gap:14px}
  .brand{font-weight:700;font-size:17px;letter-spacing:-.02em}
  .brand span{color:var(--blue)}
  .top .divider{width:1px;height:20px;background:var(--border)}
  .top h1{font-size:15px;font-weight:600;margin:0;color:var(--ink-2)}
  .top .gen{margin-left:auto;color:var(--muted);font-size:12px}
  .wrap{max-width:1240px;margin:0 auto;padding:22px 24px 80px}
  /* KPI strip */
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:20px}
  .kpi{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow)}
  .kpi .n{font-size:24px;font-weight:700;letter-spacing:-.02em;line-height:1.1}
  .kpi .l{color:var(--ink-2);font-size:12px;margin-top:3px}
  .kpi.hl .n{color:var(--green)}
  .kpi.blue .n{color:var(--blue)}
  /* controls */
  .controls{display:flex;gap:10px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
  .controls input{flex:1;min-width:200px;background:var(--surface);border:1px solid var(--border);border-radius:9px;
    padding:9px 13px;font-size:14px;color:var(--ink);font-family:inherit}
  .seg{display:flex;border:1px solid var(--border);border-radius:9px;overflow:hidden;background:var(--surface)}
  .seg button{border:0;background:transparent;padding:9px 14px;font-size:13px;font-weight:600;color:var(--ink-2);cursor:pointer;font-family:inherit}
  .seg button.on{background:var(--blue);color:#fff}
  .chip{border:1px solid var(--border);background:var(--surface);color:var(--ink-2);border-radius:9px;padding:9px 13px;
    font-size:13px;font-weight:600;cursor:pointer;user-select:none}
  .chip.on{background:var(--ink);color:#fff;border-color:var(--ink)}
  /* table */
  .card{background:var(--surface);border:1px solid var(--border);border-radius:14px;box-shadow:var(--shadow);overflow:hidden}
  .scroll{overflow-x:auto}
  table{border-collapse:collapse;width:100%;font-size:13.5px}
  thead th{position:sticky;top:0;background:var(--surface);text-align:left;color:var(--muted);font-weight:600;
    font-size:11px;text-transform:uppercase;letter-spacing:.05em;padding:12px 14px;border-bottom:1px solid var(--border);
    cursor:pointer;white-space:nowrap;z-index:1}
  thead th.num{text-align:right}
  thead th .ar{opacity:.5;font-size:10px;margin-left:3px}
  tbody td{padding:11px 14px;border-bottom:1px solid var(--line);white-space:nowrap;vertical-align:middle}
  tbody tr:last-child td{border-bottom:0}
  tbody tr:hover td{background:var(--row-hover)}
  td.num{text-align:right;font-variant-numeric:tabular-nums}
  .rank{color:var(--muted);font-variant-numeric:tabular-nums;width:34px}
  .acc{display:flex;align-items:center;gap:11px;min-width:260px;white-space:normal}
  .logo{width:30px;height:30px;border-radius:7px;flex:0 0 30px;display:flex;align-items:center;justify-content:center;
    color:#fff;font-weight:700;font-size:13px}
  .acc .nm{font-weight:600;letter-spacing:-.01em}
  .acc .nm a:hover{color:var(--blue)}
  .acc .hq{color:var(--muted);font-size:12px;margin-top:1px}
  .val{font-weight:700;letter-spacing:-.01em}
  .badge{display:inline-flex;align-items:center;gap:4px;font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px}
  .b-vc{background:var(--blue-soft);color:var(--blue)}
  .b-worked{background:var(--green-soft);color:var(--green)}
  .delta{color:var(--green);font-weight:700}
  .dash{color:var(--muted)}
  .foot{color:var(--muted);font-size:12px;margin-top:12px}
  .tags{display:inline-flex;gap:5px}
  .tag{background:var(--line);color:var(--ink-2);border-radius:6px;padding:1px 7px;font-size:11px}
  /* view tabs */
  .viewtabs{display:inline-flex;gap:4px;background:var(--surface);border:1px solid var(--border);
    border-radius:10px;padding:3px;margin-bottom:16px}
  .viewtabs button{border:0;background:transparent;padding:8px 16px;font-size:13.5px;font-weight:600;
    color:var(--ink-2);cursor:pointer;border-radius:7px;font-family:inherit}
  .viewtabs button.on{background:var(--blue);color:#fff}
  /* cohort calendar */
  .monthstrip{display:flex;gap:9px;overflow-x:auto;padding:2px 2px 14px;margin-bottom:6px}
  .mcell{flex:0 0 auto;min-width:72px;background:var(--surface);border:1px solid var(--border);border-radius:11px;
    overflow:hidden;cursor:pointer;box-shadow:var(--shadow);text-align:center;display:flex;flex-direction:column;padding:0}
  .mcell:hover{border-color:var(--muted)}
  .mcell .mc-top{background:#f2f4f8;color:var(--ink-2);font-size:10px;font-weight:700;letter-spacing:.06em;
    text-transform:uppercase;padding:5px 12px;border-bottom:1px solid var(--border)}
  .mcell .mc-n{font-size:22px;font-weight:700;letter-spacing:-.02em;line-height:1.1;padding:9px 12px 0}
  .mcell .mc-sub{font-size:10px;color:var(--muted);padding:1px 12px 9px}
  .mcell.mc-over{border-color:var(--danger)}
  .mcell.mc-over .mc-top{background:var(--danger);color:#fff;border-bottom-color:var(--danger)}
  .mcell.mc-over .mc-n{color:var(--danger)}
  .agenda{display:flex;flex-direction:column;gap:20px}
  .ag-h{font-size:12px;font-weight:700;color:var(--ink);margin:0 0 6px;padding-bottom:7px;border-bottom:1px solid var(--border)}
  .ag-over .ag-h{color:var(--danger)}
  .ag-item{display:flex;align-items:center;gap:13px;padding:10px 4px;border-bottom:1px solid var(--line)}
  .ag-item:last-child{border-bottom:none}
  .ag-date{flex:0 0 30px;text-align:center;font-variant-numeric:tabular-nums;font-weight:700;font-size:16px;color:var(--ink-2)}
  .ag-body{flex:1;min-width:0}
  .ag-name{font-weight:600}
  .ag-name a:hover{color:var(--blue)}
  .ag-meta{color:var(--muted);font-size:12px;margin-top:1px;white-space:normal}
  .ag-right{flex:0 0 auto;text-align:right;white-space:nowrap}
  .ag-val{font-weight:700;font-size:13px}
  .ag-rel{color:var(--ink-2);font-size:11px;font-weight:600}
  .ag-over .ag-rel{color:var(--danger)}
  .ag-more-btn{width:100%;text-align:left;background:var(--surface);border:1px solid var(--border);border-radius:10px;
    padding:11px 14px;color:var(--ink);font-size:13px;font-weight:600;cursor:pointer;display:flex;align-items:center;gap:9px;font-family:inherit}
  .ag-more-btn:hover{border-color:var(--muted)}
  .ag-more-body{display:flex;flex-direction:column;gap:20px;margin-top:18px}
  .cal-note{color:var(--muted);font-size:12px;margin:2px 0 14px}
</style></head>
<body>
  <div class="top">
    <div class="brand">dealroom<span>.co</span></div>
    <div class="divider"></div>
    <h1>US Accelerator Coverage &mdash; leaderboard</h1>
    <div class="gen">Prototype &middot; generated <span id="gen"></span></div>
  </div>
  <div class="wrap">
    <div class="kpis" id="kpis"></div>
    <div class="viewtabs">
      <button id="vLead" class="on">Leaderboard</button>
      <button id="vCal">Cohort calendar</button>
    </div>
    <div id="lbView">
    <div class="controls">
      <input id="q" placeholder="Search accelerator, city, sector…">
      <span class="chip" id="vcChip">VC-backed only</span>
      <span class="chip" id="wkChip">Worked only</span>
      <div class="seg"><button id="t50" class="on">Top 50</button><button id="tall">All</button></div>
    </div>
    <div class="card"><div class="scroll"><table>
      <thead><tr>
        <th data-k="rank">#</th>
        <th data-k="n">Accelerator</th>
        <th data-k="pf" class="num">Portfolio</th>
        <th data-k="val" class="num">Current value</th>
        <th data-k="ex" class="num">Exits</th>
        <th data-k="lr">Last round</th>
        <th data-k="dpf" class="num" title="Portfolio-size increase since we worked it">&Delta; Portfolio</th>
        <th data-k="np" class="num" title="New Dealroom profiles we created">New profiles</th>
      </tr></thead>
      <tbody id="rows"></tbody>
    </table></div></div>
    <div class="foot" id="count"></div>
    </div>
    <div id="calView" hidden>
      <div class="viewtabs" style="margin-bottom:14px">
        <button id="cRecheck" class="on">Re-check schedule</button>
        <button id="cApps">Application deadlines</button>
      </div>
      <div id="recheckCal">
        <p class="cal-note" id="rcNote"></p>
        <div class="kpis" id="rcTiles" style="margin-bottom:16px"></div>
        <div class="monthstrip" id="rcStrip"></div>
        <div class="agenda" id="rcAgenda"></div>
      </div>
      <div id="appsCal" hidden>
        <p class="cal-note" id="apNote"></p>
        <div class="kpis" id="apTiles" style="margin-bottom:16px"></div>
        <div class="monthstrip" id="apStrip"></div>
        <div class="agenda" id="apAgenda"></div>
      </div>
    </div>
  </div>
<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
const D=JSON.parse(document.getElementById('payload').textContent);
document.getElementById('gen').textContent=D.generated;
const COLORS=['#2f5bff','#12a06a','#b7791f','#8b3fd6','#d6455f','#0e8f9e','#c2701a','#4b62d6'];
const fmtMoney=v=>{ if(v==null) return '<span class=dash>&mdash;</span>';
  if(v>=1000) return '$'+(v/1000).toFixed(1)+'B';
  if(v>=100) return '$'+Math.round(v)+'M';
  if(v>=1) return '$'+v.toFixed(1)+'M';
  if(v>0) return '$'+Math.round(v*1000)+'K'; return '<span class=dash>$0</span>'; };
const fmtInt=v=> v==null?'<span class=dash>&mdash;</span>':v.toLocaleString();
function kpis(){
  const k=[['n_total','Accelerators tracked',''],['n_vc','VC-backed portfolios',''],
    ['n_worked','Checked and backfilled','hl'],['add_total','Portfolio additions','hl'],['np_total','New profiles created','blue']];
  document.getElementById('kpis').innerHTML=k.map(([f,l,c])=>{
    let v=D[f]; if(f==='add_total') v='+'+v;
    return `<div class="kpi ${c}"><div class="n">${typeof v==='number'?v.toLocaleString():v}</div><div class="l">${l}</div></div>`;
  }).join('');
}
let sortK='val', sortDir=-1, top50=true, vcOnly=false, wkOnly=false;
function render(){
  const q=document.getElementById('q').value.trim().toLowerCase();
  let r=D.rows.filter(x=>{
    if(vcOnly&&!x.vc) return false;
    if(wkOnly&&x.dpf==null) return false;
    if(q){return (x.n+' '+x.city+' '+(x.sec||[]).join(' ')).toLowerCase().includes(q);}
    return true;
  });
  r.sort((a,b)=>{let va=a[sortK],vb=b[sortK];
    if(va==null)va=-Infinity; if(vb==null)vb=-Infinity;
    if(typeof va==='string')return sortDir*va.localeCompare(vb);
    return sortDir*(va-vb);});
  const shown = (top50&&!q&&!vcOnly&&!wkOnly) ? r.slice(0,50) : r;
  document.getElementById('rows').innerHTML = shown.map(x=>{
    const ini=(x.n||'?').replace(/[^A-Za-z0-9]/g,'').slice(0,2).toUpperCase()||'?';
    const col=COLORS[(x.rank||0)%COLORS.length];
    const nm=x.u?`<a href="${x.u}" target="_blank" rel="noopener">${x.n}</a>`:x.n;
    const hq=[x.city,x.country&&x.country!=='United States'?x.country:''].filter(Boolean).join(', ')||x.country||'';
    const badges=(x.vc?'<span class="badge b-vc">VC</span> ':'')+(x.dpf!=null?'<span class="badge b-worked">worked</span>':'');
    return `<tr>
      <td class="rank">${x.rank}</td>
      <td><div class="acc"><div class="logo" style="background:${col}">${ini}</div>
        <div><div class="nm">${nm} ${badges}</div><div class="hq">${hq}</div></div></div></td>
      <td class="num">${fmtInt(x.pf)}</td>
      <td class="num"><span class="val">${fmtMoney(x.val)}</span></td>
      <td class="num">${fmtMoney(x.ex)}</td>
      <td>${x.lr||'<span class=dash>&mdash;</span>'}</td>
      <td class="num">${x.dpf!=null?'<span class="delta">+'+x.dpf+'</span>':'<span class=dash>&mdash;</span>'}</td>
      <td class="num">${x.np!=null&&x.np>0?x.np:'<span class=dash>&mdash;</span>'}</td>
    </tr>`;}).join('');
  document.getElementById('count').textContent =
    `${shown.length.toLocaleString()} shown of ${r.length.toLocaleString()} filtered · ${D.n_total.toLocaleString()} total US accelerators · sorted by ${sortK==='val'?'current value':sortK}`;
}
kpis();
document.getElementById('q').addEventListener('input',render);
document.querySelectorAll('thead th').forEach(th=>th.addEventListener('click',()=>{
  const k=th.dataset.k; if(sortK===k)sortDir*=-1; else{sortK=k;sortDir=(k==='n'||k==='lr')?1:-1;} render();}));
document.getElementById('t50').onclick=()=>{top50=true;document.getElementById('t50').classList.add('on');document.getElementById('tall').classList.remove('on');render();};
document.getElementById('tall').onclick=()=>{top50=false;document.getElementById('tall').classList.add('on');document.getElementById('t50').classList.remove('on');render();};
document.getElementById('vcChip').onclick=function(){vcOnly=!vcOnly;this.classList.toggle('on',vcOnly);render();};
document.getElementById('wkChip').onclick=function(){wkOnly=!wkOnly;this.classList.toggle('on',wkOnly);render();};
render();

// ---- cohort calendar view ----
const TODAY=D.today;
const MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const MONF=['January','February','March','April','May','June','July','August','September','October','November','December'];
const daysBetween=(a,b)=>Math.round((new Date(b+'T00:00:00')-new Date(a+'T00:00:00'))/864e5);
window.scrollToMonth=function(id){var el=document.getElementById(id);if(!el)return;var b=el.closest('.ag-more-body');if(b&&b.style.display==='none'){var btn=b.parentNode.querySelector('.ag-more-btn');if(btn)btn.click();}el.scrollIntoView({behavior:'smooth',block:'start'});};
window.toggleFuture=function(btn){var b=btn.parentNode.querySelector('.ag-more-body');if(!b)return;var c=btn.querySelector('.fc');var open=b.style.display!=='none';b.style.display=open?'none':'';if(c)c.textContent=open?'▸':'▾';};
function relTxt(d,kind){
  if(kind==='apps') return d<0?`closed ${-d}d ago`:(d===0?'closes today':(d<=45?`closes in ${d}d`:''));
  return d<0?`${-d}d ago`:(d===0?'due today':(d<=30?`in ${d}d`:''));
}
function agItem(x,kind){
  const nm=x.u?`<a href="${x.u}" target="_blank" rel="noopener">${x.n}</a>`:x.n;
  let meta,right;
  if(kind==='apps'){
    meta=(x.cohort?x.cohort+' &middot; ':'')+(x.region||'');
    right=x.apply?`<a class="ag-val" style="color:var(--blue)" href="${x.apply}" target="_blank" rel="noopener">Apply &#8599;</a>`:'';
  }else{
    const icon=x.mode==='cohort'?'⟳ ':(x.mode==='override'?'✎ ':'');
    meta=icon+(x.basis||'scheduled')+(x.region?' &middot; '+x.region:'');
    right=x.val!=null?`<div class="ag-val">${fmtMoney(x.val)}</div>`:'';
  }
  const rel=relTxt(x.d,kind);
  return `<div class="ag-item"><div class="ag-date">${x.due.slice(8,10)}</div>`+
    `<div class="ag-body"><div class="ag-name">${nm}</div><div class="ag-meta">${meta}</div></div>`+
    `<div class="ag-right">${right}${rel?`<div class="ag-rel">${rel}</div>`:''}</div></div>`;
}
function renderCal(data, ids, kind){
  const items=data.map(x=>({...x,d:daysBetween(TODAY,x.due)})).sort((a,b)=>a.due.localeCompare(b.due));
  const T=document.getElementById(ids.tiles), S=document.getElementById(ids.strip), A=document.getElementById(ids.agenda);
  if(!items.length){ T.innerHTML=''; S.innerHTML='';
    A.innerHTML=`<div class="cal-note" style="padding:26px 2px;font-size:14px">${ids.empty}</div>`; return; }
  const overdue=items.filter(x=>x.d<=0), upcoming=items.filter(x=>x.d>0);
  const tiles = kind==='apps'
    ? [[overdue.length,'Closed / due now',''],[upcoming.filter(x=>x.d<=30).length,'Closing in 30 days',''],[upcoming.filter(x=>x.d<=90).length,'Open next 90 days',''],[items.length,'Application windows','blue']]
    : [[overdue.length,'Overdue / due now',''],[upcoming.filter(x=>x.d<=30).length,'Next 30 days',''],[upcoming.filter(x=>x.d<=90).length,'Next 90 days',''],[items.length,'Scheduled re-checks','blue']];
  T.innerHTML=tiles.map(([n,l,c])=>`<div class="kpi ${c}"><div class="n">${n}</div><div class="l">${l}</div></div>`).join('');
  const byMonth={}; upcoming.forEach(x=>{(byMonth[x.due.slice(0,7)]=byMonth[x.due.slice(0,7)]||[]).push(x);});
  const months=Object.keys(byMonth).sort(), P=ids.prefix;
  const mcell=(cls,top,n,sub,tgt)=>`<button class="mcell ${cls}" onclick="scrollToMonth('${tgt}')"><span class="mc-top">${top}</span><span class="mc-n">${n}</span><span class="mc-sub">${sub}</span></button>`;
  const over=overdue.length?mcell('mc-over',kind==='apps'?'Closed':'Overdue',overdue.length,'due',P+'-agm-overdue'):'';
  S.innerHTML=over+months.map(mk=>{const[y,m]=mk.split('-');return mcell('',`${MON[+m-1]} '${y.slice(2)}`,byMonth[mk].length,'due',P+'-agm-'+mk);}).join('');
  const grp=mk=>{const[y,m]=mk.split('-');return `<div id="${P}-agm-${mk}"><div class="ag-h">${MONF[+m-1]} ${y} &middot; ${byMonth[mk].length} due</div>`+byMonth[mk].map(x=>agItem(x,kind)).join('')+`</div>`;};
  const near=months.slice(0,2), future=months.slice(2);
  let html='';
  const overH=kind==='apps'?'Closed / due now':'Overdue / due now';
  if(overdue.length) html+=`<div class="ag-over" id="${P}-agm-overdue"><div class="ag-h">${overH} &middot; ${overdue.length}</div>`+overdue.map(x=>agItem(x,kind)).join('')+`</div>`;
  html+=near.map(grp).join('');
  if(future.length){const fN=future.reduce((s,mk)=>s+byMonth[mk].length,0);
    html+=`<div><button class="ag-more-btn" onclick="toggleFuture(this)"><span class="fc">▸</span> Later ${kind==='apps'?'windows':'re-checks'} <span style="color:var(--muted);font-weight:500">&middot; ${fN} across ${future.length} later months</span></button><div class="ag-more-body" style="display:none">${future.map(grp).join('')}</div></div>`;}
  A.innerHTML=html;
}
let rcDone=false, apDone=false;
function renderRecheck(){ if(rcDone)return; rcDone=true;
  document.getElementById('rcNote').innerHTML=`Cohort re-check schedule for the ${D.calendar.length} accelerators we're actively tracking &mdash; <b>&#8635;</b> cohort-aligned, <b>&#9998;</b> manually set. New accelerators get a schedule as they're worked.`;
  renderCal(D.calendar,{tiles:'rcTiles',strip:'rcStrip',agenda:'rcAgenda',prefix:'rc',empty:'No re-checks scheduled yet.'},'recheck'); }
function renderApps(){ if(apDone)return; apDone=true;
  document.getElementById('apNote').innerHTML=`Upcoming cohort application deadlines &mdash; the seed of a public destination where founders find open calls. No data captured yet; windows appear here as we enrich accelerators with their application dates.`;
  renderCal(D.app_deadlines,{tiles:'apTiles',strip:'apStrip',agenda:'apAgenda',prefix:'ap',empty:"No application deadlines captured yet. As we enrich accelerators with their open-call dates, upcoming cohort application windows will show up here."},'apps'); }
function showCal(apps){
  document.getElementById('recheckCal').hidden=apps; document.getElementById('appsCal').hidden=!apps;
  document.getElementById('cRecheck').classList.toggle('on',!apps); document.getElementById('cApps').classList.toggle('on',apps);
  if(apps)renderApps(); else renderRecheck();
}
document.getElementById('cRecheck').onclick=()=>showCal(false);
document.getElementById('cApps').onclick=()=>showCal(true);
function showView(cal){
  document.getElementById('lbView').hidden=cal; document.getElementById('calView').hidden=!cal;
  document.getElementById('vLead').classList.toggle('on',!cal); document.getElementById('vCal').classList.toggle('on',cal);
  if(cal)renderRecheck();
}
document.getElementById('vLead').onclick=()=>showView(false);
document.getElementById('vCal').onclick=()=>showView(true);
</script>
</body></html>"""

out = HTML.replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False))
open(os.path.join(BASE, "leaderboard.html"), "w").write(out)
print(f"Wrote leaderboard.html  ({n_total} accelerators, {n_vc} VC-backed, {len(matched)} worked; "
      f"+{add_total} portfolio additions, {np_total} new profiles)")
