import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import aliastorm as a
import site_intel as intel

class ClassicTests(unittest.TestCase):
    def test_exact_legacy_catalog_161_lines(self):
        lines=[x for x in a.CATALOG.read_text().splitlines() if x.strip()]
        self.assertEqual(len(lines),161)
        self.assertEqual(len(a.load_sources()),154)
    def test_url_patterns(self):
        self.assertEqual(a.profile_url('https://www.tiktok.com/@','rosie'),'https://www.tiktok.com/@rosie')
        self.assertEqual(a.profile_url('https://www.reddit.com/user/','rosie'),'https://www.reddit.com/user/rosie')
        self.assertEqual(a.profile_url('https://www.yelp.com/user_details?userid=','rosie'),'https://www.yelp.com/user_details?userid=rosie')
        self.assertEqual(a.profile_url('https://pinboard.in/u:','rosie'),'https://pinboard.in/u:rosie')
    def test_username_validation(self):
        for value in ('https://target.invalid/','../bad','*','bad name','@admin'):
            with self.assertRaises(ValueError):a.safe_handle(value)
        self.assertEqual(a.safe_handle('rosie.glitch'), 'rosie.glitch')
    def test_html_evidence(self):
        page='<title>rosie on gallery</title><meta name="description" content="Rosie artist">' \
             '<h1>rosie</h1><script>fake_seen_here</script><p>Hello rosie from HTML</p>'
        def fetch(_):return 200,{'content-type':'text/html','server':'Example'},page,'https://demo.org/rosie',''
        result=a.inspect_profile(('demo.org','https://demo.org/'),'rosie',show_headers=True,fetcher=fetch)
        self.assertEqual(result['status'],'POSSIBLE')
        self.assertEqual(result['title'],'rosie on gallery')
        self.assertEqual(result['description'],'Rosie artist')
        self.assertIn('VISIBLE_HTML',result['evidence_fields'])
        self.assertEqual(result['response_headers']['server'],'Example')
        self.assertNotIn('fake_seen_here',result['html_excerpt'])
        self.assertIn('RAW_HTML',result['evidence_fields'])
    def test_raw_html_attribute_evidence_not_identity(self):
        def fetch(_):return 200,{'content-type':'text/html'},'<title>Directory</title><a href="/profile/rosie">Link</a>','https://demo.org/rosie',''
        result=a.inspect_profile(('demo.org','https://demo.org/'),'rosie',fetcher=fetch)
        self.assertEqual(result['status'],'PAGE_MENTION')
        self.assertIn('RAW_HTML',result['evidence_fields'])
        self.assertTrue(result['raw_html_excerpt'])
    def test_200_not_proof(self):
        def fetch(_):return 200,{'content-type':'text/html'},'<title>Welcome home</title><p>Generic content</p>','https://demo.org/rosie',''
        result=a.inspect_profile(('demo.org','https://demo.org/'),'rosie',fetcher=fetch)
        self.assertEqual(result['status'],'REVIEW')
        self.assertFalse(result['evidence_fields'])
    def test_html_only_distinct(self):
        def fetch(_):return 200,{'content-type':'text/html'},'<title>Directory</title><p>Welcome rosie</p>','https://demo.org/rosie',''
        result=a.inspect_profile(('demo.org','https://demo.org/'),'rosie',fetcher=fetch)
        self.assertEqual(result['status'],'PAGE_MENTION')
    def test_http_404_and_blocked(self):
        for status,expected in ((404,'NOT_FOUND'),(429,'BLOCKED'),(403,'BLOCKED')):
            def fetch(_):return status,{},'', 'https://demo.org/rosie',f'HTTP {status}'
            result=a.inspect_profile(('demo.org','https://demo.org/'),'rosie',fetcher=fetch)
            self.assertEqual(result['status'],expected)
    def test_preserve_insecure_source_but_skip(self):
        result=a.inspect_profile(('www.money-talk.org','http://www.money-talk.org/profile.php?mode=viewprofile&u='),'rosie')
        self.assertEqual(result['status'],'UNRESOLVED')
        self.assertIn('skipped',result['detail'])
    def test_export_real_evidence_and_dot_handle(self):
        with tempfile.TemporaryDirectory() as d:
            row={'site':'demo.org','url':'https://demo.org/rosie.glitch','status':'POSSIBLE','http':200,'title':'rosie.glitch artist','description':'Original description','h1':'rosie.glitch','html_excerpt':'hello rosie.glitch','evidence_fields':['TITLE'],'detail':'','checked_utc':'2026-11-11'}
            files=a.save_report('rosie.glitch',[row],d)
            self.assertEqual(len(files),4)
            for f in files:self.assertTrue(f.exists(),f)
            data=json.loads(files[0].read_text())
            self.assertEqual(data['results'][0]['title'],'rosie.glitch artist')
            self.assertTrue('rosie.glitch-' in files[0].name)
    def test_three_public_gets_optional_extra(self):
        seen=[]
        def fetch(url,host):
            seen.append(url)
            return {'url':url,'final_url':url,'status':200,'headers':{'content-type':'text/html'},'body':'<title>Test</title>' if url.endswith('/') else 'User-agent: *\nDisallow: /private/','truncated':False,'error':''}
        data=intel.inspect('example.org',fetcher=fetch,resolve=False)
        self.assertEqual(len(seen),3)
        self.assertIn('robots.txt',seen[1])
        self.assertEqual(data['page']['metadata']['title'],'Test')
    def test_no_unauthorized_local_site(self):
        for url in ('localhost','http://127.0.0.1','file:///etc/passwd','example.local'):
            with self.assertRaises(ValueError):intel.normalize_url(url)
    def test_full_mode_limit_and_real_time_output(self):
        def checker(item,handle,show_headers,allow_http):
            return {'site':item[0],'template':item[1],'url':a.profile_url(item[1],handle),'http':404,'status':'NOT_FOUND','title':'','description':'','h1':'','html_excerpt':'','evidence_fields':[],'response_headers':{},'detail':'','checked_utc':'x'}
        with redirect_stdout(io.StringIO()) as capture:
            rows=a.run_search('rosie','full',max_sources=4,ui=a.Palette('never'),checker=checker)
        self.assertEqual(len(rows),4)
        self.assertIn('[001/004]',capture.getvalue())


    def test_rainbow_palette_without_ansi_fallback(self):
        ui=a.Palette('never')
        self.assertEqual(ui.rainbow('ALIASTORM'), 'ALIASTORM')
        self.assertEqual(ui.color('signal','green'), 'signal')
    def test_rainbow_palette_with_ansi(self):
        ui=a.Palette('always')
        self.assertIn('\x1b[',ui.rainbow('ALIASTORM'))
        self.assertIn('\x1b[',ui.color('signal','green'))
    def test_display_preserves_fields_and_wraps(self):
        row={'site':'example.org','url':'https://example.org/user/rosie','http':200,'status':'POSSIBLE',
             'title':'rosie profile','description':'rosie artist', 'h1':'rosie',
             'evidence_fields':['TITLE','VISIBLE_HTML'],
             'html_excerpt':'rosie public profile','raw_html_excerpt':'<title>rosie</title>',
             'response_headers':{'content-type':'text/html'},'detail':''}
        with redirect_stdout(io.StringIO()) as output:
            a.render(row,1,154,a.Palette('never'))
        text=output.getvalue()
        for key in ('[001/154]','POSSIBLE','HTTP','SOURCE','EVIDENCE','TITLE','DESCRIPTION','VISIBLE HTML','RAW HTML','HEADERS'):
            self.assertIn(key,text)

if __name__ == '__main__':unittest.main()
