# Session-local GNOME bridge. Imports and CLI utilities need no running desktop.
# A dedicated asyncio loop handles D-Bus calls from the app's worker threads.
import asyncio
import json
import threading

BUS = 'org.gnome.Shell'
PATH = '/org/gnome/Shell/Extensions/WhisperLocal'
INTERFACE = 'org.gnome.Shell.Extensions.WhisperLocal'
UUID = 'whisper-local@juicebox6030.github.io'
_loop = None
_bus = None
_lock = threading.Lock()
_connect_lock = None


async def _call(payload):
    global _bus, _connect_lock
    from dbus_next.aio import MessageBus
    from dbus_next import Message, MessageType
    if _connect_lock is None:
        _connect_lock = asyncio.Lock()
    async with _connect_lock:
        if _bus is None or not _bus.connected:
            _bus = await MessageBus().connect()
    reply = await _bus.call(Message(destination=BUS, path=PATH,
        interface=INTERFACE, member='Call', signature='s', body=[json.dumps(payload)]))
    if reply.message_type == MessageType.ERROR:
        raise RuntimeError(f'GNOME bridge: {reply.body}. Enable extension {UUID}; '
                           'a first installation may need logout/login.')
    result = json.loads(reply.body[0])
    if 'error' in result:
        raise RuntimeError(result['error'])
    return result.get('result')


def call(operation, **arguments):
    global _loop
    with _lock:
        if _loop is None:
            _loop = asyncio.new_event_loop()
            threading.Thread(target=_loop.run_forever, daemon=True,
                             name='gnome-dbus').start()
    future = asyncio.run_coroutine_threadsafe(_call(dict(op=operation, **arguments)), _loop)
    try:
        return future.result(timeout=5)
    except TimeoutError:
        future.cancel()
        raise RuntimeError('GNOME Shell bridge timed out') from None


def check():
    result = call('ping')
    if result.get('version') != 1:
        raise RuntimeError('Incompatible Whisper Local Shell extension; reinstall it.')
    return result
