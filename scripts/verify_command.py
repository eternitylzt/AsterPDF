"""CI smoke for the actual frozen bundle: detached launch and one shared GUI."""
from pathlib import Path
import json
import os
import signal
import subprocess
import sys
import tempfile
import time

import pymupdf

root = Path(__file__).resolve().parents[1]
default = ('AsterPDF.app/Contents/MacOS/AsterPDF' if sys.platform == 'darwin' else
           'AsterPDF/AsterPDF.exe' if os.name == 'nt' else 'AsterPDF/AsterPDF')
executable = Path(sys.argv[1] if len(sys.argv) > 1 else root / 'dist' / default).resolve()
assert executable.is_file(), executable


def wait_for(predicate):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if predicate():return
        time.sleep(.1)
    raise AssertionError('Frozen command did not open the expected tabs')


with tempfile.TemporaryDirectory(prefix='aster-command-') as temporary:
    folder = Path(temporary)
    profile = folder / 'user profile'
    files = ['中文 first.pdf', 'second.pdf']
    for name in files:
        with pymupdf.open() as pdf:
            pdf.new_page().insert_text((40, 50), 'Command verification')
            pdf.save(folder / name)
    environment = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen'}
    times = []

    def records():
        return list((profile / 'recovery').glob('*/recovery.json'))

    def owners():
        return {int(p.read_text(encoding='utf-8').splitlines()[0])
                for p in (profile / 'recovery').glob('*/session.lock')}

    try:
        for index, name in enumerate([*files, files[0]]):
            started = time.monotonic()
            result = subprocess.run([str(executable), '--background', '--data-dir', str(profile), '--', name],
                cwd=folder, env=environment, capture_output=True, timeout=15)
            assert result.returncode == 0, (result.stdout, result.stderr)
            times.append(round(time.monotonic() - started, 3))
            wait_for(lambda: len(records()) == min(index + 1, 2))
        time.sleep(1)
        assert len(records()) == 2 and len(owners()) == 1
        names = {Path(json.loads(p.read_text(encoding='utf-8'))['original']).name for p in records()}
        assert names == set(files)
        log = (profile / 'startup.log').read_text(encoding='utf-8', errors='replace')
        assert 'missing font family "Microsoft YaHei UI"' not in log
        print(json.dumps({'frozen_command': 'passed', 'platform': sys.platform, 'tabs': 2,
                          'processes': 1, 'return_seconds': times}))
    except Exception:
        logfile = profile / 'startup.log'
        if logfile.exists():print(logfile.read_text(encoding='utf-8', errors='replace')[-4000:])
        raise
    finally:
        # These PIDs come only from this temporary profile's own test sessions.
        # Never stop a process associated with the user's normal application.
        for pid in owners():
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True, timeout=10)
            else:
                try:os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:pass
        time.sleep(.5)
