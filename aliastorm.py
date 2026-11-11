#!/usr/bin/env python3
"""ALIASTORM // CLASSIC NEON. Public username-page signals with explicit evidence.

Independent reimplementation retaining the original username-first investigation
and legacy public URL catalog. Signals are not proof of account ownership.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import os
import shutil
import textwrap
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / 'catalog' / 'original-aliastorm-urls.txt'
VERSION = '2.1'
MAX_HTML = 160_000
TIMEOUT = 7
WORKERS = 3
HANDLE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,38}[A-Za-z0-9]$|^[A-Za-z0-9]$')
# Bright, bold 24-bit RGB colors for high-contrast rainbow terminal displays.
# These are presentation-only: scans, source selection, and evidence are unchanged.
TONES = {
    'hotpink': (255, 44, 211), 'pink': (255, 98, 224),
    'purple': (215, 150, 255), 'indigo': (182, 164, 255),
    'blue': (100, 197, 255), 'aqua': (31, 237, 255),
    'cyan': (69, 248, 255), 'green': (118, 255, 88),
    'mint': (145, 255, 196), 'yellow': (255, 246, 65),
    'orange': (255, 180, 78), 'red': (255, 105, 119),
    'white': (255, 255, 255), 'dim': (217, 229, 249),
}
COLORS = {k: f'\x1b[1;38;2;{r};{g};{b}m' for k, (r,g,b) in TONES.items()}
COLORS['reset'] = '\x1b[0m'
# A narrow midnight strip behind just the header improves visibility with
# transparent terminal wallpaper without changing the terminal itself.
PANEL_BG = '\x1b[48;2;12;14;31m'
RAINBOW = ('hotpink', 'pink', 'orange', 'yellow', 'green', 'aqua', 'blue', 'purple')

QUICK_DOMAINS = ('github.com','gitlab.com','www.reddit.com','www.chess.com','www.pinterest.com',
                 'twitch.tv','www.twitch.tv','www.deviantart.com','medium.com','soundcloud.com',
                 'www.kaggle.com','www.openstreetmap.org','www.etsy.com','www.producthunt.com',
                 'www.codepen.io','www.tiktok.com')
HEADER_FIELDS = ('content-type','server','x-powered-by','cache-control','x-frame-options','content-security-policy','x-robots-tag')

class Palette:
    """Display-only styling. Scan, evidence classification, and storage unchanged."""
    def __init__(self, color='auto'):
        self.on = color == 'always' or (color == 'auto' and sys.stdout.isatty() and not os.environ.get('NO_COLOR'))

    def color(self, text, tone):
        value = str(text)
        return f'{COLORS[tone]}{value}{COLORS["reset"]}' if self.on else value

    def rainbow(self, text):
        """Smooth RGB neon sweep for borders, titles, and rainbow dividers."""
        text = str(text)
        if not self.on:
            return text
        stops = [TONES[name] for name in ('hotpink','pink','orange','yellow','green','aqua','blue','purple','hotpink')]
        result = []
        for i, char in enumerate(text):
            where = i * (len(stops)-1) / max(1, len(text)-1)
            low = min(int(where), len(stops)-2)
            fraction = where-low
            rgb = tuple(round(a + (b-a)*fraction) for a,b in zip(stops[low], stops[low+1]))
            result.append(f'\x1b[1;38;2;{rgb[0]};{rgb[1]};{rgb[2]}m{char}')
        return ''.join(result) + COLORS['reset']

    def panel(self, text, tone='white'):
        """Opaque dark backing for a small header region only."""
        return f'{PANEL_BG}{COLORS[tone]}{text}{COLORS["reset"]}' if self.on else str(text)

    def say(self, text, tone='cyan'):
        print(self.color(text, tone), flush=True)

    def width(self):
        # Bound long metadata, preventing scroll through entire-screen lines.
        return max(48, min(112, shutil.get_terminal_size((98, 24)).columns - 1))

    def rule(self, glyph='━'):
        print(self.rainbow('  ' + glyph * max(22, self.width() - 5)), flush=True)

    def detail(self, label, value, label_tone='cyan', value_tone='white', limit=270):
        """Wrap visible terminal output without changing the underlying evidence."""
        text = cut(value, limit)
        if not text:
            return
        prefix = '   ┃ ' + label.ljust(14) + ' '
        room = max(22, self.width() - len(prefix) - 2)
        lines = textwrap.wrap(text, width=room, break_long_words=True, break_on_hyphens=False) or ['']
        print(self.color('   ┃ ', 'purple') + self.color(label.ljust(14), label_tone) + ' ' + self.color(lines[0], value_tone), flush=True)
        for line in lines[1:]:
            print(self.color('   ┃ ', 'purple') + ' '*15 + self.color(line, value_tone), flush=True)

def cut(s, n=200):
    value=' '.join(str(s or '').split())
    return value if len(value)<=n else value[:n-1]+'…'

def safe_handle(name):
    if not HANDLE.fullmatch(name or ''):
        raise ValueError('Enter a username of 1–40 letters, digits, dots, underscores or hyphens (no URL).')
    return name

def handle_in(text, handle):
    return bool(re.search(r'(?<![a-z0-9_])'+re.escape(handle)+r'(?![a-z0-9_])',str(text or ''),re.I))

def load_sources(path=CATALOG):
    entries=[];seen=set()
    for raw in Path(path).read_text(encoding='utf-8').splitlines():
        url=raw.strip()
        if not url or url.startswith('#') or url in seen:continue
        p=urlsplit(url)
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password:
            continue
        seen.add(url)
        entries.append((p.hostname,url))
    return entries

def profile_url(template, handle):
    safe_handle(handle)
    h=quote(handle,safe='')
    if template.endswith(('/','@','~',':','=','?')):
        return template+h
    return template+'/'+h

class PageEvidence(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_title=False;self.in_h1=False;self.hidden=0
        self.titles=[];self.h1=[];self.text=[];self.description='';self.canonical=''
    def handle_starttag(self, tag, attrs):
        tag=tag.lower();a={k.lower():(v or '') for k,v in attrs}
        if tag in ('script','style','noscript','svg'):self.hidden+=1
        if tag=='title':self.in_title=True
        if tag=='h1':self.in_h1=True
        if tag=='meta' and not self.description:
            if (a.get('name') or a.get('property') or '').lower() in ('description','og:description'):
                self.description=a.get('content','')
        if tag=='link' and 'canonical' in a.get('rel','').lower().split():self.canonical=a.get('href','')
    def handle_endtag(self,tag):
        tag=tag.lower()
        if tag=='title':self.in_title=False
        if tag=='h1':self.in_h1=False
        if tag in ('script','style','noscript','svg') and self.hidden:self.hidden-=1
    def handle_data(self, data):
        if self.in_title and len(self.titles)<35:self.titles.append(data)
        if self.in_h1 and len(self.h1)<25:self.h1.append(data)
        if not self.hidden and data.strip() and len(self.text)<1000:self.text.append(data.strip())
    def details(self, handle):
        title=cut(' '.join(self.titles),250)
        desc=cut(self.description,320)
        h1=cut(' '.join(self.h1),180)
        visible=' '.join(self.text)[:30000]
        needle=re.search(r'(?<![a-z0-9_])'+re.escape(handle)+r'(?![a-z0-9_])',visible,re.I)
        snippet=cut(visible[max(0,needle.start()-110):needle.end()+170] if needle else visible[:260],320)
        signal=[]
        if handle_in(title,handle):signal.append('TITLE')
        if handle_in(desc,handle):signal.append('DESCRIPTION')
        if handle_in(h1,handle):signal.append('H1')
        if needle:signal.append('VISIBLE_HTML')
        return dict(title=title,description=desc,h1=h1,canonical=cut(self.canonical,220),html_excerpt=snippet,
                    evidence_fields=signal)

class SameHostRedirect(HTTPRedirectHandler):
    """Don't follow site-to-site redirects or scheme downgrades."""
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        old,new=urlsplit(req.full_url),urlsplit(newurl)
        if new.hostname != old.hostname or new.scheme != old.scheme:
            raise URLError('off-host or protocol-changing redirect refused')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def public_fetch(url,timeout=TIMEOUT):
    request=Request(url,headers={'User-Agent':'AliaStormClassicNeon/2.1 (public page metadata reviewer)',
            'Accept':'text/html,application/xhtml+xml;q=0.9,*/*;q=0.5'})
    opener=build_opener(SameHostRedirect)
    try:
        with opener.open(request,timeout=timeout) as response:
            status=response.status
            headers={k.lower():str(v) for k,v in response.headers.items()}
            mime=headers.get('content-type','').lower()
            if 'html' not in mime and 'text/plain' not in mime:
                body=''
            else:
                data=response.read(MAX_HTML+1)
                body=data[:MAX_HTML].decode('utf-8',errors='replace')
            return status,headers,body,response.geturl(),''
    except HTTPError as exc:
        return exc.code,{k.lower():str(v) for k,v in exc.headers.items()},'',url,f'HTTP {exc.code}'
    except (URLError,OSError,ValueError,TimeoutError) as exc:
        return None,{},'',url,cut(str(exc),140)

