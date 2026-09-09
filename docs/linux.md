# Linux / GNOME port

This experimental port adds a Linux backend while retaining the shared transcription and
automation pipeline and the existing Windows/macOS implementations. The initial
target is **Fedora 43, GNOME Shell 49, Wayland**. Other desktops and Shell versions
are not supported by this backend yet. This is a development port, not a claim
that every application and hardware combination has been validated.

## Install from this checkout

Install Fedora desktop/runtime dependencies:

```sh
sudo dnf install portaudio wl-clipboard libcxx libcxxabi ptyxis python3-gobject gtk4
uv tool install --force --python 3.13 --editable '.[loopback,noise]'
python3 tools/install-linux.py --enable
```

`libcxx`/`libcxxabi` are required by TEN VAD, not just GPU users. The managed
Python 3.13 supplied by uv includes Tk for settings/history/fallback dialogs.
If using a distro Python instead, install its matching Tk package too.
The editable install uses this checkout; keep it at the same path.

GNOME may not discover a newly installed extension until logout/login. Save
your work and log out normally; do not restart or kill a Wayland Shell. Then:

```sh
gnome-extensions enable whisper-local@juicebox6030.github.io
whisper-local --doctor
whisper-local --selftest
whisper-local
```

Installing an updated extension does not reload an already-running copy. Log
out/in after updating the extension, then check with `--doctor` again.
Startup fails visibly if the companion extension is unavailable. A headless
server can use utility/API commands, but cannot provide desktop dictation.

## Desktop behavior

- Hold **Ctrl+Super**, speak, then release to dictate. Toggle mode is also
  configurable. Key-containing shortcuts support both press and release.
- Hardware shortcuts can use a two-digit hexadecimal XKB keycode. For example,
  `hotkey.recording_hotkey: "super+shift+0xc9"` binds the Copilot key on keyboards
  that emit Super+Shift with keycode 201. Confirm your keyboard's events first;
  this is not a universal Copilot mapping and does not change the system keymap.
- **Escape** cancels while recording, including with the overlay disabled;
  ordinary application Escape is not grabbed while idle.
- **Ctrl+Shift+Super** invokes rephrase; **Alt+Super** invokes voice commands;
  **Ctrl+Alt+Super** pauses/unpauses the app. As with other modifier-only chord
  systems, press the distinguishing modifier before completing a shorter chord.
- The microphone panel menu exposes the shared menus: model, language, profile,
  device, recent transcripts, settings/history, diagnostics, and login startup.
  The native Shell recording pill does not take keyboard focus.
- GNOME virtual input works with native Wayland and XWayland applications.
  Unicode uses the input method when supported. The `type` backend falls back
  to clipboard paste when characters cannot be represented by the keymap;
  it restores the previous text clipboard. Clipboard-rich content is not
  preserved by upstream's text-only clipboard API.
- Desktop overview, Shell dialogs, and locked sessions reject automatic input.
  A failed focus probe does not cause blind typing. Dictation is retained via
  the shared fallback/error paths where possible. Window identity, **not field
  accessibility**, drives app rules; this is not password-field detection.
- Config lives at `$XDG_CONFIG_HOME/whisperkey` (default
  `~/.config/whisperkey`). Existing user files are never overwritten.
  Fresh voice-command defaults use GNOME apps and `xdg-open`; the Linux-only
  `hotkey: show_desktop` action minimizes windows on the current workspace,
  since GNOME assigns no Show Desktop shortcut by default.
- `--enable-autostart` / panel **Start on login** creates an XDG autostart entry.
  Autostart remains opt-in. Diagnostics opened from the panel use a terminal
  that stays open so the results can be read.

## Models and optional features

Local CPU inference, model selection, VAD, streaming, voice commands, transforms,
profiles, history, the HTTP API, local Ollama rephrase, and optional noise
suppression continue to use shared code. They have not been replaced by remote
services. Model downloads and explicitly configured external services still
require networking, as upstream does.

NVIDIA acceleration uses CTranslate2's Linux CUDA runtime. Onboarding can install
CUDA 12 / cuDNN 9 wheels into the active environment; the launcher re-execs once
with their library directories in `LD_LIBRARY_PATH` when needed. GPU detection
is not proof of successful model inference. Verify your configured GPU with
`--selftest`. The requirements follow
[faster-whisper's Linux GPU instructions](https://github.com/SYSTRAN/faster-whisper#gpu).

Windows-specific AMD ROCm wheel installation is **not** reused on Linux. AMD GPU
acceleration is not yet validated/supported by this port's automatic setup; use
CPU, or independently configure/test the optional whisper.cpp backend. Do not
interpret the Linux port as verified AMD acceleration parity.

System-audio capture uses SoundCard's PulseAudio-compatible monitor input
(including PipeWire's PulseAudio service), via `--transcribe-system SECONDS`.
This remains experimental and requires an actual available monitor device.

## Verification

```sh
uv venv --python 3.13
uv pip install -e '.[loopback,noise]' pytest
.venv/bin/pytest -q
node --check packaging/gnome/whisper-local@juicebox6030.github.io/extension.js
node --test tests/test_gnome_extension.cjs
dbus-run-session -- .venv/bin/python tools/test-gnome.py
```

`--desktop-only` runs the compositor and settings/history checks without full
audio application startup; it must not be reported as a full-app success.

GitHub Actions runs cross-platform smoke tests and a separate Ubuntu Linux
regression job with the installed Python package and mocked extension logic.
The Node tests do not run GNOME or inject input. The Fedora/GNOME 49 integration
command above remains a separate check, not part of the Ubuntu CI job.

The extension currently uses `whisper-local@juicebox6030.github.io`. Its final
upstream identifier/distribution is a maintainer decision; keep the directory,
metadata, installer, and Python bridge identifiers in sync if changing it.
The Python wheel alone does not install the companion extension: use this source
checkout and the installation steps above.

The compositor integration test runs a disposable, headless GNOME session with
its own D-Bus, settings, extension copy, and GTK Wayland text target. Test-only
input-driving operations are added only to that temporary copy. It checks
Unicode/replacement, clipboard preservation, hotkey edges, overlay-independent
cancel, Shell focus safety, and real app startup/shutdown. It needs the runtime
dependencies above; missing VAD libraries are a real failure, not skipped.
It does not substitute for a physical keyboard/microphone test in your normal
browser/editor, or independently validate every optional model and GPU backend.

To remove: stop Whisper Local, run `whisper-local --disable-autostart`,
`gnome-extensions uninstall whisper-local@juicebox6030.github.io`, then
`uv tool uninstall whisper-local`. Configuration and downloaded models remain.
