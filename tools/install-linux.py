#!/usr/bin/env python3
# Install the companion GNOME extension without changing other extensions.
# The Python app is installed separately with uv; first activation may need login.
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--enable', action='store_true')
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1] / 'packaging' / 'gnome'
    uuid = 'whisper-local@juicebox6030.github.io'
    directory = source / uuid
    metadata = json.loads((directory / 'metadata.json').read_text())
    assert metadata['uuid'] == uuid
    with tempfile.TemporaryDirectory(prefix='whisper-extension-') as temp:
        archive = Path(temp) / (uuid + '.shell-extension.zip')
        with zipfile.ZipFile(archive, 'w') as output:
            for path in directory.rglob('*'):
                if path.is_file():
                    output.write(path, path.relative_to(directory))
        subprocess.run(['gnome-extensions', 'install', '--force', str(archive)], check=True)
    print(f'Installed GNOME extension: {uuid}')
    if args.enable:
        result = subprocess.run(['gnome-extensions', 'enable', uuid])
        if result.returncode:
            print(f'Log out and back in, then run: gnome-extensions enable {uuid}')
            return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
