#!/usr/bin/env python3
# Real compositor integration smoke test on a private D-Bus session.
# Run with dbus-run-session -- .venv/bin/python tools/test-gnome.py.
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import sys
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--desktop-only', action='store_true', help='Test desktop integration without full audio app startup')
    args = parser.parse_args()
    from whisper_key.platform.linux import bridge
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='whisper-gnome-test-') as temp:
        data = Path(temp) / 'data'
        extension = data / 'gnome-shell' / 'extensions' / bridge.UUID
        shutil.copytree(Path(bridge.__file__).parent / 'assets', extension)
        # Test-only input driver in the disposable extension copy. It simulates
        # physical key edges without the production delivery feedback filter.
        source = extension / 'extension.js'
        source.write_text(source.read_text().replace("case 'ping':", """case 'test-ready':
            Main.overview.hide();
            return !Main.layoutManager._startingUp;
        case 'test-focus':
            return {overview: Main.overview.visible, focus: String(global.stage.key_focus),
                windows: global.get_window_actors().map(a => a.meta_window.get_title())};
        case 'test-overview':
            Main.overview.show();
            return true;
        case 'test-displays':
            return {DISPLAY: GLib.getenv('DISPLAY'), XAUTHORITY: GLib.getenv('XAUTHORITY')};
        case 'test-key':
            this._keyboard.notify_keyval(GLib.get_monotonic_time(), keyval(r.key),
                r.pressed ? Clutter.KeyState.PRESSED : Clutter.KeyState.RELEASED);
            return true;
        case 'ping':"""))
        os.environ.update(XDG_DATA_HOME=str(data), XDG_CONFIG_HOME=str(Path(temp) / 'config'),
                          GSETTINGS_BACKEND='keyfile')
        subprocess.run(['gsettings', 'set', 'org.gnome.shell', 'enabled-extensions',
                        f"['{bridge.UUID}']"], check=True)
        subprocess.run(['gsettings', 'set', 'org.gnome.mutter', 'overlay-key', ''], check=True)
        subprocess.run(['gsettings', 'set', 'org.gnome.shell', 'welcome-dialog-last-shown-version', '99.0'], check=True)
        display = f'whisper-test-{os.getpid()}'
        os.environ['WAYLAND_DISPLAY'] = display
        with open(Path(temp) / 'shell.log', 'w+') as log:
            shell = subprocess.Popen(['gnome-shell', '--headless', '--wayland',
                '--wayland-display', display, '--virtual-monitor', '1280x720'], stdout=log, stderr=log)
            try:
                for _ in range(40):
                    if shell.poll() is not None:
                        raise RuntimeError(f'GNOME exited: {shell.returncode}')
                    try:
                        print('BRIDGE', bridge.check(), flush=True)
                        break
                    except Exception:
                        time.sleep(0.5)
                else:
                    raise RuntimeError('GNOME bridge did not become available')
                for _ in range(40):
                    if bridge.call('test-ready'):
                        break
                    time.sleep(0.2)
                time.sleep(0.5)
                bridge.call('register', bindings=['ctrl+win', 'ctrl', 'alt', 'esc', 'ctrl+win+shift', 'ctrl+alt+win'], generation=1)
                bridge.call('menu', title='Whisper test', items=[dict(id='1', label='Test', enabled=True)])
                bridge.call('overlay', mode='recording', text='Test recording', position='bottom-center', level=0.5)
                print('FOREGROUND', bridge.call('foreground'), flush=True)
                bridge.call('overlay', mode='hidden', text='', position='bottom-center', level=0)
                bridge.call('register', bindings=['ctrl+super+space'], generation=2)
                print('EVENTS', bridge.call('poll'), flush=True)
                bridge.call('register', bindings=[], generation=3)
                result = Path(temp) / 'typed.txt'
                probe_env = dict(os.environ, GDK_BACKEND='wayland')
                probe = subprocess.Popen(['/usr/bin/python3', str(root / 'tools' / 'gnome-probe.py'), str(result)], env=probe_env)
                try:
                    for _ in range(30):
                        info = bridge.call('foreground')
                        if info.get('title') == 'Whisper Linux integration probe':
                            break
                        time.sleep(0.2)
                    else:
                        raise RuntimeError(f'Probe did not focus: {info} {bridge.call("test-focus")}')
                    print('NATIVE WAYLAND FOCUS', info, flush=True)
                    from whisper_key.platform.linux import keyboard
                    import pyperclip
                    pyperclip.copy('original clipboard')
                    keyboard.type_text('Whisper café 世界 🎤')
                    time.sleep(0.5)
                    actual = result.read_text() if result.exists() else ''
                    assert actual == 'Whisper café 世界 🎤', repr(actual)
                    assert pyperclip.paste() == 'original clipboard'
                    bridge.call('keys', keys=['ctrl', 'a'])
                    time.sleep(0.1)
                    print('TEXT RESULT', bridge.call('text', text='Replacement'), flush=True)
                    time.sleep(0.3)
                    assert result.read_text() == 'Replacement', repr(result.read_text())
                    print('UNICODE + CTRL+A REPLACEMENT passed', flush=True)
                    time.sleep(0.2)
                    bridge.call('register', bindings=['ctrl+win', 'ctrl', 'alt', 'esc'], generation=4)
                    for key in ('ctrl', 'win'):
                        bridge.call('test-key', key=key, pressed=True)
                        time.sleep(0.06)
                    # A complete press/release sequence alone misses premature
                    # release: assert the chord stays down throughout a hold.
                    time.sleep(1)
                    held_events = bridge.call('poll')
                    assert [e['pressed'] for e in held_events if e.get('index') == 0] == [True], held_events
                    bridge.call('test-key', key='win', pressed=False)
                    time.sleep(0.08)
                    released_events = bridge.call('poll')
                    assert [e['pressed'] for e in released_events if e.get('index') == 0] == [False], released_events
                    assert not any(e.get('index') == 1 and e['pressed'] for e in released_events), released_events
                    bridge.call('test-key', key='ctrl', pressed=False)
                    time.sleep(0.08)
                    events = held_events + released_events + bridge.call('poll')
                    ptt = [e['pressed'] for e in events if e.get('index') == 0]
                    assert ptt == [True, False], events
                    print('MODIFIER PUSH-TO-TALK passed', events, flush=True)
                    bridge.call('register', bindings=['ctrl+super+space'], generation=5)
                    for key in ('ctrl', 'super', 'space'):
                        bridge.call('test-key', key=key, pressed=True)
                    time.sleep(0.1)
                    for key in ('space', 'super', 'ctrl'):
                        bridge.call('test-key', key=key, pressed=False)
                    time.sleep(0.1)
                    events = bridge.call('poll')
                    assert [e['pressed'] for e in events] == [True, False], events
                    print('ACCELERATOR PRESS/RELEASE passed', flush=True)
                    bridge.call('register', bindings=['esc'], recordingOnly=[0], generation=6)
                    bridge.call('state', state='recording')
                    bridge.call('test-key', key='esc', pressed=True)
                    time.sleep(0.06)
                    bridge.call('test-key', key='esc', pressed=False)
                    time.sleep(0.06)
                    assert [e['pressed'] for e in bridge.call('poll')] == [True, False]
                    bridge.call('state', state='idle')
                    bridge.call('test-key', key='esc', pressed=True)
                    bridge.call('test-key', key='esc', pressed=False)
                    time.sleep(0.06)
                    assert bridge.call('poll') == []
                    print('CANCEL WITHOUT OVERLAY + IDLE ESCAPE passed', flush=True)
                    bridge.call('test-overview')
                    time.sleep(0.3)
                    assert bridge.call('foreground') == {}
                    try:
                        keyboard.type_text('must not reach Shell search')
                    except RuntimeError:
                        pass
                    else:
                        raise AssertionError('Shell focus must reject delivery')
                    bridge.call('test-ready')
                    print('SHELL FOCUS SAFETY passed', flush=True)
                    time.sleep(0.4)
                    keyboard.send_hotkey('show_desktop')
                    time.sleep(0.3)
                    assert bridge.call('foreground') == {}
                    print('SHOW DESKTOP passed', flush=True)
                finally:
                    probe.terminate()
                    probe.wait(timeout=5)
                # These shared Tk windows use XWayland. Never inherit the real
                # desktop's DISPLAY while testing against a nested compositor.
                gui_env = dict(os.environ)
                displays = bridge.call('test-displays')
                if not displays.get('DISPLAY'):
                    raise RuntimeError('Nested compositor did not expose XWayland DISPLAY')
                for key, value in displays.items():
                    if value:
                        gui_env[key] = value
                    else:
                        gui_env.pop(key, None)
                for flag, title in [('--settings', 'Whisper Local'), ('--history', 'Whisper Local')]:
                    window = subprocess.Popen([sys.executable, '-m', 'whisper_key.main', flag], env=gui_env)
                    try:
                        for _ in range(40):
                            titles = bridge.call('test-focus')['windows']
                            if any(title in name for name in titles):
                                break
                            if window.poll() is not None:
                                raise RuntimeError(f'{flag} exited before opening a window')
                            time.sleep(0.2)
                        else:
                            raise RuntimeError(f'{flag} did not open: {titles}')
                        print(f'{flag} XWAYLAND WINDOW passed', flush=True)
                    finally:
                        window.terminate()
                        window.wait(timeout=5)
                        time.sleep(0.2)
                if args.desktop_only:
                    print('GNOME desktop integration passed (full audio startup not requested)', flush=True)
                    return
                # Release the test client's ownership before exercising the real app.
                bridge._loop.call_soon_threadsafe(bridge._bus.disconnect)
                time.sleep(0.2)
                config = Path(os.environ['XDG_CONFIG_HOME']) / 'whisperkey'
                config.mkdir(exist_ok=True)
                (config / 'first_run_complete.txt').write_text('test')
                (config / 'onboarding-complete.txt').write_text('test')
                (config / 'user_settings.yaml').write_text('onboarding:\n  gpu: no_gpu\naudio_feedback:\n  enabled: false\nupdate_check:\n  enabled: false\n')
                with open(Path(temp) / 'app.log', 'w+') as app_log:
                    app = subprocess.Popen([sys.executable, '-u', '-m', 'whisper_key.main'],
                        stdin=subprocess.DEVNULL, stdout=app_log, stderr=app_log)
                    try:
                        for _ in range(100):
                            app_log.seek(0)
                            output = app_log.read()
                            if 'Whisper Local ready!' in output:
                                break
                            if app.poll() is not None:
                                raise RuntimeError(f'App startup failed: {output}')
                            time.sleep(0.2)
                        else:
                            raise RuntimeError(f'App startup timed out: {output}')
                        print('FULL APPLICATION STARTUP passed', flush=True)
                    finally:
                        app.terminate()
                        try:
                            app.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            app.kill()
                            app.wait()
                        app_log.seek(0)
                        output = app_log.read()
                        print(output, flush=True)
                    assert app.returncode == 0, output
                    assert 'shutting down' in output, output
                    print('APPLICATION CLEAN SHUTDOWN passed', flush=True)
                print('GNOME integration smoke passed', flush=True)
            finally:
                shell.terminate()
                try:
                    shell.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    shell.kill()
                    shell.wait()
                log.seek(0)
                print(log.read()[-10000:])


if __name__ == '__main__':
    main()
