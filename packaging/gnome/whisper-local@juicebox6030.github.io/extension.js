// GNOME 49 desktop integration for Whisper Local. The Python application owns
// audio/models/actions; this bridge owns compositor-only operations and UI.
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const PATH = '/org/gnome/Shell/Extensions/WhisperLocal';
const XML = `<node><interface name="org.gnome.Shell.Extensions.WhisperLocal">
<method name="Call"><arg name="request" type="s" direction="in"/>
<arg name="response" type="s" direction="out"/></method></interface></node>`;
const MODS = {ctrl: 4, control: 4, shift: 1, alt: 8, option: 8,
    win: 64, windows: 64, super: 64, cmd: 64, command: 64};
const MOD_NAMES = {1: '<Shift>', 4: '<Control>', 8: '<Alt>', 64: '<Super>'};
const KEYS = {ctrl: 'Control_L', control: 'Control_L', shift: 'Shift_L',
    alt: 'Alt_L', option: 'Alt_L', win: 'Super_L', windows: 'Super_L',
    super: 'Super_L', cmd: 'Super_L', command: 'Super_L', esc: 'Escape',
    escape: 'Escape', enter: 'Return', return: 'Return', backspace: 'BackSpace',
    delete: 'Delete', tab: 'Tab', space: 'space', home: 'Home', end: 'End',
    left: 'Left', right: 'Right', up: 'Up', down: 'Down',
    pageup: 'Page_Up', pagedown: 'Page_Down', insert: 'Insert', print: 'Print'};

function keyName(key) {
    key = key.trim().toLowerCase();
    return KEYS[key] ?? (/^f\d+$/.test(key) ? key.toUpperCase() : key);
}

function keyval(key) {
    const value = Clutter[`KEY_${keyName(key)}`];
    if (value === undefined)
        throw new Error(`Unknown key: ${key}`);
    return value;
}

