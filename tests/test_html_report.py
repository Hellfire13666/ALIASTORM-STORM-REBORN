"""Self-contained HTML export tests; all fictional, no live HTTP requests."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import aliastorm as a
from report_html import render_report


class ReportViewerTests(unittest.TestCase):
    def setUp(self):
        self.record = {
            'site':'example.org', 'url':'https://example.org/fictional',
            'status':'POSSIBLE', 'http':200, 'title':'Fictional & "Example"',
            'description':'Sample artist profile', 'h1':'Demo Artist',
            'html_excerpt':'Fictional visible evidence',
            'raw_html_excerpt':'<script>alert("BAD")</script>',
            'response_headers':{'content-type':'text/html'},
            'evidence_fields':['TITLE','VISIBLE_HTML'], 'checked_utc':'2026-01-01T00:00:00Z',
        }

    def test_html_has_embedded_artwork_no_network_dependencies(self):
        doc=render_report('demo',[self.record],preview=True)
        self.assertIn('data:image/webp;base64,',doc)
        self.assertIn('STORM REBORN',doc)
        self.assertNotIn('<script src=',doc)
        self.assertNotIn('<link rel="stylesheet" href=',doc)
        self.assertIn('These sample records are fictional',doc)

    def test_untrusted_html_stays_escaped(self):
        doc=render_report('<img src=x onerror=alert(2)>',[self.record])
        self.assertNotIn('<script>alert("BAD")</script>',doc)
        self.assertIn('&lt;script&gt;alert(&quot;BAD&quot;)&lt;/script&gt;',doc)
        self.assertIn('&lt;img src=x onerror=alert(2)&gt;',doc)
        self.assertIn('Fictional &amp; &quot;Example&quot;',doc)

    def test_save_report_fallback_and_json_csv_txt_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            paths=a.save_report('DemoUser',[self.record],d)
            self.assertEqual([p.suffix for p in paths],['.json','.csv','.txt','.html'])
            self.assertTrue(all(p.exists() for p in paths))
            self.assertIn('STORM REBORN',paths[3].read_text())
            self.assertEqual(json.loads(paths[0].read_text())['results'][0]['title'],self.record['title'])
            self.assertIn('Fictional',paths[2].read_text())

    def test_convert_existing_saved_json_no_rescan(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'archive-report.json'
            p.write_text(json.dumps({'username':'ArchiveUser','saved_utc':'2026-02-01','results':[self.record]}))
            before=p.read_bytes()
            with redirect_stdout(io.StringIO()) as output:
                code=a.main(['--html-from-json',str(p),'--color','never'])
            self.assertEqual(code,0)
            self.assertEqual(p.read_bytes(),before)
            self.assertTrue(p.with_suffix('.html').exists())
            self.assertIn('ArchiveUser',p.with_suffix('.html').read_text())
            self.assertIn('No browser was launched',output.getvalue())

    def test_filter_status_whitelist(self):
        r=dict(self.record,status='INJECTED',url='https://example.org/a')
        doc=render_report('Demo',[r])
        self.assertIn('data-status="UNRESOLVED"',doc)
        self.assertNotIn('data-status="INJECTED"',doc)

    def test_invalid_archive_error(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'invalid.json'
            path.write_text('{"results":{}}')
            with redirect_stdout(io.StringIO()):
                self.assertEqual(a.main(['--html-from-json',str(path),'--color','never']),2)
            self.assertFalse(path.with_suffix('.html').exists())

if __name__=='__main__': unittest.main()
