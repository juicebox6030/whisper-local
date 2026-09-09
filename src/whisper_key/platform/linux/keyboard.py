# GNOME's virtual keyboard delivers into native Wayland and XWayland clients.
# A single bridge request keeps a chord together; the Shell releases every key.
from .bridge import call
import time
import threading
import pyperclip

_delay = 0.0
_input_lock = threading.RLock()


def validate_delivery_method(method):
    if method not in ('paste', 'type'):
        raise ValueError(f'Unknown delivery method: {method}')
    return method


def set_delay(delay):
    global _delay
    _delay = max(0, float(delay))


def send_key(key):
    send_hotkey(key)


def send_hotkey(*keys):
    with _input_lock:
        if keys == ('show_desktop',):
            call('show-desktop')
            return
        call('keys', keys=list(keys), delay=_delay)


def type_text(text):
    with _input_lock:
        _type_text(text)


def _type_text(text):
    # Chunk long text to keep Shell's main loop responsive.
    for offset in range(0, len(text), 128):
        chunk = text[offset:offset + 128]
        if call('text', text=chunk) is False:
            previous = pyperclip.paste()
            try:
                pyperclip.copy(chunk)
                time.sleep(0.05)
                send_hotkey('ctrl', 'v')
                time.sleep(0.2)
            finally:
                pyperclip.copy(previous)
