## Structure

```
platform/
├── __init__.py        # sets `IS_MACOS` / `IS_WINDOWS` / `IS_LINUX` and imports
└── {macos,windows,linux}/
    ├── assets/        # platform-specific assets
    └── *.py           # modules (mirrored API)
```

Module Contract:
- Mirrored with identical API (no-ops OK)
- Imported in `__init__.py`
- No-op stubs are valid when a platform doesn't need the functionality 

## Usage

```python
from .platform import keyboard, hotkeys, app, paths, icons  # prefer
from .platform import IS_MACOS, IS_WINDOWS  # sparingly
```

The Linux backend requires the companion GNOME 49 extension for desktop
operations. `linux.bridge` owns a session D-Bus connection; keyboard, hotkeys,
foreground, panel menus, and overlays use its JSON request/reply protocol.
The extension owns compositor resources only while that client is connected.
CLI imports remain usable without a compositor. See [Linux](linux.md) for setup,
runtime dependency checks and isolated-compositor integration testing.
