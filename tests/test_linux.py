"""Linux platform contracts and failures; no live keyboard injection in unit tests."""
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Linux backend')


def test_paths_and_lock(tmp_path, monkeypatch):
    from whisper_key.platform.linux import paths, instance_lock
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    assert paths.get_app_data_path() == tmp_path / 'whisperkey'
    lock = instance_lock.acquire_lock('test')
    assert lock
    assert instance_lock.acquire_lock('test') is None
    instance_lock.release_lock(lock)
    again = instance_lock.acquire_lock('test')
    assert again
    instance_lock.release_lock(again)


def test_relative_xdg_path_ignored(monkeypatch):
    from whisper_key.platform.linux.paths import get_app_data_path
    monkeypatch.setenv('XDG_CONFIG_HOME', 'relative')
    assert Path(get_app_data_path()).is_absolute()


def test_autostart_roundtrip(tmp_path, monkeypatch):
    from whisper_key import autostart
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    monkeypatch.setattr(autostart, '_launch_command', lambda: ['/path with spaces/python', '-m', 'whisper_key.main'])
    assert not autostart.is_enabled()
    assert autostart.enable()
    assert autostart.is_enabled()
    assert 'Exec="/path with spaces/python" "-m" "whisper_key.main"' in autostart._linux_desktop_path().read_text()
    assert autostart.disable()
    assert not autostart.is_enabled()
    assert autostart.disable()


def test_desktop_entry_rejects_newlines():
    from whisper_key.autostart import _desktop_quote
    with pytest.raises(ValueError):
        _desktop_quote('/tmp/path\nExec=malicious')
    assert '%%' in _desktop_quote('/tmp/100%')


def test_hotkey_generation_and_edges():
    from whisper_key.platform.linux import hotkeys
    press, release = Mock(), Mock()
    with patch.object(hotkeys.bridge, 'call'):
        hotkeys.register([['ctrl+win', press, release, False]])
        generation = hotkeys._generation
        hotkeys.dispatch(dict(type='hotkey', index=0, pressed=True, generation=generation - 1))
        press.assert_not_called()
        hotkeys.dispatch(dict(type='hotkey', index=0, pressed=True, generation=generation))
        hotkeys.dispatch(dict(type='hotkey', index=0, pressed=False, generation=generation))
        press.assert_called_once()
        release.assert_called_once()


def test_cancel_role_not_key_name_controls_conditional_grab():
    from whisper_key.platform.linux import hotkeys
    with patch.object(hotkeys.bridge, 'call') as call:
        hotkeys.register([['esc', Mock(), None, False], ['f8', Mock(), None, False]], recording_only='f8')
    assert call.call_args.kwargs['recordingOnly'] == [1]


def test_delivery_errors_propagate():
    from whisper_key.platform.linux import keyboard, foreground
    with patch.object(keyboard, 'call', side_effect=RuntimeError('locked')):
        with pytest.raises(RuntimeError, match='locked'):
            keyboard.send_hotkey('ctrl', 'v')
    with patch.object(foreground, 'call', side_effect=RuntimeError('offline')):
        with pytest.raises(RuntimeError, match='offline'):
            foreground.get_foreground_app()


def test_unicode_delivery_chunks_without_losing_characters():
    from whisper_key.platform.linux import keyboard
    text = 'Café 世界 🎤\n' * 40
    with patch.object(keyboard, 'call') as call:
        keyboard.type_text(text)
    assert ''.join(c.kwargs['text'] for c in call.call_args_list) == text
    assert all(len(c.kwargs['text']) <= 128 for c in call.call_args_list)


def test_menu_preserves_submenus_checks_and_actions():
    from whisper_key.platform.linux import tray
    action = Mock()
    menu = tray.Menu(tray.MenuItem('Profiles', tray.Menu(
        tray.MenuItem('Code', action, checked=lambda _: True, radio=True))), tray.Menu.SEPARATOR)
    with patch.object(tray.bridge, 'call') as call:
        icon = tray.Icon('test', None, 'test', menu)
        icon._publish()
        payload = call.call_args.kwargs['items']
        child = payload[0]['children'][0]
        assert child['checked'] is True
        assert child['radio'] is True
        assert payload[1]['separator']
        icon._activate(dict(id=child['id']))
        action.assert_called_once()


def test_cli_import_has_no_desktop_dependency():
    import whisper_key.main
    assert callable(whisper_key.main.main)


def test_background_launch_defers_interactive_gpu_setup():
    from whisper_key import main
    config = Mock(config={'onboarding': {'gpu': 'pending'}})
    settings = {'device': 'cpu', 'compute_type': 'int8'}
    with patch.object(main.sys, 'stdin', Mock(isatty=lambda: False)), patch.object(main, 'detect_hardware') as detect:
        assert main.run_gpu_onboarding(config, settings) is settings
        detect.assert_not_called()


def test_foreground_failure_preserves_text_without_injecting():
    from whisper_key.state_manager import StateManager
    manager = StateManager.__new__(StateManager)
    manager.logger = Mock()
    manager.system_tray = Mock()
    with patch('whisper_key.state_manager.foreground.get_foreground_app', side_effect=RuntimeError('locked')):
        assert manager._foreground_is_textable() is False
    manager.logger.exception.assert_called_once()
    manager.system_tray.notify.assert_called_once()


def test_state_controls_do_not_depend_on_overlay():
    from whisper_key.state_manager import StateManager
    manager = StateManager.__new__(StateManager)
    manager.system_tray = Mock()
    manager.terminal_title = Mock()
    manager.level_overlay = None
    with patch('whisper_key.platform.linux.bridge.call') as call:
        manager._update_ui_state('recording')
        call.assert_called_once_with('state', state='recording')


def test_nvidia_runtime_reexec_only_for_new_paths(monkeypatch):
    from whisper_key.platform.linux import gpu
    monkeypatch.setenv('LD_LIBRARY_PATH', '/existing')
    with patch.object(gpu, 'runtime_library_paths', return_value=['/cuda/lib']), patch.object(gpu.os, 'execv') as execv:
        gpu.prepare_runtime()
        assert os.environ['LD_LIBRARY_PATH'] == '/cuda/lib:/existing'
        execv.assert_called_once()
        execv.reset_mock()
        gpu.prepare_runtime()
        execv.assert_not_called()


def test_desktop_quote_with_real_glib_parser():
    import json
    import subprocess
    from whisper_key.autostart import _desktop_quote
    probe = subprocess.run(['/usr/bin/python3', '-c', 'from gi.repository import GLib'], capture_output=True)
    if probe.returncode:
        pytest.skip('System Python GLib is needed for desktop-entry parser integration')
    arguments = ['/path with spaces/python', 'a\\b"c$d`e', '100%literal', "single'quote"]
    entry = '[Desktop Entry]\nType=Application\nExec=' + ' '.join(map(_desktop_quote, arguments)) + '\n'
    result = subprocess.run(['/usr/bin/python3', '-c',
        'import sys,json; from gi.repository import GLib; k=GLib.KeyFile(); '
        'data=sys.stdin.read(); k.load_from_data(data, len(data.encode()), GLib.KeyFileFlags.NONE); '
        'print(json.dumps(GLib.shell_parse_argv(k.get_string("Desktop Entry", "Exec"))[1]))'],
        input=entry, capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == [arg.replace('%', '%%') for arg in arguments]
