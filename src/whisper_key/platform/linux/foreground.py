# GNOME supplies metadata for native Wayland windows as well as XWayland.
# Probe failure raises: silently returning {} could bypass a suppress rule.
import os
from .bridge import call


def get_foreground_app():
    info = call('foreground')
    pid = info.pop('pid', 0)
    if pid:
        try:
            info['path'] = os.readlink(f'/proc/{int(pid)}/exe')
            info['exe'] = os.path.basename(info['path']).lower()
        except OSError:
            pass
    return info