def inspect_profile(item,handle,show_headers=False,allow_http=False,fetcher=public_fetch):
    host,template=item; url=profile_url(template,handle)
    record={'site':host,'template':template,'url':url,'final_url':url,'http':None,'status':'UNRESOLVED',
            'title':'','description':'','h1':'','canonical':'','html_excerpt':'','raw_html_excerpt':'','evidence_fields':[],
            'response_headers':{},'detail':'','checked_utc':datetime.now(timezone.utc).isoformat()}
    if urlsplit(url).scheme=='http' and not allow_http:
        record['detail']='Insecure HTTP source preserved in catalog, skipped by default';return record
    try:
        status,headers,body,final,error=fetcher(url)
        record['http']=status;record['final_url']=final;record['detail']=cut(error,140)
        if show_headers:
            record['response_headers']={k:cut(headers[k],190) for k in HEADER_FIELDS if k in headers}
        if status in (404,410):record['status']='NOT_FOUND'
        elif status in (401,403,429):record['status']='BLOCKED'
        elif status !=200:record['status']='UNRESOLVED'
        elif body:
            p=PageEvidence();p.feed(body)
            record.update(p.details(handle))
            raw_match=re.search(r'(?<![a-z0-9_])'+re.escape(handle)+r'(?![a-z0-9_])',body,re.I)
            if raw_match:
                record['raw_html_excerpt']=cut(body[max(0,raw_match.start()-80):raw_match.end()+130],230)
                record['evidence_fields'].append('RAW_HTML')
            fields=record['evidence_fields']
            record['status']='POSSIBLE' if any(f in fields for f in ('TITLE','DESCRIPTION','H1')) else ('PAGE_MENTION' if fields else 'REVIEW')
            record['detail']='Public page content; independent review needed'
        else:
            record['status']='REVIEW'
            record['detail']='Page answered without readable HTML; no evidence of account ownership'
    except Exception as exc:
        record['detail']=cut(f'Public request/parse failed ({type(exc).__name__})')
    return record

