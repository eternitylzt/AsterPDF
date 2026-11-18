"""Command registration preserves existing configuration and caller arguments."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from asterpdf import cli


@pytest.mark.parametrize('platform', ['linux', 'darwin'])
def test_install_is_idempotent_and_preserves_shell_settings(tmp_path, monkeypatch, platform):
    executable = tmp_path / 'App folder' / 'AsterPDF'
    executable.parent.mkdir()
    executable.write_bytes(b'fixture')
    monkeypatch.setattr(cli.sys, 'platform', platform)
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr(cli, 'application_command', lambda: [str(executable)])
    monkeypatch.setattr(cli.shutil, 'which', lambda command: None)
    profile = tmp_path / ('.zprofile' if platform == 'darwin' else '.profile')
    profile.write_text('# Existing configuration\nexport CUSTOM=value\n', encoding='utf-8')
    launcher = cli.install_command()
    assert launcher == tmp_path / '.local' / 'bin' / 'asterpdf'
    first = {path: path.read_bytes() for path in tmp_path.rglob('*') if path.is_file()}
    assert '# Existing configuration\nexport CUSTOM=value' in profile.read_text(encoding='utf-8')
    assert profile.read_text(encoding='utf-8').count(cli.PATH_START) == 1
    cli.install_command()
    assert first == {path: path.read_bytes() for path in tmp_path.rglob('*') if path.is_file()}


def test_existing_command_is_not_overwritten(tmp_path, monkeypatch):
    executable = tmp_path / 'AsterPDF.exe'
    executable.write_bytes(b'fixture')
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr(cli, 'application_command', lambda: [str(executable)])
    monkeypatch.setattr(cli.shutil, 'which', lambda command: str(tmp_path / 'other' / 'asterpdf'))
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    with pytest.raises(FileExistsError, match='already on PATH'):
        cli.install_command()
    assert list(tmp_path.iterdir()) == [executable]


def test_windows_registration_updates_user_path_once(tmp_path, monkeypatch):
    executable = tmp_path / 'App folder' / 'AsterPDF.exe'
    executable.parent.mkdir()
    executable.write_bytes(b'fixture')
    monkeypatch.setattr(cli.sys, 'platform', 'win32')
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setattr(cli, 'application_command', lambda: [str(executable)])
    monkeypatch.setattr(cli.shutil, 'which', lambda command: None)
    called = []
    monkeypatch.setattr(cli, 'add_windows_path', called.append)
    target = cli.install_command()
    assert target == tmp_path / 'AsterPDF' / 'bin' / 'asterpdf.cmd'
    assert called == [target.parent]
    assert '%*' in target.read_text(encoding='utf-8')
    assert 'DisableDelayedExpansion' in target.read_text(encoding='utf-8')


def test_registration_rolls_back_after_profile_write_failure(tmp_path, monkeypatch):
    executable = tmp_path / 'AsterPDF'
    executable.write_bytes(b'fixture')
    profile = tmp_path / '.profile'
    profile.write_text('export EXISTING=yes\n', encoding='utf-8')
    monkeypatch.setattr(cli.sys, 'platform', 'linux')
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr(cli, 'application_command', lambda: [str(executable)])
    monkeypatch.setattr(cli.shutil, 'which', lambda command: None)
    write = cli.write_atomic

    def fail_bashrc(path, text, executable=False):
        if path.name == '.bashrc':
            raise PermissionError('profile is read-only')
        return write(path, text, executable)

    monkeypatch.setattr(cli, 'write_atomic', fail_bashrc)
    with pytest.raises(PermissionError):
        cli.install_command()
    assert not (tmp_path / '.local' / 'bin' / 'asterpdf').exists()
    assert profile.read_text(encoding='utf-8') == 'export EXISTING=yes\n'


def test_launcher_preserves_relative_filenames_spaces_and_cwd(tmp_path):
    spy = tmp_path / '应用 folder' / 'record arguments.py'
    spy.parent.mkdir()
    spy.write_text(
        'import json, os, sys\n'
        'from pathlib import Path\n'
        'Path("received.json").write_text(json.dumps([os.getcwd(), sys.argv[1:]]))\n',
        encoding='utf-8',
    )
    windows = sys.platform == 'win32'
    launcher = tmp_path / ('asterpdf.cmd' if windows else 'asterpdf')
    cli.write_atomic(launcher, cli.launcher_text([sys.executable, str(spy)], windows), executable=True)
    arguments = ['a.pdf', 'a spaced document.pdf', '中文.pdf']
    if windows:
        subprocess.run(['cmd.exe', '/d', '/c', str(launcher), *arguments], cwd=tmp_path, check=True, timeout=15)
    else:
        subprocess.run([str(launcher), *arguments], cwd=tmp_path, check=True, timeout=15)
    directory, received = json.loads((tmp_path / 'received.json').read_text(encoding='utf-8'))
    assert Path(directory) == tmp_path
    assert received == arguments


@pytest.mark.skipif(os.name == 'nt', reason='POSIX shell PATH test')
def test_shell_path_block_handles_spaces_and_repeated_sourcing(tmp_path):
    directory = tmp_path / "user's local bin"
    profile = tmp_path / 'profile'
    profile.write_text(cli.profile_text('', directory), encoding='utf-8')
    script = '. "$1"; . "$1"; printf "%s" "$PATH"'
    result = subprocess.check_output(['sh', '-c', script, 'sh', str(profile)], text=True)
    assert result.split(':').count(str(directory)) == 1
