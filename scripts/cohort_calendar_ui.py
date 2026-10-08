"""
Front-end for the leaderboard's "Cohort calendar → Application deadlines" view
(marketing cohort calendar, 2026-10-08). Injected into leaderboard.html by
build_leaderboard.py. Reads payload.cohort_calendar (slim columnar projection of
data/cohort_calendar.json). Raw strings so JS regexes/escapes survive as written.

Rules baked in: inferred dates always carry a dashed INFERRED badge and are hidden
by the default confidence filter; month-only dates render as "Mon YYYY (date TBC)";
blanks render as "date not published"; hidden statuses are off by default.
"""

CSS = r"""
  /* ---- application deadlines (cohort calendar) ---- */
  .hot{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;margin:0 0 14px}
  .hotb{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:12px 14px;box-shadow:var(--shadow)}
  .hotb h3{margin:0 0 8px;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-2);font-weight:700}
  .hotb h3 span{color:var(--muted);font-weight:600;margin-left:4px}
  .hotb ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px;font-size:13px}
  .hotb li{display:flex;align-items:baseline;gap:6px;min-width:0}
  .hotb .more{color:var(--muted);font-size:12px}
  .hotb .none{color:var(--muted);font-size:12.5px}
  .hd{flex:0 0 46px;color:var(--muted);font-variant-numeric:tabular-nums;font-weight:600}
  .hn{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .ht{flex:0 0 auto;font-size:10px;font-weight:700;text-transform:uppercase;border-radius:5px;padding:1px 6px;margin-left:auto}
  .ht-closes{background:var(--danger-soft);color:var(--danger)}
  .ht-opens{background:var(--green-soft);color:var(--green)}
  .ht-closed{background:var(--line);color:var(--ink-2)}
  .apf{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:14px}
  .apf input{flex:1 1 220px;min-width:0;background:var(--surface);border:1px solid var(--border);border-radius:9px;
    padding:9px 13px;font-size:14px;color:var(--ink);font-family:inherit}
  .apf select{background:var(--surface);border:1px solid var(--border);border-radius:9px;padding:8px 10px;
    font-size:13px;font-weight:600;color:var(--ink-2);font-family:inherit;max-width:100%}
  .dd{position:relative}
  .dd summary{list-style:none;cursor:pointer;border:1px solid var(--border);background:var(--surface);color:var(--ink-2);
    border-radius:9px;padding:8px 12px;font-size:13px;font-weight:600;user-select:none;white-space:nowrap}
  .dd summary::-webkit-details-marker{display:none}
  .dd summary .ddv{color:var(--ink);margin-left:4px}
  .dd summary.chg{border-color:var(--blue);color:var(--blue)}
  .ddb{position:absolute;z-index:20;top:calc(100% + 4px);left:0;background:var(--surface);border:1px solid var(--border);
    border-radius:10px;box-shadow:0 10px 28px rgba(20,25,45,.14);padding:6px;min-width:260px;max-width:calc(100vw - 32px)}
  .ddb label{display:flex;gap:8px;align-items:center;padding:6px 7px;border-radius:6px;cursor:pointer;font-size:13px}
  .ddb label:hover{background:var(--row-hover)}
  .ddb .cnt{margin-left:auto;color:var(--muted);font-size:12px;font-variant-numeric:tabular-nums}
  .ddq{display:flex;gap:6px;border-top:1px solid var(--line);margin-top:4px;padding:6px 4px 2px}
  .ddq button,.apbtn{border:1px solid var(--border);background:var(--surface);color:var(--ink-2);border-radius:7px;
    padding:4px 9px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit}
  .apbtn{padding:8px 12px;font-size:13px;border-radius:9px;text-decoration:none;display:inline-block}
  .apbtn:hover,.ddq button:hover{border-color:var(--muted)}
  .apx{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap}
  .b-inf{display:inline-block;border:1px dashed var(--muted);color:var(--ink-2);font-size:10px;font-weight:700;
    letter-spacing:.05em;border-radius:5px;padding:0 5px;margin-left:6px;cursor:help;vertical-align:1px}
  .loc{display:inline-block;background:var(--line);color:var(--ink-2);border-radius:20px;padding:1px 8px;font-size:11px;
    font-weight:600;margin-left:6px;white-space:nowrap;vertical-align:1px}
  .stc{display:inline-block;border-radius:20px;padding:1px 8px;font-size:11px;font-weight:600;white-space:nowrap;
    background:var(--line);color:var(--ink-2)}
  .stc.st-active{background:var(--green-soft);color:var(--green)}
  .stc.st-likely,.stc.st-winding{background:#fdf5e6;color:var(--amber)}
  .stc.st-defunct{background:var(--danger-soft);color:var(--danger)}
  .apply{color:var(--blue);font-weight:700;font-size:13px;white-space:nowrap}
  .ag-date .ag-mo{display:block;font-size:9px;text-transform:uppercase;color:var(--muted);letter-spacing:.05em;font-weight:700}
  .kpi.click{cursor:pointer}
  .kpi.sel{border-color:var(--blue);box-shadow:0 0 0 2px var(--blue-soft)}
  .ap-sub{color:var(--muted);font-size:12.5px;margin:-4px 0 12px}
  .mgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px}
  .mg{background:var(--surface);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow);overflow:hidden;min-width:0}
  .mg-h{display:flex;justify-content:space-between;align-items:baseline;gap:8px;padding:9px 14px;border-bottom:1px solid var(--border);
    background:#f2f4f8;font-size:13px}
  .mg-h span{color:var(--muted);font-size:12px}
  .mg ul{list-style:none;margin:0;padding:4px 0}
  .mg li{display:flex;gap:10px;align-items:baseline;padding:5px 14px;font-size:13px}
  .mg-d{flex:0 0 22px;font-weight:700;color:var(--ink-2);font-variant-numeric:tabular-nums;text-align:right}
  .mg-t{flex:1;min-width:0}
  .mg-p{display:block;color:var(--muted);font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .mg-k{flex:0 0 auto;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--danger)}
  .mg li.k-start .mg-k{color:var(--blue)}
  .mg li.k-demo .mg-k{color:var(--amber)}
  .mg li.k-start .mg-t a,.mg li.k-demo .mg-t a{font-weight:500;color:var(--ink-2)}
  .mg-tbc{border-top:1px dashed var(--border);background:#fafbfc}
  .mg-tbch{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);padding:7px 14px 0}
  .mg-empty{color:var(--muted);font-size:12px;padding:12px 14px}
  .aplist td{white-space:normal;vertical-align:top}
  .aplist td .sub{color:var(--muted);font-size:12px;margin-top:1px}
  .aplist .nw{white-space:nowrap}
  .opencard{font-weight:600;cursor:pointer}
  .opencard:hover{color:var(--blue)}
  .ovl{position:fixed;inset:0;background:rgba(20,25,45,.38);z-index:50;display:flex;align-items:flex-start;
    justify-content:center;padding:6vh 16px;overflow:auto}
  .ovl[hidden]{display:none}
  .pop{background:var(--surface);border-radius:14px;max-width:580px;width:100%;box-shadow:0 20px 50px rgba(20,25,45,.25);
    padding:20px 22px 18px;position:relative}
  .pop .x{position:absolute;top:8px;right:10px;border:0;background:transparent;font-size:24px;line-height:1;cursor:pointer;
    color:var(--muted);padding:4px 8px}
  .pop h2{margin:0 30px 2px 0;font-size:18px;letter-spacing:-.01em}
  .pop .sub{color:var(--ink-2);margin-bottom:10px;font-size:13.5px}
  .pop .chips{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px}
  .pop dl{display:grid;grid-template-columns:150px 1fr;gap:7px 14px;margin:0;font-size:13.5px}
  .pop dt{color:var(--muted)}
  .pop dd{margin:0;overflow-wrap:anywhere}
  .pop .src a{display:block;color:var(--blue)}
  .pop .acts{display:flex;gap:10px;margin-top:16px;flex-wrap:wrap}
  .pop .oth{margin-top:16px;border-top:1px solid var(--line);padding-top:10px;font-size:13px}
  .pop .oth div{padding:3px 0}
  .aptoast{position:fixed;left:50%;bottom:20px;transform:translateX(-50%);background:var(--ink);color:#fff;border-radius:9px;
    padding:9px 14px;font-size:13px;z-index:60;max-width:calc(100vw - 32px)}
  @media (max-width:640px){
    .pop dl{grid-template-columns:1fr;gap:2px}
    .pop dt{margin-top:8px}
    .apx{margin-left:0}
    .wrap{padding-left:16px;padding-right:16px}
  }
"""