def render(row,index,total,ui,display=(True,True,True)):
    """Neon rainbow terminal presentation; source records are not modified."""
    status=row['status']
    tone={'POSSIBLE':'green','PAGE_MENTION':'aqua','REVIEW':'yellow',
          'NOT_FOUND':'white','BLOCKED':'red','UNRESOLVED':'purple'}[status]
    http=row['http'] if row['http'] is not None else '—'
    http_tone = 'green' if http == 200 else ('red' if http in (401,403,404,410,429) else 'yellow')
    progress = f'[{index:03d}/{total:03d}]'
    print('  '+ui.color('●','pink')+' '+ui.color(progress,'purple')+'  '+ui.color(status.ljust(12),tone)
          +' '+ui.color('HTTP','white')+' '+ui.color(str(http).ljust(3),http_tone)
          +'  '+ui.color(row['site'],'yellow'),flush=True)
    ui.detail('SOURCE',row['url'],'aqua','white',limit=340)
    if row.get('evidence_fields'):
        fields=', '.join(row['evidence_fields'])
        ui.detail('EVIDENCE',fields,'green','mint',limit=240)
    for key,tlabel,tvalue,enabled in (
        ('title','hotpink','yellow',display[0]),
        ('description','orange','white',display[1]),
        ('h1','mint','green',True)):
        if enabled and row.get(key):
            ui.detail(key.upper(),row[key],tlabel,tvalue,limit=260)
    if display[2] and row.get('html_excerpt') and 'VISIBLE_HTML' in row.get('evidence_fields',[]):
        ui.detail('VISIBLE HTML',row['html_excerpt'],'aqua','white',limit=300)
    if display[2] and row.get('raw_html_excerpt'):
        ui.detail('RAW HTML',row['raw_html_excerpt'],'pink','yellow',limit=270)
    if row.get('response_headers'):
        head=', '.join(f'{k}: {v}' for k,v in row['response_headers'].items())
        ui.detail('HEADERS',head,'blue','mint',limit=350)
    if row.get('detail') and status in ('BLOCKED','UNRESOLVED','REVIEW'):
        ui.detail('NOTE',row['detail'],'orange','white',limit=200)
    print(flush=True)

