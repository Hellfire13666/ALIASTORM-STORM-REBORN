"""Self-contained, local-only AliaStorm HTML evidence viewer.

Rendering runs only on existing saved scan records; it does not fetch sites,
transmit results, change classification, or open a web browser.
"""
from __future__ import annotations

import base64
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ASSET = Path(__file__).resolve().parent / 'assets' / 'storm-reborn.webp'
STATUSES = ('POSSIBLE', 'PAGE_MENTION', 'REVIEW', 'NOT_FOUND', 'BLOCKED', 'UNRESOLVED')
LABELS = {
    'POSSIBLE':'Possible', 'PAGE_MENTION':'Page mention', 'REVIEW':'Review',
    'NOT_FOUND':'Not found', 'BLOCKED':'Blocked', 'UNRESOLVED':'Unresolved',
}


def e(value):
    """Escape all external text and attributes, including scanned page metadata."""
    return escape(str('' if value is None else value), quote=True)


def detail(label, value, mono=False):
    if value is None or value == '' or value == [] or value == {}:
        return ''
    if isinstance(value, dict):
        value = '\n'.join(f'{key}: {val}' for key, val in value.items())
    if isinstance(value, (list, tuple)):
        value = ', '.join(str(v) for v in value)
    css = ' evidence-mono' if mono else ''
    return f'<div class="field"><dt>{e(label)}</dt><dd class="field-content{css}">{e(value)}</dd></div>'


def result_card(row, index):
    status = str(row.get('status') or 'UNRESOLVED').upper()
    if status not in STATUSES:
        status = 'UNRESOLVED'
    url = str(row.get('url') or '')
    http = row.get('http')
    http_label = str(http) if http is not None else '—'
    site = str(row.get('site') or 'Unknown source')
    title = str(row.get('title') or '')
    desc = str(row.get('description') or '')
    headline = title or desc or ('No confirmed profile evidence' if status == 'REVIEW' else 'Public source checked')
    pieces = [detail('Source URL',url,True)]
    for label, key, mono in (
        ('Title','title',False), ('Description','description',False),
        ('H1 heading','h1',False), ('Canonical','canonical',True),
        ('Evidence fields','evidence_fields',False),
        ('Visible HTML excerpt','html_excerpt',True),
        ('Raw HTML excerpt','raw_html_excerpt',True),
        ('Response headers','response_headers',True),
        ('Observed note','detail',False),('Checked UTC','checked_utc',True),
    ):
        pieces.append(detail(label, row.get(key), mono))
    evidence_fields=row.get('evidence_fields') or []
    field_count=len(evidence_fields) if isinstance(evidence_fields,(list,tuple)) else 0
    # URLs are displayed, but not turned into active links inside the offline report.
    # That keeps the viewer truly offline and avoids accidentally visiting arbitrary sites.
    return f'''<details class="record" data-status="{e(status)}" data-index="{index}">
 <summary><span class="rec-number">{index:03d}</span>
  <span class="pill status-{e(status.lower())}">{e(LABELS[status])}</span>
  <span class="rec-site">{e(site)}</span><span class="rec-http">HTTP {e(http_label)}</span>
  <span class="rec-headline">{e(headline)}</span><span class="rec-carat" aria-hidden="true">⌄</span>
 </summary>
 <div class="record-body"><div class="record-intro">{field_count} evidence field(s) · {e(http_label)} HTTP response · Public content, independent review required</div><dl>{''.join(pieces)}</dl></div>
</details>'''


