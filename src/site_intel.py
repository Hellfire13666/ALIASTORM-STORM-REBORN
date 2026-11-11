#!/usr/bin/env python3
"""Optional, one-domain public headers, robots and metadata inspector."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import ipaddress
import json
import os
import shutil
import textwrap
from pathlib import Path
import re
import socket
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

VERSION = '2.1.1'
TIMEOUT = 8
MAX_BODY = 160 * 1024
MAX_REDIRECTS = 3
USER_AGENT = 'AliaStormNeonIntel/2.0 (public-metadata-inspection; manual single-site review)'
C = {'reset':'\033[0m',
     'pink':'\033[1;38;2;255;98;224m', 'violet':'\033[1;38;2;215;150;255m',
     'cyan':'\033[1;38;2;69;248;255m', 'green':'\033[1;38;2;118;255;88m',
     'yellow':'\033[1;38;2;255;246;65m', 'red':'\033[1;38;2;255;105;119m',
     'dim':'\033[1;38;2;217;229;249m', 'bold':'\033[1m',
     'orange':'\033[1;38;2;255;180;78m', 'aqua':'\033[1;38;2;31;237;255m',
     'mint':'\033[1;38;2;145;255;196m', 'white':'\033[1;38;2;255;255;255m'}

class UI:
    def __init__(self,color='auto'):
        self.on = color == 'always' or (color == 'auto' and sys.stdout.isatty() and not os.environ.get('NO_COLOR'))
    def ink(self,text,color):
        return f'{C[color]}{text}{C["reset"]}' if self.on else str(text)
    def rainbow(self,text):
        shades=('pink','violet','cyan','aqua','green','yellow','orange')
        return ''.join(self.ink(ch,shades[i%len(shades)]) if not ch.isspace() else ch
                       for i,ch in enumerate(str(text)))
    def print(self,text,color='cyan'):
        print(self.ink(text,color))
    def field(self,label,value,accent='cyan'):
        width=max(32,min(112,shutil.get_terminal_size((98,24)).columns-1)-21)
        chunks=textwrap.wrap(clean(value,360),width=width,break_long_words=True) or ['']
        print('    '+self.ink(label.ljust(16),accent)+self.ink(chunks[0],'white'))
        for chunk in chunks[1:]:print(' '*20+self.ink(chunk,'white'))

def banner(ui):
    ui.print('\n╔════════════════════════════════════════════════════╗', 'violet')
    ui.print('║    ⚡ ALIASTORM // NEON INTEL     GLITCHBYTE       ║', 'pink')
    ui.print('║      HEADERS • ROBOTS • METADATA • EVIDENCE         ║', 'cyan')
    ui.print('╚════════════════════════════════════════════════════╝', 'violet')
    ui.print('  SINGLE PUBLIC SITE  •  READ ONLY  •  NO BROWSER\n', 'green')

def clean(value,limit=220):
    value=' '.join(str(value or '').split())
    return value[:limit-1]+'…' if len(value)>limit else value

def normalize_url(value):
    value=value.strip()
    if not value or any(ch.isspace() for ch in value):
        raise ValueError('Enter one public HTTP(S) URL with no spaces.')
    if '://' not in value:
        value='https://'+value
    u=urlparse(value)
    if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:
        raise ValueError('Only public HTTP(S) URLs without credentials are supported.')
    if u.port not in (None,80,443):
        raise ValueError('Only standard HTTP(S) ports 80 and 443 are supported.')
    hostname=u.hostname.lower().rstrip('.')
    if hostname == 'localhost' or hostname.endswith(('.local','.internal','.test','.localhost','.invalid')):
        raise ValueError('Private/local hosts are outside the public-site inspector.')
    if hostname.find('.') < 1:
        raise ValueError('Enter a public domain name (for example example.org).')
    try:
        parsed_ip=ipaddress.ip_address(hostname)
    except ValueError:
        parsed_ip=None
    if parsed_ip is not None:
        raise ValueError('Use public domain names, not raw IP addresses.')
    if not re.fullmatch(r'[a-z0-9.-]+',hostname):
        raise ValueError('The domain contains unsupported characters.')
    # Prefer secure public-page requests even when the user typed http://.
    # Preserve explicit port 443; drop port 80 when upgrading to HTTPS.
    if u.scheme == 'http':
        netloc=hostname if u.port in (None,80) else f'{hostname}:443'
        scheme='https'
    else:
        netloc=u.netloc.lower();scheme=u.scheme
    return urlunparse((scheme,netloc,u.path or '/', '',u.query,''))

def require_public_dns(hostname):
    # Protect against accidental local network queries. A network boundary is not guaranteed
    # against DNS rebinding, so use only on sites you intend to inspect.
    results=socket.getaddrinfo(hostname,None,type=socket.SOCK_STREAM)
    if not results:
        raise ValueError('No address found for the requested domain.')
    for item in results:
        ip=ipaddress.ip_address(item[4][0])
        if not ip.is_global:
            raise ValueError('Domain resolved to a private or non-public address.')

class RedirectRefused(Exception):
    """Explicit HTTP response when an ordinary redirect cannot be followed."""
    def __init__(self, reason, code, source_url, target_url, response_headers):
        super().__init__(reason)
        self.code = code
        self.source_url = source_url
        self.target_url = target_url
        self.response_headers = dict(response_headers.items())


def same_website(a,b):
    """Only exact host or its www variant; never unrelated or sibling subdomains."""
    apex_a=a[4:] if a.startswith('www.') else a
    apex_b=b[4:] if b.startswith('www.') else b
    return a == b or (apex_a == apex_b and (a.startswith('www.') or b.startswith('www.')))


class BoundedRedirects(HTTPRedirectHandler):
    def __init__(self,host,max_redirects=MAX_REDIRECTS):
        super().__init__()
        self.host=host
        self.max_redirects=max_redirects
        self.last_url=''
        self.hops=[]

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        source=urlparse(req.full_url)
        target=urlparse(newurl)
        reason=''
        try:
            valid_port=target.port in (None,80,443)
        except ValueError:
            valid_port=False
        if target.scheme not in ('http','https'):
            reason='Redirect refused: non-web destination'
        elif not target.hostname or target.username or target.password or not valid_port:
            reason='Redirect refused: invalid destination or nonstandard port'
        elif source.scheme=='https' and target.scheme!='https':
            reason='Redirect refused: HTTPS downgrade'
        elif not same_website(self.host,target.hostname.lower()):
            reason='Redirect refused: destination is outside this website'
        elif len(self.hops)>=self.max_redirects:
            reason='Redirect refused: three-hop safety limit reached'
        else:
            try:
                # Reject local/private destinations on every redirect, including a www switch.
                require_public_dns(target.hostname.lower())
            except (OSError,ValueError) as exc:
                reason='Redirect refused: destination DNS is not public or is unavailable'
        if reason:
            raise RedirectRefused(reason,code,req.full_url,newurl,headers)
        approved=super().redirect_request(req,fp,code,msg,headers,newurl)
        if approved is None:
            raise RedirectRefused('Redirect refused by HTTP client',code,req.full_url,newurl,headers)
        self.hops.append((req.full_url,newurl,code))
        self.last_url=newurl
        return approved

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title=[];self.in_title=False;self.meta={};self.canonical='';self.links=0
        self.h1=[];self.in_h1=False;self.robots_meta='';self.text_chunks=[]
        self.skip_depth=0
    def handle_starttag(self,tag,attrs):
        tag=tag.lower(); a=dict(attrs)
        if tag in ('script','style','noscript'):
            self.skip_depth+=1
        if tag=='title':self.in_title=True
        if tag=='h1':self.in_h1=True
        if tag=='a' and a.get('href'):self.links+=1
        if tag=='link' and 'canonical' in (a.get('rel') or '').lower().split():self.canonical=a.get('href') or ''
        if tag=='meta':
            k=(a.get('name') or a.get('property') or '').lower()
            if k in ('description','og:title','og:description','og:image','twitter:card','generator','robots'):
                self.meta.setdefault(k,clean(a.get('content',''),300))
    def handle_endtag(self,tag):
        tag=tag.lower()
        if tag in ('script','style','noscript') and self.skip_depth:self.skip_depth-=1
        if tag=='title':self.in_title=False
        if tag=='h1':self.in_h1=False
    def handle_data(self,data):
        if self.in_title:self.title.append(data)
        if self.in_h1:self.h1.append(data)
        if not self.skip_depth and len(self.text_chunks)<1000:
            t=clean(data,150)
            if t:self.text_chunks.append(t)
    def summary(self):
        return {'title':clean(' '.join(self.title),220),'description':self.meta.get('description',''),
                'h1':clean(' '.join(self.h1),220),'canonical':self.canonical,
                'meta':self.meta,'public_links_on_page':self.links,
                'visible_text_sample':clean(' '.join(self.text_chunks),360)}

def fetch(url,host,read_body=True,timeout=TIMEOUT):
    """One bounded public resource, optional safe redirects; no retry or crawl."""
    if urlparse(url).hostname != host:
        raise ValueError('Requested URL host does not match the approved site')
    req=Request(url,headers={'User-Agent':USER_AGENT,'Accept':'text/html,text/plain,application/xml,*/*;q=0.5'})
    guard=BoundedRedirects(host)
    opener=build_opener(guard)
    try:
        with opener.open(req,timeout=timeout) as resp:
            status=resp.status
            headers=dict(resp.headers.items())
            final=resp.geturl()
            if not same_website(host,urlparse(final).hostname or ''):
                raise ValueError('Off-website redirect blocked')
            body=resp.read(MAX_BODY+1) if read_body else b''
            return {'url':url,'final_url':final,'status':status,'headers':headers,'truncated':len(body)>MAX_BODY,
                    'body':body[:MAX_BODY].decode('utf-8','replace'),'error':'',
                    'redirect_target':'','redirects':len(guard.hops)}
    except RedirectRefused as e:
        return {'url':url,'final_url':e.source_url,'status':e.code,'headers':e.response_headers,
                'body':'','truncated':False,'error':str(e),'redirect_target':e.target_url,
                'redirects':len(guard.hops)}
    except HTTPError as e:
        return {'url':url,'final_url':e.geturl() or guard.last_url or url,'status':e.code,
                'headers':dict(e.headers.items()),'body':'','truncated':False,
                'error':f'HTTP {e.code}','redirect_target':'','redirects':len(guard.hops)}
    except (URLError,OSError,TimeoutError,ValueError) as e:
        return {'url':url,'final_url':guard.last_url or url,'status':None,
                'headers':{},'body':'','truncated':False,'error':clean(str(e),180),
                'redirect_target':'','redirects':len(guard.hops)}

def header_subset(h):
    names=('content-type','content-length','server','x-powered-by','cache-control','etag','last-modified',
           'strict-transport-security','content-security-policy','x-content-type-options',
           'x-frame-options','referrer-policy','permissions-policy','access-control-allow-origin',
           'location','link','x-robots-tag')
    low={k.lower():v for k,v in h.items()}
    return {key:clean(low[key],300) for key in names if key in low}

def robots_summary(text):
    lines=[]
    for row in text.splitlines():
        stripped=row.strip()
        if not stripped or stripped.startswith('#'):continue
        if ':' not in stripped:continue
        key=stripped.split(':',1)[0].lower()
        if key in ('user-agent','allow','disallow','crawl-delay','sitemap'):
            lines.append(clean(stripped,180))
        if len(lines)>=28:break
    return lines

def security_summary(text):
    keys={'contact','expires','encryption','acknowledgments','preferred-languages','canonical','policy','hiring'}
    return [clean(row.strip(),180) for row in text.splitlines() if ':' in row and row.split(':',1)[0].strip().lower() in keys][:12]

def inspect(url, fetcher=fetch, resolve=True):
    supplied=url.strip()
    url=normalize_url(url);parsed=urlparse(url);host=parsed.hostname
    if resolve:require_public_dns(host)
    page=fetcher(url,host)
    # Honor a verified same-website final URL, so robots/security belong to the
    # website actually inspected. On a blocked redirect, retain the original site.
    landing=page.get('final_url') or url
    parsed_landing=urlparse(landing)
    if not same_website(host,parsed_landing.hostname or ''):
        landing=url
        parsed_landing=parsed
    root=f'{parsed_landing.scheme}://{parsed_landing.netloc}'
    calls={'robots':root+'/robots.txt',
           'security':root+'/.well-known/security.txt'}
    raw={'page':page}
    for key,target in calls.items():
        raw[key]=fetcher(target,parsed_landing.hostname)
    parsed_meta={}
    if page['body'] and ('html' in next((v.lower() for k,v in page['headers'].items() if k.lower()=='content-type'),'') or '<html' in page['body'][:300].lower()):
        p=PageParser();p.feed(page['body']);parsed_meta=p.summary()
    robots=raw['robots'];security=raw['security']
    directives=robots_summary(robots['body']) if robots['status']==200 else []
    total_directives=sum(1 for row in robots['body'].splitlines() if row.strip() and not row.lstrip().startswith('#')
                         and row.partition(':')[0].strip().lower() in ('user-agent','allow','disallow','crawl-delay','sitemap')) if robots['status']==200 else 0
    return {'version':VERSION,'checked_utc':datetime.now(timezone.utc).isoformat(),
          'supplied_url':supplied,'requested_url':url,'host':host,
          'page':{'url':page['final_url'],'http':page['status'],'error':page['error'],
                  'redirect_target':page.get('redirect_target',''),
                  'redirects':page.get('redirects',0),
                  'response_headers':header_subset(page['headers']),'metadata':parsed_meta,'truncated':page['truncated']},
          'robots':{'url':robots['url'],'final_url':robots.get('final_url',robots['url']),
                    'http':robots['status'],'error':robots['error'],
                    'redirect_target':robots.get('redirect_target',''),
                    'total_directives':total_directives,'directives':directives},
          'security_txt':{'url':security['url'],'final_url':security.get('final_url',security['url']),
                    'http':security['status'],'error':security['error'],
                    'redirect_target':security.get('redirect_target',''),
                    'fields':security_summary(security['body']) if security['status']==200 else []},
          'notes':['Public HTTP observations at one moment; header presence alone is not a security audit.',
                   'robots.txt rules apply to their named User-agent group; no general access conclusions.',
                   'Requests inspect three public resources, with at most three redirects per resource.',
                   'A blocked redirect is reported but never bypassed.']}

def show(data,ui):
    ui.print('\n  '+ui.rainbow('⚡ ALIASTORM // PUBLIC SITE INTEL'),'white')
    ui.print('  '+data['requested_url'],'aqua')
    p=data['page']
    def section(title,tone):
        ui.print('\n  ━━━ '+title+' ━━━',tone)
    section('[01] RESPONSE HEADERS','pink')
    if data.get('supplied_url') and data['supplied_url'].lower().startswith('http://'):
        ui.field('HTTPS FIRST','HTTP input upgraded to HTTPS','green')
    ui.field('REQUESTED',data['requested_url'],'aqua')
    ui.field('HTTP STATUS',p['http'] if p['http'] is not None else 'NO RESPONSE','yellow')
    if p['url'] and p['url'] != data['requested_url']:
        ui.field('FINAL URL',p['url'],'mint')
    if p.get('redirect_target'):
        ui.field('REDIRECT TO',p['redirect_target'],'orange')
    if p['error']:ui.field('NOTE',p['error'],'orange')
    for k,v in p['response_headers'].items():ui.field(k.upper(),v,'cyan')
    section('[02] PAGE METADATA','aqua')
    m=p['metadata']
    for k in ('title','description','h1','canonical','public_links_on_page','visible_text_sample'):
        if k in m:ui.field(k.upper(),m[k],'pink')
    for k,v in m.get('meta',{}).items():ui.field(k.upper(),v,'violet')
    section('[03] ROBOTS.TXT','green')
    r=data['robots']
    ui.field('URL',r['url'],'aqua')
    ui.field('HTTP',r['http'] if r['http'] is not None else 'NO RESPONSE','yellow')
    if r.get('final_url') and r['final_url']!=r['url']:ui.field('FINAL URL',r['final_url'],'mint')
    if r.get('redirect_target'):ui.field('REDIRECT TO',r['redirect_target'],'orange')
    if r.get('error'):ui.field('NOTE',r['error'],'orange')
    for line in r['directives']:
        kind='USER-AGENT' if line.lower().startswith('user-agent:') else 'RULE'
        ui.field(kind,line,'violet' if kind=='USER-AGENT' else 'green')
    if r.get('total_directives',len(r['directives']))>len(r['directives']):
        ui.field('DISPLAY LIMIT',f"{len(r['directives'])} of {r['total_directives']} directives shown",'yellow')
    ui.print('    Rules belong to named User-agent groups; not a blanket ban or permission.','dim')
    if not r['directives']:ui.print('    No readable directives (not proof of permission).','dim')
    section('[04] SECURITY.TXT','orange')
    sec=data['security_txt']
    ui.field('URL',sec['url'],'aqua')
    ui.field('HTTP',sec['http'] if sec['http'] is not None else 'NO RESPONSE','yellow')
    if sec.get('final_url') and sec['final_url']!=sec['url']:ui.field('FINAL URL',sec['final_url'],'mint')
    if sec.get('redirect_target'):ui.field('REDIRECT TO',sec['redirect_target'],'orange')
    if sec.get('error'):ui.field('NOTE',sec['error'],'orange')
    for line in sec['fields']:ui.field('FIELD',line,'orange')
    if not sec['fields']:ui.print('    No readable security contact fields (not proof the file is absent).','dim')
    ui.print('\n  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━','violet')
    ui.print('  Three public resources; bounded redirects • no crawling • no auto-browser','yellow')

def save(data,folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    stem=re.sub(r'[^a-z0-9.-]','-',data['host'].lower())[:60]+'-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%SZ')
    p=folder/(stem+'.json')
    n=1
    while p.exists():
        p=folder/(stem+f'-{n}.json');n+=1
    p.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return p

def demo():
    return {'version':VERSION,'requested_url':'https://example.org/','host':'example.org',
     'page':{'url':'https://example.org/','http':200,'error':'','response_headers':{'content-type':'text/html','server':'ExampleServer','x-content-type-options':'nosniff'},
             'metadata':{'title':'Example Site','description':'Offline fictional preview','h1':'Example','canonical':'https://example.org/','public_links_on_page':2,'visible_text_sample':'Illustrative site text only'},'truncated':False},
     'robots':{'url':'https://example.org/robots.txt','http':200,'error':'','directives':['User-agent: *','Disallow: /private/','Sitemap: https://example.org/sitemap.xml']},
     'security_txt':{'url':'https://example.org/.well-known/security.txt','http':200,'error':'','fields':['Contact: https://example.org/security','Expires: 2099-01-01T00:00:00Z']}}

