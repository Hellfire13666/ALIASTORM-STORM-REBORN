"""On-demand launcher for saved local AliaStorm HTML evidence reports.

Browser launch happens only when the operator explicitly chooses [4] and a
numbered report. Public profile research, exports and background behavior
are unchanged. No browser opens after a scan.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
from typing import Callable

MAX_LISTED = 25


def find_reports(root: Path, downloads: Path | None = None) -> list[Path]:
    """Discover this build's reports plus earlier AliaStorm builds in Downloads.

    Important: new builds live in their own folders. Discover saved HTML
    from the previous build so users can keep their old local-reports intact.
    Only look for previously generated reports; never read their contents.
    """
    root = Path(root)
    candidates = list((root / 'local-reports').glob('*.html'))
    downloads = Path(downloads) if downloads is not None else Path.home() / 'Downloads'
    if downloads.is_dir():
        # Path.glob doesn't recurse throughout the user's home directory.
        candidates.extend(downloads.glob('ALIASTORM-*/local-reports/*.html'))
    unique = {}
    for p in candidates:
        try:
            if p.is_file():
                unique[p.resolve()] = p
        except (OSError, RuntimeError):
            continue
    def modified(p):
        try:
            return p.stat().st_mtime
        except OSError:
            return 0
    return sorted(unique.values(), key=modified, reverse=True)[:MAX_LISTED]


def browser_command(report: Path, which: Callable = shutil.which) -> list[str] | None:
    """Use Firefox when available, otherwise the user's standard opener.

    Keep subprocess arguments separate, so filenames cannot become shell
    commands. Local file: URLs, not HTTP URLs or network requests.
    """
    for name in ('firefox','xdg-open'):
        executable = which(name)
        if executable:
            return [executable, report.resolve().as_uri()]
    return None


def choose_and_open(root: Path, ui, ask: Callable, *,
                    downloads: Path | None = None,
                    launcher: Callable = subprocess.Popen,
                    which: Callable = shutil.which):
    """Show saved HTML reports and open one only after explicit selection."""
    reports = find_reports(root, downloads)
    ui.say('\n  🌈 STORM REBORN // LOCAL HTML RESULTS', 'hotpink')
    ui.say('  Saved scans only • no rescan • browser opens only if you choose a report', 'aqua')
    if not reports:
        ui.say('  No saved HTML reports found in this build or earlier AliaStorm Downloads folders.', 'yellow')
        ui.say('  Run [1] USERNAME STORM to create a report, then return to [4].', 'white')
        return None
    for i, report in enumerate(reports, 1):
        ui.say('  ['+str(i).rjust(2)+'] '+report.name, 'green' if i == 1 else 'white')
        ui.say('       from '+report.parent.parent.name, 'purple')
    ui.say('  [ 0] RETURN WITHOUT OPENING', 'yellow')
    choice = ask(ui.color('  Open report number > ', 'hotpink'))
    if choice in ('', '0'):
        ui.say('  Viewer canceled. No browser opened.', 'white')
        return None
    if not choice.isascii() or not choice.isdecimal() or not (1 <= int(choice) <= len(reports)):
        ui.say('  No report opened: enter a number shown in the list.', 'yellow')
        return None
    report = reports[int(choice)-1]
    # The saved report must still exist at the moment of launch.
    if not report.is_file():
        ui.say('  This report is no longer available.', 'red')
        return None
    cmd = browser_command(report, which=which)
    if not cmd:
        ui.say('  No Firefox/default opener was found. Open this file manually:', 'yellow')
        ui.say('  '+str(report), 'white')
        return None
    try:
        launcher(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                 stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as exc:
        ui.say('  Could not launch browser: '+str(exc), 'red')
        ui.say('  Open manually: '+str(report), 'white')
        return None
    ui.say('  🌈 Opening saved HTML in your browser: '+report.name, 'green')
    ui.say('  Local file only. No online scan was started.', 'aqua')
    return report
