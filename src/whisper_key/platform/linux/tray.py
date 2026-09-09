# A small pystray-compatible menu adapter sends the existing menu tree to GNOME.
# Callbacks stay in Python; the extension receives only labels and opaque IDs.
from . import bridge, hotkeys


class Menu:
    SEPARATOR = object()

    def __init__(self, *items):
        self.items = items


class MenuItem:
    def __init__(self, text, action, **options):
        self.text, self.action, self.options = text, action, options

    def value(self, name, default):
        value = self.options.get(name, default)
        return value(self) if callable(value) else value


class Icon:
    def __init__(self, name, icon, title, menu):
        self._menu, self._title, self._icon = menu, title, icon
        self._running = False
        self._callbacks = {}
        self._revision = 0

    def _publish(self):
        self._revision += 1
        callbacks = {}

        def serialize(menu):
            items = []
            for item in menu.items:
                if item is Menu.SEPARATOR:
                    items.append({'separator': True})
                    continue
                if not item.value('visible', True):
                    continue
                key = f'{self._revision}:{len(callbacks)}'
                callbacks[key] = item
                label = item.text(item) if callable(item.text) else item.text
                data = dict(id=key, label=label, enabled=bool(item.value('enabled', True)),
                            checked=item.value('checked', None), radio=item.value('radio', False))
                if isinstance(item.action, Menu):
                    data['children'] = serialize(item.action)
                items.append(data)
            return items

        tree = serialize(self._menu)
        # Install callback IDs before Shell can send a click on the new menu.
        self._callbacks = callbacks
        bridge.call('menu', items=tree, title=self._title)

    def _activate(self, event):
        item = self._callbacks.get(event['id'])
        if item and item.value('enabled', True) and callable(item.action):
            item.action(self, item)
            if self._running:
                self._publish()

    @property
    def menu(self):
        return self._menu

    @menu.setter
    def menu(self, menu):
        self._menu = menu
        if self._running:
            self._publish()

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        self._title = value
        if self._running:
            bridge.call('title', title=value)

    @property
    def icon(self):
        return self._icon

    @icon.setter
    def icon(self, value):
        self._icon = value

    def run_detached(self):
        bridge.check()
        hotkeys._handlers['menu'] = self._activate
        self._running = True
        self._publish()
        hotkeys.start()

    def notify(self, message, title='Whisper Local'):
        bridge.call('notify', title=title, message=message)

    def stop(self):
        self._running = False
        hotkeys._handlers.pop('menu', None)
        bridge.call('menu', items=[], title='Whisper Local (stopped)')
