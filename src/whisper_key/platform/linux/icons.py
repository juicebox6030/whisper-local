# Reuse the existing neutral status artwork; GNOME renders its own panel icon.
# Keeping this contract preserves SystemTray's state transitions unchanged.
from pathlib import Path
from PIL import Image


def get_tray_icons():
    assets = Path(__file__).resolve().parents[1] / 'macos' / 'assets'
    return {state: Image.open(assets / f'tray_{state}.png')
            for state in ('idle', 'recording', 'processing')}
