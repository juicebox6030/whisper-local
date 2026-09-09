#!/usr/bin/env python3
# Test delivery only into our dedicated native Wayland window on the real desktop.
# Requires an enabled extension; keep the probe focused during this short test.
import os
from pathlib import Path
import subprocess
import tempfile
import time


def main():
    from whisper_key.platform.linux import app, bridge, keyboard
    import pyperclip
    app.setup()
    bridge.check()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='whisper-desktop-test-') as temp:
        result = Path(temp) / 'text.txt'
        probe = subprocess.Popen(['/usr/bin/python3', str(root / 'tools/gnome-probe.py'), str(result)],
                                 env=dict(os.environ, GDK_BACKEND='wayland'))
        original = pyperclip.paste()
        try:
            def focused():
                info = bridge.call('foreground')
                if info.get('pid') != probe.pid:
                    raise RuntimeError('Focus changed: aborting desktop input test')

            for _ in range(100):
                if bridge.call('foreground').get('pid') == probe.pid:
                    break
                if probe.poll() is not None:
                    raise RuntimeError('Test window exited')
                time.sleep(0.1)
            focused()
            keyboard.type_text('Whisper café 世界 🎤')
            time.sleep(0.3)
            assert result.read_text() == 'Whisper café 世界 🎤'
            assert pyperclip.paste() == original
            focused()
            keyboard.send_hotkey('ctrl', 'a')
            focused()
            keyboard.type_text('Linux desktop delivery passed')
            time.sleep(0.3)
            assert result.read_text() == 'Linux desktop delivery passed'
            print('REAL DESKTOP Unicode, replacement and clipboard preservation passed', flush=True)
        finally:
            probe.terminate()
            probe.wait(timeout=5)


if __name__ == '__main__':
    main()