def render_report(username, rows, *, saved_utc=None, preview=False):
    """Return an entirely offline HTML report with a single embedded image."""
    if saved_utc is None:
        saved_utc = datetime.now(timezone.utc).isoformat()
    counts=Counter(str(x.get('status') or 'UNRESOLVED').upper() for x in rows)
    artwork=base64.b64encode(ASSET.read_bytes()).decode('ascii')
    filters='\n'.join(
        f'<button type="button" class="filter" data-filter="{s}" aria-pressed="false"><span class="filter-dot status-{s.lower()}"></span>{LABELS[s]} <strong>{counts[s]}</strong></button>'
        for s in STATUSES
    )
    cards='\n'.join(result_card(r,i) for i,r in enumerate(rows,1))
    first_four=sum(counts[s] for s in ('POSSIBLE','PAGE_MENTION','REVIEW','NOT_FOUND'))
    # Only factual summaries; the status pills must not imply ownership of accounts.
    html='''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark"><meta name="referrer" content="no-referrer"><title>ALIASTORM // STORM REBORN · Offline Evidence</title>
<style>
:root{color-scheme:dark;--bg:#060513;--panel:#100f25;--line:#524576;--ink:#f4f3ff;--soft:#bec4e1;--pink:#ff4fe1;--cyan:#2ce9fa;--lime:#8dff46;--yellow:#ffe44e;--violet:#bb86ff;--red:#ff7287;--orange:#ffa657}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(ellipse at 75% -10%,#242062 0%,transparent 46%),radial-gradient(ellipse at 8% 56%,#1c0e38,transparent 50%),#060513;color:var(--ink);font:15px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}
body:before{content:"";position:fixed;inset:0;pointer-events:none;z-index:5;opacity:.14;background:repeating-linear-gradient(0deg,transparent 0 4px,#7542b0 5px,transparent 6px)}
header,main,footer{max-width:1380px;margin:0 auto}.stripe{height:5px;background:linear-gradient(90deg,#fb39d8,#8b55ff,#29e4ff,#82ff50,#f9e247,#ff9d32,#fd3ec5);box-shadow:0 0 26px #a400d8}.mast{padding:22px 26px 10px;display:flex;gap:16px;justify-content:space-between;align-items:center;flex-wrap:wrap}.brand{font-weight:950;letter-spacing:.14em;font-size:.9rem;color:var(--cyan)}.brand span{color:var(--pink)}.right-tag{border:1px solid #6255a6;background:#120e35;padding:6px 13px;border-radius:99px;color:var(--soft);font-size:.72rem;font-weight:750;letter-spacing:.1em}.hero{padding:0 24px}.hero-art{width:100%;display:block;border-radius:20px;border:1px solid #b14aff;box-shadow:0 18px 65px #000c,0 0 29px #ab22fe42;aspect-ratio:1672/941;object-fit:cover}.art-footer{margin-top:-24px;position:relative;height:26px;pointer-events:none;background:linear-gradient(transparent,#060513)}
main{padding:18px 24px 50px}.brief{display:flex;align-items:end;justify-content:space-between;gap:22px;margin:10px 0 18px;flex-wrap:wrap}.kicker{font-size:.75rem;letter-spacing:.17em;color:var(--pink);font-weight:900}.brief h1{font-size:clamp(1.5rem,4vw,3rem);line-height:1.08;margin:7px 0 0;letter-spacing:-.035em}.brief h1 b{background:linear-gradient(105deg,#ff52c9,#72eaff,#a8fc61);color:transparent;background-clip:text}.brief p{color:var(--soft);margin:8px 0 0}.saved{color:var(--soft);font-size:.78rem;border-left:3px solid var(--cyan);padding-left:11px;overflow-wrap:anywhere}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:22px 0}.metric{border:1px solid #514184;border-radius:12px;background:linear-gradient(135deg,#1d1641d9,#0b0b21ea);padding:14px 17px;box-shadow:inset 0 1px #6654ab3b}.metric strong{display:block;font-size:clamp(1.5rem,3vw,2.1rem);line-height:1.1}.metric small{display:block;color:var(--soft);text-transform:uppercase;font-size:.68rem;letter-spacing:.11em;margin-top:6px}.metric:nth-child(1) strong{color:var(--cyan)}.metric:nth-child(2) strong{color:var(--lime)}.metric:nth-child(3) strong{color:var(--yellow)}.metric:nth-child(4) strong{color:var(--pink)}
.notice{border-left:3px solid var(--yellow);padding:12px 15px;background:#231c2d;border-radius:0 10px 10px 0;color:#ffebaf;font-size:.88rem;margin:18px 0 23px}.notice strong{color:#fff}.tools{background:linear-gradient(160deg,#171331,#0d1026);border:1px solid #50487f;border-radius:16px;padding:20px;margin-top:10px}.toolrow{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.toolrow input,.toolrow select{min-height:45px;padding:10px 12px;border:1px solid #7361a7;border-radius:9px;background:#080c23;color:#fff;font:inherit}.toolrow input{flex:1;min-width:170px}.toolrow select{min-width:160px}.toolrow input:focus-visible,.toolrow select:focus-visible,.filter:focus-visible,.small-btn:focus-visible,summary:focus-visible{outline:2px solid var(--cyan);outline-offset:3px}.filters{display:flex;gap:8px;flex-wrap:wrap;margin-top:17px}.filter{font:inherit;font-weight:700;color:#efecff;cursor:pointer;background:#12162e;border:1px solid #453a70;padding:9px 12px;border-radius:10px}.filter strong{color:#fff;margin-left:5px}.filter:hover,.filter[aria-pressed="true"]{background:#332554;border-color:var(--pink)}.filter-dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:#999;margin-right:8px}.filter-dot.status-possible{background:var(--lime)}.filter-dot.status-page_mention{background:var(--cyan)}.filter-dot.status-review{background:var(--yellow)}.filter-dot.status-not_found{background:#a3acc7}.filter-dot.status-blocked{background:var(--red)}.filter-dot.status-unresolved{background:var(--violet)}
.list-head{margin:22px 2px 12px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.list-head h2{margin:0;font-size:1rem;letter-spacing:.11em;color:var(--cyan)}.list-head span{color:var(--soft);font-size:.82rem}.small-btn{background:#151436;border:1px solid #685391;color:#e8def8;padding:8px 13px;border-radius:8px;cursor:pointer}.small-btn:hover{border-color:var(--pink)}
.records{display:flex;flex-direction:column;gap:9px}.record[hidden]{display:none!important}.record{border:1px solid #4b427b;border-left:4px solid var(--violet);background:linear-gradient(140deg,#14122b,#090c1d);border-radius:11px;overflow:hidden}.record[data-status="POSSIBLE"]{border-left-color:var(--lime)}.record[data-status="PAGE_MENTION"]{border-left-color:var(--cyan)}.record[data-status="REVIEW"]{border-left-color:var(--yellow)}.record[data-status="NOT_FOUND"]{border-left-color:#939dbe}.record[data-status="BLOCKED"]{border-left-color:var(--red)}.record[data-status="UNRESOLVED"]{border-left-color:var(--violet)}.record summary{cursor:pointer;padding:13px 17px;display:grid;align-items:center;grid-template-columns:37px 114px minmax(140px,1fr) 92px;gap:8px 12px;list-style:none}.record summary::-webkit-details-marker{display:none}.record[open] summary{background:#181436;border-bottom:1px solid #423b72}.record summary:hover{background:#1d173b}.rec-number{color:#8d95c0;font:700 .82rem ui-monospace,monospace}.pill{font-size:.68rem;font-weight:900;text-align:center;padding:5px 6px;border-radius:5px;border:1px solid currentColor;letter-spacing:.04em;text-transform:uppercase}.pill.status-possible{color:var(--lime)}.pill.status-page_mention{color:var(--cyan)}.pill.status-review{color:var(--yellow)}.pill.status-not_found{color:#9aa8ce}.pill.status-blocked{color:var(--red)}.pill.status-unresolved{color:var(--violet)}.rec-site{font-size:.95rem;font-weight:800;overflow-wrap:anywhere}.rec-http{color:#b5e7ff;white-space:nowrap;font:800 .82rem ui-monospace,monospace}.rec-headline{grid-column:3/5;color:var(--soft);font-size:.82rem;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.rec-carat{display:none}.record-body{padding:14px 20px 21px;background:#080d1f}.record-intro{color:#9cb0d9;font-size:.79rem;margin-bottom:12px}.record dl{margin:0}.field{display:grid;grid-template-columns:172px minmax(0,1fr);gap:12px;padding:10px 0;border-bottom:1px solid #37304d}.field:last-child{border-bottom:none}.field dt{font-size:.78rem;letter-spacing:.06em;text-transform:uppercase;color:var(--cyan);font-weight:800}.field dd{margin:0;color:#f1f4ff;white-space:pre-wrap;overflow-wrap:anywhere}.field .evidence-mono{font: .83rem/1.65 ui-monospace,"SFMono-Regular",Consolas,monospace;color:#fbe6a2}.empty{display:none;border:1px dashed #7564a4;padding:25px;text-align:center;border-radius:13px;color:var(--soft)}footer{border-top:1px solid #443567;padding:20px 28px 30px;color:var(--soft);font-size:.79rem;display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px}.rainbow-rule{height:4px;background:linear-gradient(90deg,var(--pink),var(--violet),var(--cyan),var(--lime),var(--yellow),var(--orange),var(--pink));margin:28px 0 4px;border-radius:4px}
@media(min-width:850px){.record summary{grid-template-columns:42px 124px minmax(160px,1fr) 110px}.rec-headline{grid-column:3/5}}
@media(max-width:760px){.hero{padding:0 12px}.hero-art{border-radius:11px}main{padding:14px 13px 38px}.mast{padding:15px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.brief{margin-top:0}.toolrow input,.toolrow select{width:100%}.record summary{grid-template-columns:30px 109px minmax(100px,1fr);gap:7px 9px;padding:12px}.rec-site{font-size:.82rem}.rec-http{grid-column:2/4}.rec-headline{grid-column:2/4}.field{grid-template-columns:1fr;gap:2px}.record-body{padding:13px}.tools{padding:13px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
</style></head><body><div class="stripe"></div>
<header><div class="mast"><span class="brand">GLITCHBYTE PHANTOM LABS <span>//</span> ALIASTORM</span><span class="right-tag">LOCAL EVIDENCE · OFFLINE VIEWER</span></div>
<div class="hero"><img class="hero-art" alt="ALIASTORM Storm Reborn artwork: rainbow phoenix, neon rose, electric storm and research symbols" src="data:image/webp;base64,__HERO__"><div class="art-footer"></div></div></header>
<main><section class="brief"><div><div class="kicker">// USERNAME → PUBLIC SITES → HTML INTELLIGENCE</div><h1><b>STORM REBORN</b> · Scan results</h1><p>Public website evidence report for <strong>__SUBJECT__</strong></p></div><div class="saved">Report saved: __TIMESTAMP__<br>All analysis stays in this HTML file.</div></section>
<div class="metrics"><div class="metric"><strong>__TOTAL__</strong><small>Sources checked</small></div><div class="metric"><strong>__POSSIBLE__</strong><small>Possible matches</small></div><div class="metric"><strong>__PAGE__</strong><small>Page mentions</small></div><div class="metric"><strong>__BLOCKED__</strong><small>Access blocked</small></div></div>
<div class="notice"><strong>Evidence, not identity.</strong> A matching username, title, page mention or HTTP 200 response does not establish that different accounts belong to one person; blocked and unresolved sites are not confirmed absences. __PREVIEW__</div>
<section class="tools" aria-label="Filter results"><div class="toolrow"><input type="search" id="search" autocomplete="off" placeholder="Search domain, title, URL, metadata..." aria-label="Search local report"><select id="sort" aria-label="Sort source results"><option value="original">Original catalog order</option><option value="site">Site name A to Z</option><option value="status">Evidence status</option></select><button class="small-btn" id="reset" type="button">Clear filters</button></div>
<div class="filters"><button type="button" class="filter" data-filter="ALL" aria-pressed="true">ALL <strong>__TOTAL__</strong></button>__FILTERS__</div></section>
<div class="list-head"><div><h2>// PUBLIC-SITE EVIDENCE STREAM</h2><span id="visible-count">__TOTAL__ / __TOTAL__ sources visible</span></div><button type="button" id="expand-all" class="small-btn">Expand visible records</button></div>
<div id="records" class="records">__RECORDS__</div><div id="empty" class="empty">No records match these filters. Try another site name or clear filters.</div><div class="rainbow-rule"></div></main>
<footer><span>ALIASTORM // STORM REBORN · Self-contained local HTML report</span><span>Public pages only · Original responses are evidence, never attribution · No external scripts or requests</span></footer>
<script>
(()=>{ 'use strict';
 const input=document.getElementById('search'), sort=document.getElementById('sort'), filters=[...document.querySelectorAll('.filter')], parent=document.getElementById('records'), rows=[...parent.querySelectorAll('.record')], counter=document.getElementById('visible-count'), empty=document.getElementById('empty');
 let current='ALL';
 for(const row of rows)row.dataset.searchtext=row.textContent.toLocaleLowerCase();
 const apply=()=>{
   const q=input.value.trim().toLocaleLowerCase(); let n=0;
   for(const row of rows){let ok=(current==='ALL'||row.dataset.status===current)&&(!q||row.dataset.searchtext.includes(q));row.hidden=!ok;if(ok)n++;}
   counter.textContent=`${n} / ${rows.length} sources visible`;
   empty.style.display=n?'none':'block';
 };
 for(const f of filters)f.addEventListener('click',()=>{current=f.dataset.filter;for(const other of filters)other.setAttribute('aria-pressed',String(other===f));apply();});
 input.addEventListener('input',apply);
 const priority=['POSSIBLE','PAGE_MENTION','REVIEW','BLOCKED','NOT_FOUND','UNRESOLVED'];
 sort.addEventListener('change',()=>{
   rows.sort((a,b)=>sort.value==='original'?Number(a.dataset.index)-Number(b.dataset.index):sort.value==='site'?a.querySelector('.rec-site').textContent.localeCompare(b.querySelector('.rec-site').textContent):priority.indexOf(a.dataset.status)-priority.indexOf(b.dataset.status)||Number(a.dataset.index)-Number(b.dataset.index));
   parent.append(...rows);apply();
 });
 document.getElementById('reset').addEventListener('click',()=>{input.value='';sort.value='original';current='ALL';filters.forEach(f=>f.setAttribute('aria-pressed',String(f.dataset.filter==='ALL')));rows.sort((a,b)=>a.dataset.index-b.dataset.index);parent.append(...rows);apply();});
 document.getElementById('expand-all').addEventListener('click',ev=>{
   const visible=rows.filter(x=>!x.hidden),open=visible.some(x=>!x.open);for(const row of visible)row.open=open;ev.currentTarget.textContent=open?'Collapse visible records':'Expand visible records';
 });
 apply();
})();
</script></body></html>'''
    replacements={
        '__HERO__':artwork,'__SUBJECT__':e(username),'__TIMESTAMP__':e(saved_utc),
        '__TOTAL__':str(len(rows)),'__POSSIBLE__':str(counts['POSSIBLE']),
        '__PAGE__':str(counts['PAGE_MENTION']),'__BLOCKED__':str(counts['BLOCKED']),
        '__FILTERS__':filters,'__RECORDS__':cards,
        '__PREVIEW__':'<strong>OFFLINE DEMO:</strong> These sample records are fictional and no real websites were queried.' if preview else '',
    }
    for name, value in replacements.items():
        html=html.replace(name,value)
    return html