def run_search(handle,mode='full',headers=False,allow_http=False,max_sources=None,ui=None,checker=inspect_profile,display=(True,True,True)):
    safe_handle(handle);ui=ui or Palette('never')
    all_entries=load_sources()
    if mode=='quick':
        entries=[item for item in all_entries if item[0] in QUICK_DOMAINS][:16]
    else:entries=all_entries
    if max_sources is not None:entries=entries[:max(1,min(len(entries),int(max_sources)))]
    ui.rule()
    print('  '+ui.rainbow('⚡ USERNAME STORM')+'  '+ui.color(handle,'yellow')+
          ui.color(f'   {len(entries)} PUBLIC SOURCE PATTERNS', 'mint'),flush=True)
    ui.say('  LIVE EVIDENCE  •  Titles / Meta / HTML / Headers  •  No auto-browser','aqua')
    ui.rule('─')
    print(flush=True)
    results=[]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        jobs=[pool.submit(checker,item,handle,headers,allow_http) for item in entries]
        for i,job in enumerate(as_completed(jobs),1):
            try:row=job.result()
            except Exception:row={'status':'UNRESOLVED','site':'unknown','url':'','http':None,'detail':'Provider failed'}
            results.append(row);render(row,i,len(entries),ui,display)
    lookup={key:i for i,key in enumerate(entries)}
    results.sort(key=lambda rec:lookup.get((rec.get('site'),rec.get('template')),9999))
    totals=Counter(r['status'] for r in results)
    ui.rule()
    print('  '+ui.rainbow('🌈 STORM SUMMARY')+'   '+ui.color(f'{len(results)} SOURCES CHECKED','white'),flush=True)
    for label,color in (('POSSIBLE','green'),('PAGE_MENTION','aqua'),('REVIEW','yellow'),
                        ('NOT_FOUND','white'),('BLOCKED','red'),('UNRESOLVED','purple')):
        print('   '+ui.color('▸',color)+' '+ui.color(label.ljust(14),color)+' '+ui.color(str(totals[label]),'white'),flush=True)
    ui.say('  A PAGE MENTION IS NOT PROOF OF ACCOUNT OWNERSHIP.\n','yellow')
    ui.rule('─')
    return results

def save_report(username,items,folder=None):
    folder=Path(folder or (ROOT/'local-reports')); folder.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%fZ')
    name=re.sub(r'[^a-z0-9._-]','_',username.lower())
    root=folder/(f'{name}-{stamp}')
    data={'application':'ALIASTORM CLASSIC NEON','version':VERSION,'username':username,'saved_utc':datetime.now(timezone.utc).isoformat(),
         'warning':'Public results are not identity attribution. A 200 response is not proof of a profile.','results':items}
    jsonpath=Path(str(root)+'.json'); csvpath=Path(str(root)+'.csv'); txtpath=Path(str(root)+'.txt')
    jsonpath.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    fields=['site','url','status','http','title','description','h1','canonical','html_excerpt','raw_html_excerpt','evidence_fields','detail','checked_utc']
    with csvpath.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader()
        for row in items:writer.writerow({**row,'evidence_fields':','.join(row.get('evidence_fields',[]))})
    with txtpath.open('w',encoding='utf-8') as stream:
        stream.write(f'ALIASTORM CLASSIC NEON // PUBLIC USERNAME INTEL // {username}\n')
        stream.write('Public page evidence does not establish account ownership.\n\n')
        for row in items:
            stream.write(f"[{row.get('status')}] {row.get('url')} HTTP={row.get('http')}\n")
            for key in ('title','description','h1','html_excerpt','raw_html_excerpt','detail'):
                if row.get(key):stream.write(f'  {key}: {row[key]}\n')
            stream.write('\n')
    # Add a standalone, offline HTML viewer; JSON/CSV/TXT remain unchanged.
    from report_html import render_report
    htmlpath = Path(str(root) + '.html')
    htmlpath.write_text(render_report(username, items, saved_utc=data['saved_utc']), encoding='utf-8')
    return jsonpath,csvpath,txtpath,htmlpath

