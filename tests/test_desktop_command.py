"""Multiple real command processes must share one GUI without holding a terminal."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time

import pymupdf as fitz
import pytest

from asterpdf.cli import launcher_text, write_atomic
from asterpdf.launch import main

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / 'tests' / 'desktop_instance_probe.py'


def wait_for(predicate, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.05)
    raise AssertionError('Timed out waiting for the desktop process')


def read_reports(profile):
    return [json.loads(p.read_text(encoding='utf-8')) for p in profile.glob('probe-*.json')]


@pytest.fixture
def desktop_command(tmp_path):
    profile = tmp_path / 'user profile'
    profile.mkdir()
    for name in ('中文 first.pdf', 'second.pdf'):
        with fitz.open() as document:
            page = document.new_page();page.insert_text((40, 50), name)
            document.save(tmp_path / name)
    launcher = tmp_path / ('asterpdf.cmd' if os.name == 'nt' else 'asterpdf')
    write_atomic(launcher, launcher_text([sys.executable, str(PROBE)], os.name == 'nt'), executable=True)
    environment = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'PYTHONPATH': str(ROOT)}

    def command(*files):
        invocation = [str(launcher), '--data-dir', str(profile), *files]
        if os.name == 'nt':invocation = ['cmd.exe', '/d', '/c', *invocation]
        return subprocess.Popen(invocation, cwd=tmp_path, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    yield command, profile, tmp_path
    (profile / 'stop').touch()
    # The probe exits cleanly, releasing its endpoint and any unsaved test data.
    deadline = time.monotonic() + 10
    while list((profile / 'recovery').glob('*/session.lock')) and time.monotonic() < deadline:
        time.sleep(.1)


def test_background_command_reuses_tabs_and_keeps_unsaved_changes(desktop_command):
    command, profile, folder = desktop_command
    first = command('中文 first.pdf')
    stdout, stderr = first.communicate(timeout=12)
    assert first.returncode == 0, (stdout, stderr)
    first_report = wait_for(lambda: next((r for r in read_reports(profile) if len(r['tabs']) == 1), None))
    assert first_report['dirty'] == [True]
    (profile / 'minimize').touch()
    wait_for(lambda: any(r['minimized'] for r in read_reports(profile)))
    second = command('second.pdf')
    stdout, stderr = second.communicate(timeout=12)
    assert second.returncode == 0, (stdout, stderr)
    state = wait_for(lambda: next((r for r in read_reports(profile) if len(r['tabs']) == 2 and not r['minimized']), None))
    assert state['pid'] == first_report['pid']
    assert state['tabs'] == [str(folder / '中文 first.pdf'), str(folder / 'second.pdf')]
    assert state['dirty'] == [True, False]
    duplicate = command('中文 first.pdf')
    assert duplicate.wait(timeout=12) == 0
    time.sleep(1)
    assert len(read_reports(profile)) == 1 and len(read_reports(profile)[0]['tabs']) == 2
    assert 'missing font family "Microsoft YaHei UI"' not in (profile / 'startup.log').read_text(encoding='utf-8')


def test_simultaneous_cold_starts_create_one_window(desktop_command):
    command, profile, folder = desktop_command
    clients = [command('中文 first.pdf'), command('second.pdf')]
    for client in clients:
        stdout, stderr = client.communicate(timeout=12)
        assert client.returncode == 0, (stdout, stderr)
    state = wait_for(lambda: next((r for r in read_reports(profile) if len(r['tabs']) == 2), None))
    assert set(state['tabs']) == {str(folder / '中文 first.pdf'), str(folder / 'second.pdf')}
    assert len(read_reports(profile)) == 1


def test_background_missing_file_reports_error_without_spawning(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: pytest.fail('No process should start'))
    assert main(['--background', str(tmp_path / 'missing.pdf')]) == 1
    assert 'missing' in capsys.readouterr().err


def test_ui_theme_uses_native_font_instead_of_windows_alias():
    from asterpdf.app import DARK, LIGHT
    assert 'font-family:' not in DARK and 'font-family:' not in LIGHT
