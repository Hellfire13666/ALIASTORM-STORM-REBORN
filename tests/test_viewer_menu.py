"""No-browser, no-network tests for the explicit terminal menu HTML viewer."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import aliastorm as a
import viewer_menu as v


class ViewerMenuTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.downloads = self.home/'Downloads'
        self.root = self.downloads/'ALIASTORM-STORM-REBORN-VIEWER-MENU'
        self.newdir = self.root/'local-reports'
        self.old = self.downloads/'ALIASTORM-STORM-REBORN-SAFE-REDIRECTS'/'local-reports'
        self.old.mkdir(parents=True)
        self.newdir.mkdir(parents=True)
        self.first = self.old/'rosie-test.html'
        self.second = self.newdir/'glitchbyte-test.html'
        self.first.write_text('<html>Rosie report</html>',encoding='utf-8')
        self.second.write_text('<html>Glitchbyte report</html>',encoding='utf-8')
        self.first.touch()
        self.second.touch()
        self.ui = a.Palette('never')

    def picker(self, reply, launcher=None, which=None):
        calls = []
        if launcher is None:
            launcher = lambda *args, **kwargs: calls.append((args,kwargs))
        if which is None:
            which = lambda app: '/usr/bin/firefox' if app == 'firefox' else None
        with redirect_stdout(io.StringIO()) as out:
            selected = v.choose_and_open(self.root,self.ui,lambda prompt: reply,
                                         downloads=self.downloads,launcher=launcher,which=which)
        return selected, calls, out.getvalue()

    def test_previous_reports_discovered_without_copying(self):
        result = v.find_reports(self.root,downloads=self.downloads)
        self.assertEqual({x.name for x in result}, {'rosie-test.html','glitchbyte-test.html'})

    def test_open_by_number_explicit_only(self):
        reports = v.find_reports(self.root,downloads=self.downloads)
        index = reports.index(self.first)+1
        selected,calls,out = self.picker(str(index))
        self.assertEqual(selected,self.first)
        self.assertEqual(len(calls),1)
        command = calls[0][0][0]
        self.assertEqual(command[0], '/usr/bin/firefox')
        self.assertEqual(command[1],self.first.resolve().as_uri())
        self.assertIn('Opening saved HTML',out)
        self.assertIn('from ALIASTORM-STORM-REBORN-SAFE-REDIRECTS',out)

    def test_cancel_and_blank_never_launch(self):
        for reply in ('','0'):
            selected,calls,out = self.picker(reply)
            self.assertIsNone(selected)
            self.assertFalse(calls)
            self.assertIn('canceled',out)

    def test_wrong_number_never_launch(self):
        for reply in ('abc','-1','999','2;echo unsafe'):
            selected,calls,out = self.picker(reply)
            self.assertIsNone(selected)
            self.assertFalse(calls)
            self.assertIn('No report opened',out)

    def test_empty_folder_does_not_launch(self):
        self.first.unlink()
        self.second.unlink()
        selected,calls,out = self.picker('1')
        self.assertIsNone(selected)
        self.assertFalse(calls)
        self.assertIn('No saved HTML reports',out)

    def test_fallback_to_default_opener(self):
        selected,calls,out = self.picker('1',which=lambda app: '/usr/bin/xdg-open' if app=='xdg-open' else None)
        self.assertIsNotNone(selected)
        self.assertEqual(calls[0][0][0][0],'/usr/bin/xdg-open')

    def test_no_installed_browser_does_not_launch(self):
        selected,calls,out = self.picker('1',which=lambda app: None)
        self.assertIsNone(selected)
        self.assertFalse(calls)
        self.assertIn('Open this file manually',out)

    def test_no_shell_interpolation(self):
        file = self.old/'name;echo attack.html'
        file.write_text('safe')
        index = v.find_reports(self.root,downloads=self.downloads).index(file)+1
        selected,calls,out = self.picker(str(index))
        self.assertEqual(selected,file)
        self.assertEqual(len(calls[0][0][0]),2)
        self.assertNotIn('bash',str(calls))

    def test_menu_wires_four_to_picker(self):
        with patch('aliastorm.ask',side_effect=['4','','0']), \
             patch('viewer_menu.choose_and_open') as choose, \
             redirect_stdout(io.StringIO()) as out:
            a.menu(self.ui)
        choose.assert_called_once()
        self.assertIn('[4] HTML RESULTS VIEWER',out.getvalue())

    def test_report_picker_never_edits_saved_files(self):
        before=self.first.read_bytes()
        self.picker('0')
        self.assertEqual(before,self.first.read_bytes())

if __name__=='__main__':
    unittest.main()