def banner(ui):
    """Compact, aligned rainbow frame with a dark backing for readability.

    ASCII wording within box-drawing borders avoids emoji double-width drift.
    The same visible geometry is used with and without terminal colors.
    """
    heading = 'ALIASTORM  //  CLASSIC RAINBOW'
    subtitle = 'USERNAME > PUBLIC SITES > HTML INTEL'
    columns = shutil.get_terminal_size((80, 24)).columns
    inside = min(57, columns - 8)
    if inside < max(len(heading), len(subtitle)):
        print('  ' + ui.rainbow('ALIASTORM') + ui.color('  //  CLASSIC RAINBOW', 'white'), flush=True)
        print('  ' + ui.color('USERNAME', 'yellow') + ui.color(' > ', 'hotpink') +
              ui.color('PUBLIC SITES', 'aqua') + ui.color(' > ', 'hotpink') +
              ui.color('HTML INTEL', 'green'), flush=True)
    else:
        # All frame rows have precisely inside+4 display columns.
        def row(segments):
            total = sum(len(part) for part, _ in segments)
            if total > inside:
                raise ValueError('Rainbow header text exceeds available width')
            content = (ui.panel(' ', 'white') +
                       ''.join(ui.panel(part, tone) for part, tone in segments) +
                       ui.panel(' ' * (inside - total + 1), 'white'))
            print('  ' + ui.color('║', 'hotpink') + content + ui.color('║', 'hotpink'), flush=True)

        frame = '═' * (inside + 2)
        print('  ' + ui.rainbow('╔' + frame + '╗'), flush=True)
        # Rainbow-styled name and white supporting title.
        row([('ALIA', 'hotpink'), ('STORM', 'aqua'),
             ('  //  CLASSIC RAINBOW', 'white')])
        row([('USERNAME', 'yellow'), (' > ', 'hotpink'),
             ('PUBLIC SITES', 'aqua'), (' > ', 'hotpink'),
             ('HTML INTEL', 'green')])
        print('  ' + ui.rainbow('╚' + frame + '╝'), flush=True)
    print('  ' + ui.color('161 original URLs', 'green') +
          '  ' + ui.color('●', 'hotpink') + '  ' +
          ui.color('154 unique patterns', 'green') + '  ' +
          ui.color('●', 'hotpink') + '  ' +
          ui.color('no auto-browser', 'white') + '\n', flush=True)

def demo(ui):
    ui.say('\n  OFFLINE DEMO // FICTIONAL, NO NETWORK REQUESTS','yellow')
    samples=[('https://example.org/u/phantom',200,'<title>phantom profile</title><h1>phantom</h1><p>About phantom the artist</p>'),
             ('https://example.net/u/phantom',200,'<title>Welcome</title><p>Public directory</p>'),
             ('https://example.com/u/phantom',404,'')]
    for i,(url,status,body) in enumerate(samples,1):
        def mock(_):return status,{'content-type':'text/html'},body,url,''
        row=inspect_profile((urlsplit(url).hostname,url.rsplit('/',1)[0]+'/'),'phantom',fetcher=mock)
        render(row,i,len(samples),ui)
    ui.say('  No real websites were visited.\n','yellow')

def ask(prompt,default=''):
    try:return input(prompt).strip() or default
    except (EOFError,KeyboardInterrupt):return ''

