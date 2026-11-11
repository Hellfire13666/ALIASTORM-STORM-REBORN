"""Presentation-only regression checks for neon RGB edition."""
import io
import os
import re
from contextlib import redirect_stdout
from unittest import TestCase, mock
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import aliastorm

ESCAPES = re.compile(r'\x1b\[[0-9;]*m')

class NeonStyleTests(TestCase):
    def test_bright_rgb_is_truecolor_and_bold(self):
        p = aliastorm.Palette('always')
        self.assertIn('\x1b[1;38;2;',p.color('NEON', 'hotpink'))
        self.assertIn('\x1b[1;38;2;',p.rainbow('ALIASTORM'))

    def test_no_color_remains_plain(self):
        p = aliastorm.Palette('never')
        self.assertEqual(p.color('NEON','yellow'), 'NEON')
        self.assertEqual(p.panel('NEON','yellow'), 'NEON')
        self.assertEqual(p.rainbow('ALIASTORM'), 'ALIASTORM')

    def test_header_frame_is_square_for_several_widths(self):
        for cols in (42, 60, 80, 105, 180):
            for kind in ('never', 'always'):
                with self.subTest(width=cols, color=kind):
                    with mock.patch.object(aliastorm.shutil, 'get_terminal_size', return_value=os.terminal_size((cols,24))):
                        buf=io.StringIO()
                        with redirect_stdout(buf): aliastorm.banner(aliastorm.Palette(kind))
                    lines=[ESCAPES.sub('',x) for x in buf.getvalue().splitlines()]
                    if cols < 44: continue
                    self.assertTrue(lines[0].startswith('  ╔'))
                    self.assertTrue(lines[1].startswith('  ║'))
                    self.assertTrue(lines[2].startswith('  ║'))
                    self.assertTrue(lines[3].startswith('  ╚'))
                    self.assertEqual(len(lines[0]),len(lines[1]))
                    self.assertEqual(len(lines[1]),len(lines[2]))
                    self.assertEqual(len(lines[2]),len(lines[3]))
                    self.assertLessEqual(len(lines[0]),cols)

    def test_narrow_fallback_has_no_broken_box(self):
        with mock.patch.object(aliastorm.shutil, 'get_terminal_size', return_value=os.terminal_size((35,24))):
            b=io.StringIO()
            with redirect_stdout(b): aliastorm.banner(aliastorm.Palette('never'))
        s=b.getvalue()
        self.assertIn('ALIASTORM',s)
        self.assertNotIn('╔',s)

    def test_sources_and_report_engine_still_present(self):
        self.assertEqual(len(aliastorm.load_sources()),154)
