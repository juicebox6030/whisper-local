# Fail visibly if the desktop integration is missing. A successful import
# alone cannot prove Wayland hotkeys, focus detection or input injection work.
from . import bridge
from pathlib import Path
import subprocess
import tempfile
import zipfile


def check_accessibility_permission():
    try:
        bridge.check()
        return True
    except Exception:
        return False


def handle_missing_permission(config_manager):
    raise RuntimeError('Run whisper-local --install-gnome-extension, then log out and back in. '
                       'Run whisper-local --doctor to verify desktop integration.')


# Explicit CLI action: never change the desktop during import or diagnostics.
def install_extension():
    source = Path(__file__).parent / 'assets'
    try:
        with tempfile.TemporaryDirectory(prefix='whisper-extension-') as temp:
            archive = Path(temp) / (bridge.UUID + '.shell-extension.zip')
            with zipfile.ZipFile(archive, 'w') as output:
                for name in ('extension.js', 'metadata.json'):
                    output.write(source / name, name)
            subprocess.run(['gnome-extensions', 'install', '--force', str(archive)], check=True)
        result = subprocess.run(['gnome-extensions', 'enable', bridge.UUID])
    except (OSError, subprocess.CalledProcessError) as error:
        print(f'Could not install GNOME integration: {error}')
        return 1
    print('Installed GNOME integration. Log out and back in to load the new version.')
    if result.returncode:
        print(f'After logging in, run: gnome-extensions enable {bridge.UUID}')
    return 0