export default class WhisperLocal extends Extension {
    enable() {
        this._bindings = [];
        this._events = [];
        this._generation = 0;
        this._owner = null;
        this._ownerWatch = 0;
        this._injectUntil = 0;
        this._suppressed = 0;
        this._state = 'idle';
        this._keyboard = Clutter.get_default_backend().get_default_seat()
            .create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);
        this._indicator = new PanelMenu.Button(0.0, 'Whisper Local');
        this._icon = new St.Icon({icon_name: 'audio-input-microphone-symbolic',
            style_class: 'system-status-icon'});
        this._indicator.add_child(this._icon);
        Main.panel.addToStatusArea(this.uuid, this._indicator);
        this._indicator.hide();
        this._overlay = new St.BoxLayout({reactive: false, can_focus: false,
            style: 'background-color: #0d1117; color: #c9d1d9; padding: 10px; border-radius: 14px;'});
        this._label = new St.Label({text: ''});
        this._overlay.add_child(this._label);
        Main.layoutManager.addChrome(this._overlay, {affectsInputRegion: false});
        this._overlay.hide();
        this._activated = global.display.connect('accelerator-activated',
            (_display, action) => this._accelerator(action, true));
        this._deactivated = global.display.connect('accelerator-deactivated',
            (_display, action) => this._accelerator(action, false));
        this._timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 20, () => {
            this._pollModifiers();
            return GLib.SOURCE_CONTINUE;
        });
        this._dbus = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this._dbus.export(Gio.DBus.session, PATH);
    }

    // Tie desktop resources to the app's bus connection, including crash cleanup.
    async CallAsync([raw], invocation) {
        try {
            const request = JSON.parse(raw);
            const sender = invocation.get_sender();
            if (!['ping', 'foreground'].includes(request.op)) {
                if (this._owner && this._owner !== sender)
                    throw new Error('Another Whisper Local client owns the desktop bridge');
                if (!this._owner) {
                    this._owner = sender;
                    this._ownerWatch = Gio.bus_watch_name_on_connection(Gio.DBus.session,
                        sender, Gio.BusNameWatcherFlags.NONE, null, () => this._disconnect());
                }
            }
            const result = await this._call(request);
            invocation.return_value(new GLib.Variant('(s)', [JSON.stringify({result})]));
        } catch (error) {
            invocation.return_value(new GLib.Variant('(s)', [JSON.stringify({error: error.message})]));
        }
    }

    _call(r) {
        switch (r.op) {
        case 'ping': return {version: 1, desktop: 'GNOME', locked: Main.sessionMode.isLocked};
        case 'register': return this._register(r.bindings, r.generation, r.recordingOnly ?? []);
        case 'poll': return this._events.splice(0);
        case 'foreground': {
            if (Main.sessionMode.isLocked)
                throw new Error('Desktop is locked');
            const window = global.display.focus_window;
            if (!window || Main.overview.visible || global.stage.key_focus)
                return {};
            const app = Shell.WindowTracker.get_default().get_window_app(window);
            return {exe: (window.get_wm_class() ?? app?.get_id() ?? '').toLowerCase(),
                path: '', title: window.get_title() ?? '', pid: window.get_pid()};
        }
        case 'keys': {
            return this._sendChord(r.keys.map(keyval), r.delay);
        }
        case 'show-desktop': {
            this._checkInput();
            for (const window of global.workspace_manager.get_active_workspace().list_windows()) {
                if (!window.skip_taskbar && window.can_minimize()) window.minimize();
            }
            return true;
        }
        case 'text': {
            this._checkInput();
            if (r.text.length > 1024)
                throw new Error('Text chunk too large');
            this._injectUntil = GLib.get_monotonic_time() + 150000;
            if (Main.inputMethod.currentFocus) {
                Main.inputMethod.commit(r.text);
                return true;
            }
            // Raw virtual events cannot type symbols absent from the keymap.
            // Request Python's clipboard-preserving fallback before typing anything.
            if (/[^\x09\x0a\x20-\x7e]/u.test(r.text)) return false;
            return this._typeAscii(r.text);
        }
        case 'menu': this._menu(r); return true;
        case 'title': this._indicator.accessible_name = r.title; return true;
        case 'notify': Main.notify(r.title, r.message); return true;
        case 'overlay': this._showOverlay(r); return true;
        case 'state': this._setState(r.state); return true;
        default: throw new Error(`Unknown bridge operation: ${r.op}`);
        }
    }

    _checkInput() {
        if (Main.sessionMode.isLocked || Main.sessionMode.currentMode !== 'user')
            throw new Error('Keyboard delivery requires an unlocked user session');
        if (Main.overview.visible || global.stage.key_focus)
            throw new Error('Keyboard delivery requires a focused application, not Shell UI');
    }

    _settle(milliseconds = 5) {
        return new Promise(resolve => GLib.timeout_add(GLib.PRIORITY_DEFAULT, milliseconds, () => {
            resolve();
            return GLib.SOURCE_REMOVE;
        }));
    }

    async _sendChord(values, delay = 0) {
        this._checkInput();
        const pressed = [];
        this._injectUntil = Number.MAX_SAFE_INTEGER;
        try {
            for (const value of values) {
                this._keyboard.notify_keyval(GLib.get_monotonic_time(), value, Clutter.KeyState.PRESSED);
                pressed.push(value);
                await this._settle(Math.max(5, Math.min(100, delay * 1000)));
            }
        } finally {
            for (const value of pressed.reverse()) {
                this._keyboard?.notify_keyval(GLib.get_monotonic_time(), value, Clutter.KeyState.RELEASED);
                await this._settle();
            }
            this._injectUntil = GLib.get_monotonic_time() + 100000;
        }
        return true;
    }

    async _typeAscii(text) {
        for (const char of text) {
            const value = char === '\n' ? Clutter.KEY_Return : char === '\t' ? Clutter.KEY_Tab : char.codePointAt(0);
            await this._sendChord([value]);
        }
        return true;
    }

    _releaseBindings() {
        for (const b of this._bindings) {
            if (b.action) {
                Main.wm.allowKeybinding(Meta.external_binding_name_for_action(b.action), Shell.ActionMode.NONE);
                global.display.ungrab_accelerator(b.action);
            }
        }
        this._bindings = [];
        this._suppressed = 0;
    }

    _register(bindings, generation, recordingOnly) {
        const parsed = bindings.map((text, index) => {
            let mask = 0;
            const keys = [];
            for (const part of text.toLowerCase().split('+').map(s => s.trim())) {
                if (MODS[part]) mask |= MODS[part];
                else keys.push(keyName(part));
            }
            if (keys.length > 1 || (!keys.length && !mask))
                throw new Error(`Invalid hotkey: ${text}`);
            if (keys.length) keyval(keys[0]);
            const prefix = Object.entries(MOD_NAMES).filter(([bit]) => mask & Number(bit))
                .map(([, name]) => name).join('');
            return {index, mask, key: keys[0], accelerator: prefix + (keys[0] ?? ''),
                recordingOnly: recordingOnly.includes(index), down: false};
        });
        this._releaseBindings();
        this._events = this._events.filter(e => e.type !== 'hotkey');
        this._generation = generation;
        this._bindings = parsed;
        try {
            for (const b of parsed) {
                // Gate the cancel role, not the key name: custom cancel keys and
                // Escape used as a recording shortcut must also work correctly.
                if (b.key && !b.recordingOnly) this._grab(b);
            }
            this._setState(this._state);
        } catch (error) {
            this._releaseBindings();
            throw error;
        }
        return true;
    }

    _grab(b) {
        b.action = global.display.grab_accelerator(b.accelerator,
            Meta.KeyBindingFlags.TRIGGER_RELEASE | Meta.KeyBindingFlags.IGNORE_AUTOREPEAT);
        if (!b.action) throw new Error(`Hotkey unavailable or reserved: ${b.accelerator}`);
        Main.wm.allowKeybinding(Meta.external_binding_name_for_action(b.action), Shell.ActionMode.NORMAL);
    }

    _emit(b, pressed) {
        if (b.down === pressed) return;
        b.down = pressed;
        this._events.push({type: 'hotkey', index: b.index, pressed, generation: this._generation});
        if (this._events.length > 256) this._events.shift();
    }

    _accelerator(action, pressed) {
        if (Main.sessionMode.isLocked || GLib.get_monotonic_time() < this._injectUntil) return;
        const b = this._bindings.find(binding => binding.action === action);
        if (b) this._emit(b, pressed);
    }

    _pollModifiers() {
        if (Main.sessionMode.isLocked) {
            for (const b of this._bindings) if (b.down) this._emit(b, false);
            this._overlay.hide();
            return;
        }
        if (GLib.get_monotonic_time() < this._injectUntil) return;
        const raw = global.get_pointer()[2];
        const mask = (raw & (1 | 4 | 8 | 64)) | (raw & (1 << 26) ? 64 : 0);
        this._suppressed &= mask;
        // Suppress leftover modifiers only on physical release, not when a
        // larger chord is being assembled (Ctrl followed by Super). Compute
        // this before emitting so binding order cannot affect subset behavior.
        for (const b of this._bindings) {
            if (!b.key && b.down && (b.mask & ~mask))
                this._suppressed |= b.mask & mask;
        }
        for (const b of this._bindings) {
            if (b.key) continue;
            if (b.recordingOnly && this._state !== 'recording') continue;
            const down = mask === b.mask && (this._suppressed & b.mask) === 0;
            this._emit(b, down);
        }
    }

    _menu(r) {
        this._indicator.menu.removeAll();
        this._indicator.accessible_name = r.title;
        const append = (menu, items) => {
            for (const data of items) {
                if (data.separator) {
                    menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
                    continue;
                }
                const item = data.children ? new PopupMenu.PopupSubMenuMenuItem(data.label) :
                    new PopupMenu.PopupMenuItem(data.label);
                item.setSensitive(data.enabled);
                if (data.checked)
                    item.setOrnament(data.radio ? PopupMenu.Ornament.DOT : PopupMenu.Ornament.CHECK);
                menu.addMenuItem(item);
                if (data.children) append(item.menu, data.children);
                else item.connect('activate', () => this._events.push({type: 'menu', id: data.id}));
            }
        };
        append(this._indicator.menu, r.items);
        this._indicator.visible = r.items.length > 0;
    }

    _setState(state) {
        this._state = state;
        const recording = state === 'recording';
        for (const b of this._bindings.filter(b => b.recordingOnly)) {
            if (!b.key) {
                if (!recording) b.down = false;
                continue;
            }
            if (recording && !b.action) this._grab(b);
            if (!recording && b.action) {
                global.display.ungrab_accelerator(b.action);
                Main.wm.allowKeybinding(Meta.external_binding_name_for_action(b.action), Shell.ActionMode.NONE);
                b.action = 0;
                b.down = false;
            }
        }
        this._icon.set_style(recording ? 'color: #3fb950' :
            state === 'processing' ? 'color: #e3b341' : '');
    }

    _showOverlay(r) {
        const recording = r.mode === 'recording';
        if (r.mode === 'hidden' || Main.sessionMode.isLocked) {
            this._overlay.hide();
            return;
        }
        const bars = '▰'.repeat(Math.round(r.level * 8)).padEnd(8, '▱');
        const text = r.text || (recording ? 'Listening…' : r.mode === 'processing' ? 'Transcribing…' : 'Done');
        this._label.text = `${recording ? bars + '  ' : ''}${text.slice(-80)}`;
        this._overlay.show();
        const monitor = Main.layoutManager.primaryMonitor;
        if (!monitor) return;
        const width = this._overlay.get_preferred_width(-1)[1];
        const height = this._overlay.get_preferred_height(width)[1];
        const x = r.position.endsWith('left') ? monitor.x + 24 :
            r.position.endsWith('right') ? monitor.x + monitor.width - width - 24 :
            monitor.x + (monitor.width - width) / 2;
        const y = r.position.startsWith('top') ? monitor.y + 60 : monitor.y + monitor.height - height - 80;
        this._overlay.set_position(Math.round(x), Math.round(y));
    }

    _disconnect() {
        if (this._ownerWatch) Gio.bus_unwatch_name(this._ownerWatch);
        this._ownerWatch = 0;
        this._owner = null;
        this._releaseBindings();
        this._state = 'idle';
        this._events = [];
        this._overlay.hide();
        this._indicator.hide();
    }

    disable() {
        this._dbus?.unexport();
        if (this._timer) GLib.Source.remove(this._timer);
        global.display.disconnect(this._activated);
        global.display.disconnect(this._deactivated);
        this._disconnect();
        Main.layoutManager.removeChrome(this._overlay);
        this._overlay.destroy();
        this._indicator.destroy();
        this._keyboard = null;
    }
}
