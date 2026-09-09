# Fail visibly if the desktop integration is missing. A successful import
# alone cannot prove Wayland hotkeys, focus detection or input injection work.
from . import bridge


def check_accessibility_permission():
    try:
        bridge.check()
        return True
    except Exception:
        return False


def handle_missing_permission(config_manager):
    raise RuntimeError('Enable the Whisper Local GNOME extension before dictating. '
                       'See docs/linux.md; run whisper-local --doctor to verify.')
