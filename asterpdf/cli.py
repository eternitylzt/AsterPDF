"""Install a per-user command for a frozen desktop bundle or source checkout."""
from pathlib import Path
import os
import shlex
import shutil
import sys
import tempfile


MARKER = 'AsterPDF managed command'
PATH_START = '# >>> AsterPDF command >>>'
PATH_END = '# <<< AsterPDF command <<<'


def application_command():
    if getattr(sys, 'frozen', False):
        return [str(Path(sys.executable).resolve())]
    return [str(Path(sys.executable).resolve()), str(Path(__file__).resolve().parents[1] / 'run.py')]


def launcher_text(command, windows=False):
    if any('\n' in arg or '\r' in arg or '"' in arg for arg in command):
        raise ValueError('The application path cannot contain quotes or line breaks.')
    if windows:
        quoted = ' '.join('"' + arg.replace('%', '%%') + '"' for arg in command)
        return (
            f'@echo off\nrem {MARKER}\nsetlocal DisableDelayedExpansion\n'
            'for /f "tokens=2 delims=:" %%C in (\'chcp\') do set "asterpdf_codepage=%%C"\n'
            'chcp 65001 >nul\n'
            f'{quoted} %*\n'
            'set "asterpdf_status=%errorlevel%"\n'
            'chcp %asterpdf_codepage% >nul\n'
            'exit /b %asterpdf_status%\n'
        ).replace('\n', '\r\n')  # cmd requires CRLF when changing UTF-8 code pages.
    return f'#!/bin/sh\n# {MARKER}\nexec {shlex.join(command)} "$@"\n'


def write_atomic(path, text, executable=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    previous_mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
        os.chmod(temporary, previous_mode | (0o111 if executable else 0))
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def shell_profiles(home, platform):
    if platform == 'darwin':
        # zsh is the default macOS login shell. Include bash when configured.
        profiles = [home / '.zprofile', home / '.zshrc']
        if (home / '.bash_profile').exists():
            profiles.append(home / '.bash_profile')
    else:
        profiles = [home / '.profile', home / '.bashrc']
        if (home / '.bash_profile').exists():
            profiles.append(home / '.bash_profile')
        if 'zsh' in os.environ.get('SHELL', '') or (home / '.zshrc').exists():
            profiles.append(home / '.zshrc')
    return profiles


def profile_text(current, directory):
    if PATH_START in current:
        if PATH_END not in current or current.index(PATH_END) < current.index(PATH_START):
            raise ValueError('An incomplete AsterPDF PATH block already exists in a shell profile.')
        return current
    quoted = shlex.quote(str(directory))
    # The guard avoids adding the directory again when login and interactive
    # profiles are both read, and does not require external shell utilities.
    block = (
        f'{PATH_START}\n'
        f'case ":$PATH:" in\n'
        f'  *:{quoted}:*) ;;\n'
        f'  *) export PATH="$PATH":{quoted} ;;\n'
        f'esac\n'
        f'{PATH_END}\n'
    )
    return current.rstrip('\n') + '\n\n' + block


def add_windows_path(directory):
    import ctypes
    import winreg

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, 'Environment', 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            value, kind = winreg.QueryValueEx(key, 'Path')
        except FileNotFoundError:
            value, kind = '', winreg.REG_EXPAND_SZ
        entries = [os.path.normcase(os.path.expandvars(item.strip())) for item in value.split(';')]
        if os.path.normcase(str(directory)) not in entries:
            value = value.rstrip(';') + (';' if value else '') + str(directory)
            winreg.SetValueEx(key, 'Path', 0, kind, value)
    # Notify Explorer so newly opened terminals inherit the updated user PATH.
    result = ctypes.c_size_t()
    ctypes.windll.user32.SendMessageTimeoutW(
        0xFFFF, 0x001A, 0, ctypes.c_wchar_p('Environment'), 0x0002, 3000, ctypes.byref(result)
    )


def install_command():
    """Register ``asterpdf`` for this user and return the launcher path.

    New terminal sessions read the persisted PATH change. Existing terminals
    can immediately invoke the returned absolute path. No administrator access
    is needed. Linux distribution packages already install /usr/bin/asterpdf.
    """
    command = application_command()
    executable = Path(command[0])
    if not executable.is_file():
        raise FileNotFoundError(executable)
    home = Path.home()
    windows = sys.platform == 'win32'
    directory = (
        Path(os.environ.get('LOCALAPPDATA', home / 'AppData' / 'Local')) / 'AsterPDF' / 'bin'
        if windows else home / '.local' / 'bin'
    )
    target = directory / ('asterpdf.cmd' if windows else 'asterpdf')
    if target.is_symlink():
        raise FileExistsError(f'The command location is a symbolic link: {target}')
    if target.exists() and MARKER not in target.read_text(encoding='utf-8'):
        raise FileExistsError(f'An existing command occupies {target}')

    existing = shutil.which('asterpdf')
    if existing and Path(existing) != target:
        existing_path = Path(existing)
        if existing_path.resolve() == executable and getattr(sys, 'frozen', False):
            return existing_path
        if existing_path == Path('/usr/bin/asterpdf') and executable == Path('/opt/asterpdf/AsterPDF'):
            if 'exec /opt/asterpdf/AsterPDF "$@"' in existing_path.read_text(encoding='utf-8'):
                return existing_path
        raise FileExistsError(f'Another asterpdf command is already on PATH: {existing}')

    changes = {target: launcher_text(command, windows)}
    if not windows:
        for profile in shell_profiles(home, sys.platform):
            # Follow an existing user's profile symlink and preserve its target.
            profile = profile.resolve()
            current = profile.read_text(encoding='utf-8') if profile.exists() else ''
            changes[profile] = profile_text(current, directory)
    originals = {path: path.read_bytes().decode('utf-8') if path.exists() else None for path in changes}
    written = []
    try:
        for path, text in changes.items():
            if text != originals[path]:
                write_atomic(path, text, executable=path == target)
                written.append(path)
        if windows:
            add_windows_path(directory)
    except Exception:
        for path in reversed(written):
            previous = originals[path]
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                write_atomic(path, previous, executable=path == target)
        raise
    return target