HTML = r"""
      <div id="appsCal" hidden>
        <p class="cal-note" id="apNote"></p>
        <div class="hot" id="apHot"></div>
        <div class="apf">
          <input id="apQ" type="search" placeholder="Search accelerator, program, location…" aria-label="Search programs">
          <details class="dd" data-key="st"><summary>Status<span class="ddv"></span></summary><div class="ddb"></div></details>
          <details class="dd" data-key="hq"><summary>HQ<span class="ddv"></span></summary><div class="ddb"></div></details>
          <details class="dd" data-key="conf"><summary>Date confidence<span class="ddv"></span></summary><div class="ddb"></div></details>
          <select id="apCad" aria-label="Cadence"></select>
          <select id="apSec" aria-label="Sector" hidden></select>
          <button class="apbtn" id="apReset" type="button">Reset filters</button>
          <span class="apx">
            <button class="apbtn" id="apCsv" type="button">Export CSV</button>
            <a class="apbtn" id="apIcs" href="cohort_deadlines.ics" target="_blank" rel="noopener">Export .ics</a>
          </span>
        </div>
        <div class="viewtabs" id="apTabs" style="margin-bottom:14px">
          <button data-v="up" class="on" type="button">Upcoming deadlines</button>
          <button data-v="grid" type="button">Month grid</button>
          <button data-v="list" type="button">All programs</button>
        </div>
        <div id="apUp">
          <div class="kpis" id="apTiles" style="margin-bottom:12px"></div>
          <p class="ap-sub" id="apUpSub"></p>
          <div class="monthstrip" id="apStrip"></div>
          <div class="agenda" id="apAgenda"></div>
        </div>
        <div id="apGrid" hidden></div>
        <div id="apList" hidden></div>
        <div class="foot" id="apFoot"></div>
      </div>
"""

