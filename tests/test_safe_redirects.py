"""Offline tests for the optional one-site inspection reliability patch."""
import io
from contextlib import redirect_stdout
from email.message import Message
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.request import Request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import site_intel as intel


def headers(**kw):
    msg=Message()
    for k,v in kw.items(): msg[k.replace('_','-')]=v
    return msg


class RedirectTests(unittest.TestCase):
    def test_url_http_input_prefers_https(self):
        self.assertEqual(intel.normalize_url('http://facebook.com'), 'https://facebook.com/')
        self.assertEqual(intel.normalize_url('http://example.org:80/sub?q=a'), 'https://example.org/sub?q=a')
        self.assertEqual(intel.normalize_url('https://example.org/sub'), 'https://example.org/sub')

    def test_allow_http_to_https_with_www_switch(self):
        g=intel.BoundedRedirects('facebook.com')
        with patch.object(intel,'require_public_dns') as dns:
            r=g.redirect_request(Request('http://facebook.com/'),None,301,'Moved',headers(),
                                 'https://www.facebook.com/')
        self.assertEqual(r.full_url,'https://www.facebook.com/')
        self.assertEqual(len(g.hops),1)
        dns.assert_called_once_with('www.facebook.com')

    def test_reject_https_downgrade(self):
        g=intel.BoundedRedirects('facebook.com')
        with self.assertRaises(intel.RedirectRefused) as caught:
            g.redirect_request(Request('https://facebook.com/'),None,302,'Found',headers(Location='http://facebook.com/'),
                               'http://facebook.com/')
        self.assertIn('downgrade',str(caught.exception).lower())
        self.assertEqual(caught.exception.code,302)

    def test_refuse_different_or_sibling_host_and_non_web(self):
        for target in ('https://facebook.com.evil.net/', 'https://login.facebook.com/',
                       'https://evil.net/', 'file:///etc/passwd',
                       'https://www.facebook.com:8080/'):
            with self.subTest(target=target):
                g=intel.BoundedRedirects('facebook.com')
                with self.assertRaises(intel.RedirectRefused):
                    g.redirect_request(Request('https://facebook.com/'),None,302,'Found',headers(),target)

    def test_refuse_nonpublic_dns_even_at_www(self):
        g=intel.BoundedRedirects('facebook.com')
        with patch.object(intel,'require_public_dns',side_effect=ValueError('private')):
            with self.assertRaises(intel.RedirectRefused) as c:
                g.redirect_request(Request('https://facebook.com/'),None,301,'Moved',headers(),
                                   'https://www.facebook.com/')
        self.assertIn('DNS',str(c.exception))

    def test_3_redirect_limit(self):
        g=intel.BoundedRedirects('example.com')
        with patch.object(intel,'require_public_dns'):
            a=Request('https://example.com/')
            for i in range(3):
                a=g.redirect_request(a,None,302,'Found',headers(),f'https://example.com/{i}')
            with self.assertRaises(intel.RedirectRefused) as c:
                g.redirect_request(a,None,302,'Found',headers(),'https://example.com/4')
        self.assertIn('three-hop',str(c.exception))

    def test_fetch_reports_blocked_redirect_http_code_and_location(self):
        target='https://other.example.net/'
        class FakeOpener:
            def __init__(self,guard):self.guard=guard
            def open(self,req,timeout):
                self.guard.redirect_request(req,None,302,'Found',headers(Location=target),target)
        with patch.object(intel,'build_opener',side_effect=lambda guard:FakeOpener(guard)):
            report=intel.fetch('https://facebook.com/','facebook.com')
        self.assertEqual(report['status'],302)
        self.assertEqual(report['final_url'],'https://facebook.com/')
        self.assertEqual(report['redirect_target'],target)
        self.assertIn('outside',report['error'])
        self.assertEqual(report['headers']['Location'],target)

    def test_inspect_uses_effective_same_site_https_root_and_keeps_3_resources(self):
        calls=[]
        def fake_fetch(url,host):
            calls.append((url,host))
            final='https://www.facebook.com/' if url=='https://facebook.com/' else url
            body='User-agent: GPTBot\nDisallow: /\nUser-agent: Googlebot\nAllow: /' if 'robots.txt' in url else '<title>Public Page</title>'
            return {'url':url,'final_url':final,'status':200,'headers':{'content-type':'text/html'},
                    'body':body,'truncated':False,'error':'','redirect_target':'',
                    'redirects':int(final!=url)}
        data=intel.inspect('http://facebook.com',fetcher=fake_fetch,resolve=False)
        self.assertEqual(len(calls),3)
        self.assertEqual(calls[0],('https://facebook.com/','facebook.com'))
        self.assertEqual(calls[1],('https://www.facebook.com/robots.txt','www.facebook.com'))
        self.assertEqual(calls[2],('https://www.facebook.com/.well-known/security.txt','www.facebook.com'))
        self.assertEqual(data['page']['url'],'https://www.facebook.com/')
        self.assertEqual(data['robots']['total_directives'],4)
        with redirect_stdout(io.StringIO()) as captured:
            intel.show(data,intel.UI('never'))
        output=captured.getvalue()
        self.assertIn('HTTPS FIRST',output)
        self.assertIn('FINAL URL',output)
        self.assertIn('User-agent: GPTBot',output)
        self.assertIn('not a blanket ban',output)

    def test_robots_display_explicit_limit_for_many_groups(self):
        lines=[]
        for i in range(28):lines += [f'User-agent: Bot{i}', 'Disallow: /']
        body='\n'.join(lines)
        def fake_fetch(url,host):
            return {'url':url,'final_url':url,'status':200,
                    'headers':{'content-type':'text/plain'},'body':body if 'robots.txt' in url else '',
                    'truncated':False,'error':''}
        data=intel.inspect('example.org',fetcher=fake_fetch,resolve=False)
        self.assertEqual(data['robots']['total_directives'],56)
        self.assertEqual(len(data['robots']['directives']),28)
        with redirect_stdout(io.StringIO()) as captured:intel.show(data,intel.UI('never'))
        self.assertIn('28 of 56 directives shown',captured.getvalue())


if __name__=='__main__':unittest.main()