def menu(ui):
    while True:
        banner(ui)
        print('  '+ui.color('[1]','hotpink')+' '+ui.color('USERNAME STORM', 'yellow')+'   '+ui.color('154 sites · real HTML intel','aqua'),flush=True)
        print('  '+ui.color('[2]','aqua')+' '+ui.color('SITE INTEL EXTRA','green')+' '+ui.color('headers · robots · metadata','white'),flush=True)
        print('  '+ui.color('[3]','pink')+' '+ui.color('OFFLINE DEMO','pink'),flush=True)
        print('  '+ui.color('[4]','hotpink')+' '+ui.color('HTML RESULTS VIEWER','aqua')+' '+ui.color('choose saved report · open on request','white'),flush=True)
        print('  '+ui.color('[0]','white')+' '+ui.color('EXIT\n','white'),flush=True)
        choice=ask(ui.rainbow('  ALIASTORM')+ui.color(' > ', 'hotpink'))
        if choice in ('0','exit'):return
        if choice=='1':
            h=ask(ui.color('  Username > ','pink'))
            try:safe_handle(h)
            except ValueError as exc:ui.say('  '+str(exc),'red');ask('  Enter to continue...');continue
            mode='quick' if ask('  Search full catalog [Enter] or quick [q]? ','full').lower().startswith('q') else 'full'
            show=ask('  Show response headers for each page? [y/N] ','n').lower().startswith('y')
            titles=not ask('  Include titles in terminal? [Y/n] ','y').lower().startswith('n')
            descriptions=not ask('  Include descriptions? [Y/n] ','y').lower().startswith('n')
            html=not ask('  Include HTML excerpts? [Y/n] ','y').lower().startswith('n')
            rows=run_search(h,mode,headers=show,ui=ui,display=(titles,descriptions,html))
            paths=save_report(h,rows)
            ui.say('  SAVED REAL EVIDENCE → '+', '.join(p.name for p in paths),'green')
            ui.say('  Location: '+str(paths[0].parent),'white')
        elif choice=='2':
            url=ask(ui.color('  Public URL or domain > ','green'))
            if url:
                from site_intel import inspect,show,UI
                try:show(inspect(url),UI('always' if ui.on else 'never'))
                except Exception as exc:ui.say('  Not inspected: '+cut(exc,160),'red')
        elif choice=='3':demo(ui)
        elif choice=='4':
            from viewer_menu import choose_and_open
            choose_and_open(ROOT, ui, ask)
        else:ui.say('  Choose 0, 1, 2, 3 or 4.','yellow')
        ask('  Press Enter to return...')

def main(argv=None):
    parser=argparse.ArgumentParser(description='Username-first public-page HTML + metadata intelligence, inspired by original AliaStorm')
    parser.add_argument('username',nargs='?',help='Public username, like original: python3 aliastorm.py username')
    parser.add_argument('--quick',action='store_true',help='Quick catalog instead of the original full catalog')
    parser.add_argument('--headers',action='store_true',help='Print selected public response headers per result')
    parser.add_argument('--hide-titles',action='store_true',help='Hide titles in terminal (reports still preserve evidence)')
    parser.add_argument('--hide-descriptions',action='store_true',help='Hide descriptions in terminal')
    parser.add_argument('--hide-html',action='store_true',help='Hide matching HTML excerpts in terminal')
    parser.add_argument('--allow-http',action='store_true',help='Allow legacy non-HTTPS catalog entry, otherwise skipped')
    parser.add_argument('--site-intel',metavar='DOMAIN',help='Optional, independent one-domain metadata/robots inspector')
    parser.add_argument('--html-from-json',metavar='SAVED_JSON',help='Make offline HTML from an existing saved scan without rescanning')
    parser.add_argument('--demo',action='store_true',help='Offline fictional demonstration')
    parser.add_argument('--max-sources',type=int,help='Stop after this many sources (testing or focused checks)')
    parser.add_argument('--color',choices=('auto','always','never'),default='auto')
    args=parser.parse_args(argv);ui=Palette(args.color)
    if args.html_from_json:
        from report_html import render_report
        try:
            saved = Path(args.html_from_json).expanduser()
            data = json.loads(saved.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or not isinstance(data.get('results'), list):
                raise ValueError('Expected an AliaStorm JSON report with a results array')
            target = saved.with_suffix('.html')
            target.write_text(render_report(data.get('username') or 'Unknown username', data['results'],
                                           saved_utc=data.get('saved_utc')), encoding='utf-8')
        except (OSError, ValueError, TypeError, UnicodeError) as exc:
            ui.say('  HTML report could not be created: ' + cut(exc, 120), 'red')
            return 2
        ui.say('  STORM REBORN HTML READY: ' + str(target), 'green')
        ui.say('  Open the .html file yourself. No browser was launched.', 'aqua')
        return 0
    if args.demo:banner(ui);demo(ui);return 0
    if args.site_intel:
        banner(ui)
        from site_intel import inspect,show,UI
        try:show(inspect(args.site_intel),UI('always' if ui.on else 'never'))
        except Exception as exc:ui.say('  Inspection failed: '+cut(exc),'red');return 2
        return 0
    if args.username:
        banner(ui)
        try:records=run_search(args.username,'quick' if args.quick else 'full',args.headers,args.allow_http,args.max_sources,ui,display=(not args.hide_titles,not args.hide_descriptions,not args.hide_html))
        except ValueError as exc:ui.say(str(exc),'red');return 2
        paths=save_report(args.username,records)
        ui.say('  Local evidence saved: '+', '.join(p.name for p in paths),'green')
        return 0
    menu(ui);return 0

if __name__=='__main__':
    raise SystemExit(main())