OVERLAY = r"""
  <div class="ovl" id="apOvl" hidden><div class="pop" role="dialog" aria-modal="true" aria-labelledby="apCardT">
    <button class="x" type="button" aria-label="Close">&times;</button><div id="apCard"></div></div></div>
"""

JS = r"""
// ---- application deadlines: marketing cohort calendar (payload.cohort_calendar) ----
(function(){
const CC=D.cohort_calendar;
const pad=n=>String(n).padStart(2,'0');
const iso=d=>`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
const TD=iso(new Date());                       // live "today" for the viewer
const addDays=(s,n)=>{const d=new Date(s+'T00:00:00');d.setDate(d.getDate()+n);return iso(d);};
const dayDiff=(a,b)=>Math.round((new Date(b+'T00:00:00')-new Date(a+'T00:00:00'))/864e5);
const isDay=s=>/^\d{4}-\d{2}-\d{2}$/.test(s||''), isMon=s=>/^\d{4}-\d{2}$/.test(s||''), isYr=s=>/^\d{4}$/.test(s||'');
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const okUrl=u=>/^https?:\/\//i.test(u||'');
const DRU='https://app.dealroom.co/investors/';
function fmtD(s){
  if(!s) return 'date not published';
  if(isDay(s)){const[y,m,d]=s.split('-');return `${MON[+m-1]} ${+d}, ${y}`;}
  if(isMon(s)){const[y,m]=s.split('-');return `${MON[+m-1]} ${y} (date TBC)`;}
  if(isYr(s)) return `${s} (date TBC)`;
  return s;
}
const fmtS=s=>{const[,m,d]=s.split('-');return `${MON[+m-1]} ${+d}`;};
const ST={active_dated:'Active · dated',active_rolling:'Active · rolling',active_undated:'Active · no dates yet',
  likely_inactive:'Likely inactive',winding_down:'Winding down',defunct:'Defunct',duplicate:'Duplicate',
  not_accelerator_vc:'Not an accelerator (VC)',not_accelerator_studio:'Not an accelerator (studio)',
  not_accelerator_other:'Not an accelerator (other)',unknown:'Unknown'};
const ST_ORDER=Object.keys(ST);
const HQ={Y:'US',N:'Non-US','':'HQ not set'};
const CF={'published':'Published','inferred-from-pattern':'Inferred','unknown':'No dates'};
const WS={open:'Open now',upcoming_start:'Opening soon',upcoming_unpublished:'Next window not published',in_program:'In program',
  closed:'Closed',rolling:'Rolling',no_public_dates:'No public dates',no_public_apps:'No public applications',
  not_cohort_program:'Not a cohort program',inactive:'Inactive'};
// Confidence default = published dates + rows with no dates at all ("unknown" rows carry no date to
// misrepresent); inferred stays off until the viewer opts in.
const DEF={st:['active_dated','active_rolling','active_undated'],hq:['Y'],conf:['published','unknown']};
const F={st:new Set(DEF.st),hq:new Set(DEF.hq),conf:new Set(DEF.conf),cad:'',sec:'',q:''};
let ROWS=[], view='up', win=30, inited=false, DL=null;

window.apInit=function(){
  if(inited) return; inited=true;
  const note=document.getElementById('apNote');
  if(!CC||!CC.rows.length){ note.textContent='No cohort calendar data loaded.'; return; }
  ROWS=CC.rows.map((a,i)=>{const o={i};CC.cols.forEach((k,j)=>o[k]=a[j]);return o;});
  note.innerHTML=`Application windows for ${ROWS.length.toLocaleString()} accelerator programs and cohorts &mdash; the seed of a public destination where founders find open calls. Click any name for its details.`;
  buildFilters(); wire(); renderAll();
  try{ if(window.claude&&claude.use) claude.use('downloads').then(ns=>{DL=ns; setIcsMode();}).catch(()=>{}); }catch(e){}
  setIcsMode();
};

// ---------- filtering ----------
function pass(r,skip){
  if(skip!=='st'&&!F.st.has(r.st)) return false;
  if(skip!=='hq'&&!F.hq.has(r.hq)) return false;
  if(skip!=='conf'&&!F.conf.has(r.conf)) return false;
  if(F.cad&&r.cad!==F.cad) return false;
  if(F.sec&&!(r.sec||'').split(';').includes(F.sec)) return false;
  if(F.q){const h=[r.n,r.prog,r.coh,r.loc,r.cad,r.sec,r.check].join(' ').toLowerCase(); if(!h.includes(F.q)) return false;}
  return true;
}
const filtered=()=>ROWS.filter(r=>pass(r));

function buildFilters(){
  const opts={st:ST_ORDER,hq:['Y','N',''],conf:['published','inferred-from-pattern','unknown']};
  const lab={st:ST,hq:HQ,conf:CF};
  document.querySelectorAll('#appsCal .dd').forEach(dd=>{
    const k=dd.dataset.key;
    dd.querySelector('.ddb').innerHTML=opts[k].map(o=>
      `<label><input type="checkbox" value="${esc(o)}"> ${esc(lab[k][o]||o)}<span class="cnt" data-o="${esc(o)}"></span></label>`).join('')+
      `<div class="ddq"><button type="button" data-a="all">All</button><button type="button" data-a="none">None</button><button type="button" data-a="def">Default</button></div>`;
    dd.addEventListener('change',e=>{const v=e.target.value; e.target.checked?F[k].add(v):F[k].delete(v); renderAll();});
    dd.querySelector('.ddq').addEventListener('click',e=>{const a=e.target.dataset.a; if(!a)return;
      F[k]=new Set(a==='all'?opts[k]:a==='none'?[]:DEF[k]); renderAll();});
  });
  const cads={}; ROWS.forEach(r=>{const c=r.cad||'(blank)';cads[c]=(cads[c]||0)+1;});
  document.getElementById('apCad').innerHTML='<option value="">All cadences</option>'+
    Object.entries(cads).sort((a,b)=>b[1]-a[1]).map(([c,n])=>`<option value="${esc(c==='(blank)'?'':c)}">${esc(c)} (${n})</option>`).join('');
  const secs={}; ROWS.forEach(r=>(r.sec||'').split(';').filter(Boolean).forEach(s=>secs[s]=(secs[s]||0)+1));
  const sel=document.getElementById('apSec');
  if(Object.keys(secs).length){ sel.hidden=false;
    sel.innerHTML='<option value="">All sectors</option>'+Object.entries(secs).sort((a,b)=>a[0].localeCompare(b[0]))
      .map(([s,n])=>`<option value="${esc(s)}">${esc(s)} (${n})</option>`).join(''); }
}
function syncFilters(){
  const lab={st:ST,hq:HQ,conf:CF};
  document.querySelectorAll('#appsCal .dd').forEach(dd=>{
    const k=dd.dataset.key;
    dd.querySelectorAll('input').forEach(i=>i.checked=F[k].has(i.value));
    dd.querySelectorAll('.cnt').forEach(c=>{const o=c.dataset.o;c.textContent=ROWS.filter(r=>r[k]===o&&pass(r,k)).length;});
    const isDef=F[k].size===DEF[k].length&&DEF[k].every(v=>F[k].has(v));
    const names=[...F[k]].map(v=>lab[k][v]||v);
    dd.querySelector('.ddv').textContent=': '+(isDef&&k==='st'?'Active':F[k].size===0?'none':names.length<=2?names.join(', '):F[k].size+' selected');
    dd.querySelector('summary').classList.toggle('chg',!isDef);
  });
  document.getElementById('apCad').value=F.cad; document.getElementById('apSec').value=F.sec;
  document.getElementById('apQ').value=F.q;
}

// ---------- bits ----------
const infB=r=>r.conf==='inferred-from-pattern'?`<span class="b-inf" title="${esc(r.notes||'Inferred from past cycles; not published by the accelerator')}">INFERRED</span>`:'';
const locC=r=>r.loc?`<span class="loc">${esc(r.loc)}</span>`:'';
const stC=r=>`<span class="stc st-${esc(r.st.split('_')[0])}">${esc(ST[r.st]||r.st)}</span>`;
const applyA=r=>okUrl(r.apply)?`<a class="apply" href="${esc(r.apply)}" target="_blank" rel="noopener">Apply &#8599;</a>`:'';
const nmA=r=>`<a href="#" class="opencard" data-i="${r.i}">${esc(r.n)}</a>`;
const progOf=r=>(r.prog&&r.prog!==r.n)?r.prog:'';
const exactClose=r=>isDay(r.close)&&r.conf==='published';

// ---------- top strip ----------
function renderHot(rs){
  const ex=rs.filter(exactClose);
  const closed=ex.filter(r=>r.close<TD&&r.close>=addDays(TD,-14)).sort((a,b)=>b.close.localeCompare(a.close)).map(r=>({r,d:r.close,t:'closed'}));
  const soon=[...ex.filter(r=>r.close>=TD&&r.close<=addDays(TD,14)).map(r=>({r,d:r.close,t:'closes'})),
              ...rs.filter(r=>isDay(r.open)&&r.open>=TD&&r.open<=addDays(TD,14)).map(r=>({r,d:r.open,t:'opens'}))]
              .sort((a,b)=>a.d.localeCompare(b.d));
  const box=(title,list,empty)=>{const N=7;
    return `<div class="hotb"><h3>${title}<span>${list.length}</span></h3>`+(list.length?`<ul>`+list.slice(0,N).map(({r,d,t})=>
      `<li><span class="hd">${fmtS(d)}</span><span class="hn">${nmA(r)}${progOf(r)?` <span style="color:var(--muted)">&middot; ${esc(progOf(r))}</span>`:''}</span><span class="ht ht-${t}">${t}</span></li>`).join('')+
      (list.length>N?`<li class="more">+${list.length-N} more</li>`:'')+`</ul>`:`<div class="none">${empty}</div>`)+`</div>`;};
  document.getElementById('apHot').innerHTML=
    box('Closed in the last 14 days',closed,'Nothing closed in the last two weeks for this filter.')+
    box('Opening soon / closing in 14 days',soon,'Nothing opening or closing in the next two weeks for this filter.');
}

// ---------- upcoming deadlines (30 / 60 / 90-day windows) ----------
const WIN={30:[0,30],60:[31,60],90:[61,90]};
function renderUp(rs){
  const ex=rs.filter(exactClose).map(r=>({r,d:dayDiff(TD,r.close)}));
  const inW=(x,w)=>x.d>=WIN[w][0]&&x.d<=WIN[w][1];
  const n={30:ex.filter(x=>inW(x,30)).length,60:ex.filter(x=>inW(x,60)).length,90:ex.filter(x=>inW(x,90)).length};
  const later=ex.filter(x=>x.d>90).length, closed=ex.filter(x=>x.d<0).length;
  const tiles=[[30,'Closing in 0–30 days',n[30]],[60,'Closing in 31–60 days',n[60]],[90,'Closing in 61–90 days',n[90]],
               [null,'Closing after 90 days',later],[null,'Already closed',closed]];
  const T=document.getElementById('apTiles');
  T.innerHTML=tiles.map(([w,l,c])=>`<div class="kpi${w?' click':''}${w===win?' sel':''}"${w?` data-w="${w}" role="button" tabindex="0"`:''}><div class="n">${c}</div><div class="l">${l}</div></div>`).join('');
  const items=ex.filter(x=>inW(x,win)).sort((a,b)=>a.r.close.localeCompare(b.r.close));
  const tbc=rs.filter(r=>isMon(r.close)).length;
  document.getElementById('apUpSub').innerHTML=`Published application deadlines closing ${WIN[win][0]}–${WIN[win][1]} days from today (${fmtD(TD)}). Click a tile to switch window.`+
    (tbc?` ${tbc} more ${tbc===1?'window has':'windows have'} only a month published &mdash; see the Month grid.`:'');
  const byM={}; items.forEach(x=>{const k=x.r.close.slice(0,7);(byM[k]=byM[k]||[]).push(x);});
  const months=Object.keys(byM).sort();
  document.getElementById('apStrip').innerHTML=months.map(mk=>{const[y,m]=mk.split('-');
    return `<button class="mcell" onclick="scrollToMonth('apu-${mk}')"><span class="mc-top">${MON[+m-1]} '${y.slice(2)}</span><span class="mc-n">${byM[mk].length}</span><span class="mc-sub">closing</span></button>`;}).join('');
  const A=document.getElementById('apAgenda');
  if(!items.length){A.innerHTML=`<div class="cal-note" style="padding:22px 2px;font-size:14px">No published deadlines in this window for the current filters.</div>`;return;}
  A.innerHTML=months.map(mk=>{const[y,m]=mk.split('-');
    return `<div id="apu-${mk}"><div class="ag-h">${MONF[+m-1]} ${y} &middot; ${byM[mk].length} closing</div>`+byM[mk].map(({r,d})=>
      `<div class="ag-item"><div class="ag-date">${r.close.slice(8,10)}<span class="ag-mo">${MON[+r.close.slice(5,7)-1]}</span></div>`+
      `<div class="ag-body"><div class="ag-name">${nmA(r)}${locC(r)}</div><div class="ag-meta">${esc([progOf(r),r.coh].filter(Boolean).join(' · '))||'&nbsp;'}</div></div>`+
      `<div class="ag-right">${applyA(r)}<div class="ag-rel">${d===0?'closes today':d===1?'1 day left':d+' days left'}</div></div></div>`).join('')+`</div>`;}).join('');
}

// ---------- month-by-month grid (12 months from this month) ----------
function renderGrid(rs){
  const t=new Date(TD+'T00:00:00'), months=[];
  for(let i=0;i<12;i++){const d=new Date(t.getFullYear(),t.getMonth()+i,1);months.push(`${d.getFullYear()}-${pad(d.getMonth()+1)}`);}
  const M={}; months.forEach(m=>M[m]={day:[],tbc:[]});
  const put=(s,kind,r)=>{ if(!s) return;
    if(isDay(s)&&M[s.slice(0,7)]) M[s.slice(0,7)].day.push({s,kind,r});
    else if(isMon(s)&&M[s]) M[s].tbc.push({s,kind,r}); };
  rs.forEach(r=>{put(r.close,'deadline',r);put(r.start,'start',r);put(r.demo,'demo',r);});
  const KO={deadline:0,start:1,demo:2}, KL={deadline:'deadline',start:'starts',demo:'demo day'};
  const li=(x,day)=>`<li class="k-${x.kind}"><span class="mg-d">${day?+x.s.slice(8,10):''}</span><span class="mg-t">${nmA(x.r)}${x.kind==='deadline'?infB(x.r):''}`+
    `${progOf(x.r)||x.r.coh?`<span class="mg-p">${esc([progOf(x.r),x.r.coh].filter(Boolean).join(' · '))}</span>`:''}</span><span class="mg-k">${KL[x.kind]}</span></li>`;
  document.getElementById('apGrid').innerHTML=`<p class="ap-sub">Deadlines by day, with program starts and demo days as secondary markers. Month-only dates sit in each month's &ldquo;Date TBC&rdquo; row.</p><div class="mgrid">`+months.map(mk=>{
    const [y,m]=mk.split('-'), b=M[mk];
    b.day.sort((a,c)=>a.s.localeCompare(c.s)||KO[a.kind]-KO[c.kind]);
    const nd=b.day.filter(x=>x.kind==='deadline').length+b.tbc.filter(x=>x.kind==='deadline').length;
    return `<div class="mg"><div class="mg-h"><b>${MONF[+m-1]} ${y}</b><span>${nd} deadline${nd===1?'':'s'}</span></div>`+
      (b.day.length?`<ul>${b.day.map(x=>li(x,true)).join('')}</ul>`:(b.tbc.length?'':`<div class="mg-empty">Nothing dated this month.</div>`))+
      (b.tbc.length?`<div class="mg-tbc"><div class="mg-tbch">Date TBC</div><ul>${b.tbc.map(x=>li(x,false)).join('')}</ul></div>`:'')+`</div>`;
  }).join('')+`</div>`;
}

// ---------- all programs list ----------
function nextKey(r){
  if(isDay(r.close)&&r.close>=TD) return '0'+r.close;
  if(isMon(r.close)&&r.close>=TD.slice(0,7)) return '1'+r.close;
  if(r.cad==='rolling'||r.st==='active_rolling') return '2';
  if(r.close) return '3'+r.close;
  return '4';
}
function winCell(r){
  if(!r.open&&!r.close) return (r.st==='active_rolling'||r.cad==='rolling')?'Rolling':'<span class="dash">date not published</span>';
  return `${r.open?`${esc(fmtD(r.open))} &rarr; `:''}${r.close?esc(fmtD(r.close)):'<span class="dash">close not published</span>'}${infB(r)}`;
}
function renderList(rs){
  const L=[...rs].sort((a,b)=>nextKey(a).localeCompare(nextKey(b))||a.n.localeCompare(b.n));
  document.getElementById('apList').innerHTML=`<div class="card"><div class="scroll"><table class="aplist"><thead><tr>
    <th>Accelerator / program</th><th>Location</th><th>Status</th><th>Cadence</th><th>Application window</th><th>Window</th></tr></thead><tbody>`+
    L.map(r=>`<tr><td>${nmA(r)}${progOf(r)||r.coh?`<div class="sub">${esc([progOf(r),r.coh].filter(Boolean).join(' · '))}</div>`:''}</td>`+
      `<td>${r.loc?esc(r.loc):'<span class="dash">&mdash;</span>'}</td><td>${stC(r)}</td><td class="nw">${esc(r.cad)||'<span class="dash">&mdash;</span>'}</td>`+
      `<td>${winCell(r)}</td><td class="nw">${esc(WS[r.ws]||r.ws)||'<span class="dash">&mdash;</span>'}</td></tr>`).join('')+
    `</tbody></table></div></div>`;
}

// ---------- per-accelerator card ----------
function openCard(i){
  const r=ROWS[i]; if(!r) return;
  const row=(k,v)=>v?`<dt>${k}</dt><dd>${v}</dd>`:'';
  const srcs=(r.src||'').split('|').map(s=>s.trim()).filter(okUrl);
  const others=ROWS.filter(o=>o!==r&&(r.slug?o.slug===r.slug:o.n===r.n));
  const nextW=(r.open||r.close)?`${r.open?esc(fmtD(r.open))+' &rarr; ':''}${esc(fmtD(r.close))}${infB(r)}`:
    ((r.st==='active_rolling'||r.cad==='rolling')?'Rolling applications':'date not published');
  document.getElementById('apCard').innerHTML=
    `<h2 id="apCardT">${esc(r.n)}</h2><div class="sub">${esc([progOf(r),r.coh].filter(Boolean).join(' · '))||'&nbsp;'}</div>`+
    `<div class="chips">${stC(r)}${r.loc?`<span class="loc" style="margin-left:0">${esc(r.loc)}</span>`:''}${r.ws?`<span class="stc">${esc(WS[r.ws]||r.ws)}</span>`:''}</div><dl>`+
    row('Cadence',esc(r.cad||'unknown'))+row('Next window',nextW)+
    row('Program start',r.start?esc(fmtD(r.start)):'')+row('Program end',r.end?esc(fmtD(r.end)):'')+
    row('Demo day',r.demo?esc(fmtD(r.demo)):'')+row('Check size / terms',esc(r.check))+
    row('Notes',esc(r.notes))+
    row('Sources',srcs.length?`<span class="src">${srcs.map(s=>`<a href="${esc(s)}" target="_blank" rel="noopener">${esc(s.replace(/^https?:\/\/(www\.)?/,'').slice(0,70))}</a>`).join('')}</span>`:'')+
    row('Last checked',esc(r.lc))+`</dl>`+
    `<div class="acts">${okUrl(r.apply)?`<a class="apbtn" style="color:var(--blue)" href="${esc(r.apply)}" target="_blank" rel="noopener">Apply &#8599;</a>`:''}`+
    `${r.slug?`<a class="apbtn" href="${DRU}${esc(r.slug)}" target="_blank" rel="noopener">Dealroom profile &#8599;</a>`:''}`+
    `${exactClose(r)&&r.close>=TD?`<a class="apbtn" href="${esc(gcalUrl(r))}" target="_blank" rel="noopener">Add to Google Calendar &#8599;</a>`:''}</div>`+
    (others.length?`<div class="oth"><b>Other windows for this accelerator</b>${others.map(o=>`<div>${nmA(o)} <span style="color:var(--muted)">&middot; ${esc([progOf(o),o.coh].filter(Boolean).join(' · '))||esc(ST[o.st]||o.st)} &middot; ${esc(o.close?fmtD(o.close):'date not published')}</span>${infB(o)}</div>`).join('')}</div>`:'');
  const ov=document.getElementById('apOvl'); ov.hidden=false; ov.querySelector('.x').focus();
}
const closeCard=()=>{document.getElementById('apOvl').hidden=true;};

// ---------- exports ----------
const CSV_COLS=[['accelerator','n'],['dealroom_url',r=>r.slug?DRU+r.slug:''],['program','prog'],['cohort_name','coh'],
  ['application_open','open'],['application_close','close'],['program_start','start'],['apply_url','apply'],['notes','notes'],
  ['status','st'],['hq_us','hq'],['location','loc'],['cadence','cad'],['program_end','end'],['demo_day','demo'],
  ['check_size_terms','check'],['source_urls','src'],['date_confidence','conf'],['window_status','ws'],['last_checked','lc'],['list_source','ls']];
function toCsv(rs){
  const q=v=>{v=String(v==null?'':v);return /[",\r\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v;};
  return [CSV_COLS.map(c=>c[0]).join(',')].concat(rs.map(r=>CSV_COLS.map(([,k])=>q(typeof k==='function'?k(r):r[k])).join(','))).join('\r\n')+'\r\n';
}
const slugify=t=>t.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'').slice(0,80);
const icsEsc=t=>(t||'').replace(/\\/g,'\\\\').replace(/;/g,'\\;').replace(/,/g,'\\,').replace(/\r/g,'').replace(/\n/g,'\\n');
function fold(line){const enc=new TextEncoder();const out=[];let cur='';
  for(const ch of line){ if(enc.encode(cur+ch).length>74){out.push(cur);cur=ch;} else cur+=ch; }
  out.push(cur); return out.join('\r\n ');}
function toIcs(rs){
  const st=new Date().toISOString().replace(/[-:]/g,'').replace(/\.\d+Z$/,'Z');
  const L=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Dealroom//Accelerator Cohort Calendar//EN','CALSCALE:GREGORIAN','METHOD:PUBLISH','X-WR-CALNAME:Accelerator application deadlines'];
  let n=0;
  rs.filter(r=>exactClose(r)&&r.close>=TD).sort((a,b)=>a.close.localeCompare(b.close)).forEach(r=>{
    const d=r.close.replace(/-/g,''), e=addDays(r.close,1).replace(/-/g,'');
    const desc=[r.coh,r.loc,r.lc?'Last checked '+r.lc:''].filter(Boolean).join(' · ');
    L.push('BEGIN:VEVENT','UID:'+d+'-'+slugify(r.n+'|'+r.prog+'|'+r.coh)+'@accelerator-coverage','DTSTAMP:'+st,
      'DTSTART;VALUE=DATE:'+d,'DTEND;VALUE=DATE:'+e,'SUMMARY:'+icsEsc(`${r.n}: ${r.prog||r.n} deadline`),'TRANSP:TRANSPARENT');
    if(okUrl(r.apply)) L.push('URL:'+r.apply);
    if(desc) L.push('DESCRIPTION:'+icsEsc(desc));
    L.push('END:VEVENT'); n++;
  });
  L.push('END:VCALENDAR');
  return {text:L.map(fold).join('\r\n')+'\r\n',n};
}
function toast(msg){const t=document.createElement('div');t.className='aptoast';t.textContent=msg;document.body.appendChild(t);setTimeout(()=>t.remove(),3500);}
function blobSave(name,text,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type}));
  a.download=name;document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove();},800);}
function saveCsv(){
  const rs=filtered(); if(!rs.length){toast('No rows match the current filters.');return;}
  const name=`cohort_calendar_${TD}.csv`, text=toCsv(rs);
  if(DL){ DL.save({filename:name,data:text}).catch(e=>{ if(e&&e.code==='declined')return;
      if(e&&(e.code==='rate_limited'))toast('A save prompt is already open.'); else toast('Saving is not available in this view.'); }); }
  else blobSave(name,text,'text/csv');
}
// The claude.ai viewer can neither serve nor download .ics, so there the button opens the published
// default-view file (served as plain text: save it as .ics to import) and each card offers an
// "Add to Google Calendar" link; opened as a plain page, it builds an .ics from the current filters.
function setIcsMode(){
  const a=document.getElementById('apIcs'); if(!a) return;
  if(DL){ a.textContent='Open .ics (default view)';
    a.title='Upcoming published deadlines for the default view (active programs, US HQ). Opens as text: save it with a .ics extension, then import into your calendar.'; }
  else a.title='Upcoming published deadlines for the current filters, as a calendar file';
}
function gcalUrl(r){
  const d=r.close.replace(/-/g,''), e=addDays(r.close,1).replace(/-/g,'');
  const det=[progOf(r),r.coh,okUrl(r.apply)?'Apply: '+r.apply:''].filter(Boolean).join('\n');
  return 'https://calendar.google.com/calendar/render?action=TEMPLATE&text='+encodeURIComponent(`${r.n}: ${r.prog||r.n} deadline`)+
    '&dates='+d+'/'+e+'&details='+encodeURIComponent(det);
}
function icsClick(e){
  if(DL) return;                          // let the link open the published cohort_deadlines.ics
  e.preventDefault();
  const {text,n}=toIcs(filtered());
  if(!n){toast('No upcoming published deadlines for the current filters.');return;}
  blobSave(`accelerator_deadlines_${TD}.ics`,text,'text/calendar');
}

// ---------- wiring + render ----------
function wire(){
  const root=document.getElementById('appsCal');
  document.getElementById('apQ').addEventListener('input',e=>{F.q=e.target.value.trim().toLowerCase();renderAll();});
  document.getElementById('apCad').addEventListener('change',e=>{F.cad=e.target.value;renderAll();});
  document.getElementById('apSec').addEventListener('change',e=>{F.sec=e.target.value;renderAll();});
  document.getElementById('apReset').addEventListener('click',()=>{F.st=new Set(DEF.st);F.hq=new Set(DEF.hq);F.conf=new Set(DEF.conf);F.cad='';F.sec='';F.q='';renderAll();});
  document.getElementById('apCsv').addEventListener('click',saveCsv);
  document.getElementById('apIcs').addEventListener('click',icsClick);
  document.getElementById('apTabs').addEventListener('click',e=>{const v=e.target.dataset&&e.target.dataset.v;if(!v)return;view=v;renderAll();});
  document.getElementById('apTiles').addEventListener('click',e=>{const k=e.target.closest('[data-w]');if(k){win=+k.dataset.w;renderAll();}});
  document.getElementById('apTiles').addEventListener('keydown',e=>{const k=e.target.closest('[data-w]');if(k&&(e.key==='Enter'||e.key===' ')){e.preventDefault();win=+k.dataset.w;renderAll();}});
  const openFrom=e=>{const a=e.target.closest('.opencard');if(!a)return;e.preventDefault();openCard(+a.dataset.i);};
  root.addEventListener('click',openFrom);
  const ov=document.getElementById('apOvl');
  ov.addEventListener('click',e=>{ if(e.target===ov||e.target.closest('.x')) closeCard(); else openFrom(e); });
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!ov.hidden)closeCard();});
  document.addEventListener('click',e=>{document.querySelectorAll('#appsCal details.dd[open]').forEach(d=>{if(!d.contains(e.target))d.open=false;});});
}
function renderAll(){
  syncFilters();
  const rs=filtered();
  renderHot(rs);
  document.querySelectorAll('#apTabs button').forEach(b=>b.classList.toggle('on',b.dataset.v===view));
  document.getElementById('apUp').hidden=view!=='up';
  document.getElementById('apGrid').hidden=view!=='grid';
  document.getElementById('apList').hidden=view!=='list';
  if(view==='up') renderUp(rs); else if(view==='grid') renderGrid(rs); else renderList(rs);
  const inf=ROWS.filter(r=>r.conf==='inferred-from-pattern').length;
  document.getElementById('apFoot').innerHTML=`${rs.length.toLocaleString()} of ${ROWS.length.toLocaleString()} programs match the filters`+
    (F.conf.has('inferred-from-pattern')?'':` &middot; ${inf} inferred dates hidden (turn on &ldquo;Inferred&rdquo; under Date confidence)`)+
    `<br>Last checked ${esc(CC.last_checked)} &middot; source: Cohort Calendar sheet &middot; inferred dates are badged`;
}
})();
"""
