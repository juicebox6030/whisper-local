# Poll only registered shortcut transitions, never arbitrary user keystrokes.
# Dispatch off the D-Bus loop so callbacks may safely call other bridge methods.
import logging
import threading
from . import bridge

_bindings = []
_thread = None
_stop = threading.Event()
_generation = 0
_handlers = {}
_lock = threading.RLock()


def register(bindings, recording_only=None):
    global _bindings, _generation
    with _lock:
        _generation += 1
        _bindings = list(bindings)
        conditional = [i for i, b in enumerate(_bindings)
                       if b[0].lower().strip() == (recording_only or '').lower().strip()]
        bridge.call('register', bindings=[b[0] for b in _bindings],
                    recordingOnly=conditional, generation=_generation)


def dispatch(event):
    if event['type'] == 'hotkey':
        with _lock:
            if event.get('generation') != _generation:
                return
            index = event['index']
            if not 0 <= index < len(_bindings):
                return
            binding = _bindings[index]
            callback = binding[1 if event['pressed'] else 2]
        if callback:
            callback()
    else:
        callback = _handlers.get(event['type'])
        if callback:
            callback(event)


def _run():
    while not _stop.wait(0.02):
        try:
            for event in bridge.call('poll'):
                dispatch(event)
        except Exception:
            logging.getLogger(__name__).exception('Linux desktop event processing failed')
            if _stop.wait(1):
                break


def start():
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_run, daemon=True, name='gnome-events')
    _thread.start()


def stop():
    _stop.set()
    bridge.call('register', bindings=[], generation=_generation)
    if _thread and _thread is not threading.current_thread():
        _thread.join(timeout=2)
