#!/usr/bin/env python3
# Native Wayland GTK test target. Only writes its own entry contents to a temp
# result file supplied by the isolated compositor test harness.
import sys
from pathlib import Path
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

result = Path(sys.argv[1])
app = Gtk.Application(application_id='io.github.juicebox6030.WhisperProbe')


def activate(application):
    window = Gtk.ApplicationWindow(application=application, title='Whisper Linux integration probe')
    entry = Gtk.Entry()
    keys = Gtk.EventControllerKey()
    keys.connect('key-pressed', lambda _c, keyval, keycode, state: print('KEY', keyval, keycode, int(state), flush=True) or False)
    entry.add_controller(keys)
    entry.connect('changed', lambda widget: result.write_text(widget.get_text(), encoding='utf-8'))
    window.set_child(entry)
    window.set_default_size(600, 120)
    window.present()
    entry.grab_focus()


app.connect('activate', activate)
app.run([])
