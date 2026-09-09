# Linux config paths follow XDG, shared by settings, history and diagnostics.
# File opening uses argv so paths never become executable shell fragments.
import os
import subprocess
from pathlib import Path


def get_app_data_path():
    base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    if not base.is_absolute():
        base = Path.home() / '.config'
    return base / 'whisperkey'


def open_file(path):
    subprocess.Popen(['xdg-open', str(Path(path).absolute())])
