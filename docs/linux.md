# Linux (GNOME / Wayland)

The Linux backend targets **Fedora 43 with GNOME Shell 49 on Wayland**.
Other desktops and Shell versions are not supported yet. Transcription,
settings, history, profiles, voice commands and model management use the same
Python application as Windows and macOS. A bundled GNOME extension supplies
global hotkeys, foreground-window detection, text delivery, panel menus and
the recording overlay without taking focus from the application.

## Installation

Linux uses the normal Python package, like macOS; there is no separate binary.
For this unreleased port, download/build the wheel from the Linux branch:

```sh
sudo dnf install portaudio wl-clipboard libcxx libcxxabi python3-tkinter
python3 -m venv .venv
.venv/bin/pip install ./whisper_local-*.whl
.venv/bin/whisper-local --install-gnome-extension
```

Alternatively, install the source with `.venv/bin/pip install .` (not editable).
Neither installation needs the checkout afterwards. Once released, the normal
`pip install whisper-local` command will include the Linux integration too.
Optional extras remain `[loopback,noise]`. TEN VAD needs `libcxx`/`libcxxabi`
even for CPU inference. Install Tk matching your Python for the shared dialogs.

Save your work and log out/in normally after installing or updating the
extension; do not restart or kill a Wayland Shell. If activation was deferred:

```sh
gnome-extensions enable whisper-local@juicebox6030.github.io
.venv/bin/whisper-local --doctor
.venv/bin/whisper-local --setup
.venv/bin/whisper-local
```

Extension installation is explicit and per-user. Upgrading the Python package
does not replace a running extension: repeat `--install-gnome-extension` and
log out/in. Startup reports missing integration; imports and utility/API
commands do not require it. Autostart remains opt-in via the panel or
`--enable-autostart`.

## Desktop behavior and limits

- Hold **Ctrl+Super** to dictate; release to insert. Toggle mode is configurable.
  **Escape** cancels only while recording, including with the overlay disabled.
- **Ctrl+Shift+Super** rephrases, **Alt+Super** invokes voice commands, and
  **Ctrl+Alt+Super** pauses. For modifier-only chords, press the distinguishing
  modifier before completing a shorter chord.
- Panel menus expose the shared actions. Settings/history/fallback use the
  existing Tk dialogs. Diagnostics use a terminal (Ptyxis or GNOME Terminal).
- Text delivery supports native Wayland and XWayland. Unicode falls back to
  paste where needed, restoring the previous text clipboard. Rich clipboard
  contents are not preserved by the shared text-only clipboard API.
- Locked sessions, the overview and Shell dialogs reject automatic input.
  Failed focus probes retain text through fallback/error handling, not blind
  typing. Window identity drives app rules; this is not password-field detection.
- Settings use `$XDG_CONFIG_HOME/whisperkey`, default `~/.config/whisperkey`.
  Existing settings/commands are not overwritten. New voice-command defaults
  use Linux apps; `show_desktop` minimizes windows on the current workspace.
- CPU inference is validated. NVIDIA CUDA 12/cuDNN 9 setup is supported but
  GPU inference is not validated; check your hardware with `--selftest`.
  Automatic AMD GPU setup is not supported. System-audio capture remains
  experimental and requires a PulseAudio/PipeWire monitor input.

Stop the app before `--uninstall`: its existing confirmation flow removes
settings/autostart and separately offers GNOME extension and model removal.
Then use `pip uninstall whisper-local` to remove the Python package.

## Development verification

```sh
python3 -m pip install build
python3 -m build
.venv/bin/pip install -e '.[loopback,noise]' pytest
.venv/bin/python -m unittest tests.test_smoke
.venv/bin/pytest -q
node --test tests/test_gnome_extension.cjs
dbus-run-session -- .venv/bin/python tools/test-gnome.py
```

The integration harness needs GNOME 49 plus system Python GTK4 bindings
(`python3-gobject gtk4` on Fedora). It uses a disposable compositor, private
D-Bus, temporary settings and an extension copy; test-only input operations
never ship in the extension. It checks hotkey hold/release, cancellation,
Unicode/replacement, clipboard preservation, Shell focus safety, shared
settings/history windows, and full audio app startup/shutdown.
`--desktop-only` skips full audio startup and must not be called a full-app pass.
Physical microphone/keyboard testing remains necessary for a new desktop;
these checks do not certify every GPU, model or optional backend.
