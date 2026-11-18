"""Lightweight terminal/desktop entry: registration needs no GUI imports."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def parser():
    result = argparse.ArgumentParser(description='AsterPDF desktop')
    result.add_argument('files', nargs='*')
    result.add_argument('--data-dir')
    result.add_argument('--install-cli', action='store_true', help='Install the command for the current user (no sudo) and exit')
    result.add_argument('--background', action='store_true', help='Return to the terminal immediately')
    result.add_argument('--smoke-test', action='store_true')
    result.add_argument('--verify-desktop', metavar='OUTPUT_DIRECTORY', help=argparse.SUPPRESS)
    result.add_argument('--verify-update', action='store_true', help=argparse.SUPPRESS)
    return result


def profile_path(directory=None):
    from PySide6.QtCore import QCoreApplication, QStandardPaths
    QCoreApplication.setOrganizationName('AsterPDF')
    QCoreApplication.setApplicationName('AsterPDF')
    return Path(directory).resolve() if directory else Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))


def start_background(args):
    from .cli import application_command
    profile = profile_path(args.data_dir)
    profile.mkdir(parents=True, exist_ok=True)
    logfile = profile / 'startup.log'
    # Bound the diagnostic log without discarding errors from the current launch.
    if logfile.exists() and logfile.stat().st_size > 1024 * 1024:
        logfile.replace(profile / 'startup.previous.log')
    command = application_command() + ['--data-dir', str(profile), '--', *args.files]
    options = {'start_new_session': True} if os.name != 'nt' else {
        'creationflags': subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
    with logfile.open('ab') as output:
        subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
            close_fds=True, env={**os.environ, 'PYINSTALLER_RESET_ENVIRONMENT': '1'}, **options)
    return 0


def main(arguments=None):
    args = parser().parse_args(arguments)
    try:
        if args.install_cli:
            from .cli import install_command
            destination = install_command()
            if sys.stdout:
                print(f'Installed: {destination}\nOpen a new terminal and run: asterpdf "file.pdf"\nNo sudo is needed.')
            return 0
        if args.verify_update:
            from . import __version__
            from .network import fetch_latest_release
            from .release import REPOSITORY
            print(json.dumps(fetch_latest_release(REPOSITORY, __version__)))
            return 0
        # Resolve paths in the caller, before handing them to another process.
        args.files = [str(Path(filename).expanduser().resolve()) for filename in args.files]
        if args.data_dir:
            args.data_dir = str(Path(args.data_dir).expanduser().resolve())
        if args.background and not (args.smoke_test or args.verify_desktop):
            for filename in args.files:
                if not Path(filename).is_file():
                    raise FileNotFoundError(f'File is missing or inaccessible: {filename}')
            return start_background(args)
    except (OSError, ValueError) as error:
        if sys.stderr:
            print(str(error), file=sys.stderr)
        return 1
    from .cli import refresh_registered_command
    try:
        refresh_registered_command()
    except (OSError, UnicodeError):
        pass  # An unwritable command must not prevent normal document reading.
    from .app import run_desktop
    return run_desktop(args)


def command_main():
    return main(['--background', *sys.argv[1:]])
