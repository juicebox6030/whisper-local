import platform as _platform

# Resolve the platform once at import time. Whisper Local officially supports
# Windows, macOS, and Linux/GNOME have independent desktop implementations.
# Runtime permissions are checked at startup, not during utility imports.
_system = _platform.system()
if _system == 'Darwin':
    PLATFORM = 'macos'
elif _system == 'Windows':
    PLATFORM = 'windows'
elif _system == 'Linux':
    PLATFORM = 'linux'
else:
    PLATFORM = 'unsupported'

IS_MACOS = PLATFORM == 'macos'
IS_WINDOWS = PLATFORM == 'windows'
IS_LINUX = PLATFORM == 'linux'

# Only import the current operating system's native integration dependencies.
if IS_MACOS:
    from .macos import instance_lock, keyboard, hotkeys, paths, app, permissions, icons, gpu, console, foreground
elif IS_WINDOWS:
    from .windows import instance_lock, keyboard, hotkeys, paths, app, permissions, icons, gpu, console, foreground
elif IS_LINUX:
    from .linux import instance_lock, keyboard, hotkeys, paths, app, permissions, icons, gpu, console, foreground
