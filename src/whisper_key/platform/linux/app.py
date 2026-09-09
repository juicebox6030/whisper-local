# Linux lifecycle and terminal input. Desktop environment is inherited from
# the session manager when a coding-agent shell omitted display variables.
import os
import subprocess
import sys
import shutil


def setup():
    if not os.environ.get('WAYLAND_DISPLAY'):
        try:
            result = subprocess.run(['systemctl', '--user', 'show-environment'],
                                    capture_output=True, text=True, timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            return
        for line in result.stdout.splitlines():
            key, _, value = line.partition('=')
            if key in {'DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'XDG_SESSION_TYPE', 'XDG_CURRENT_DESKTOP'}:
                os.environ.setdefault(key, value)


def open_terminal(command):
    # Pass argv, not user/config text interpolated into a shell command.
    # The short wrapper holds the window open so diagnostics remain readable.
    held = ['sh', '-c', '"$@"; printf "\\nPress Enter to close…"; read -r answer', 'whisper-local', *command]
    for binary, options in [('ptyxis', ['--new-window', '--']),
                            ('gnome-terminal', ['--']), ('x-terminal-emulator', ['-e'])]:
        if shutil.which(binary):
            return subprocess.Popen([binary, *options, *held])
    raise RuntimeError('Install ptyxis or gnome-terminal to open diagnostics from the panel')


def run_event_loop(shutdown_event):
    shutdown_event.wait()


def getch():
    if not sys.stdin.isatty():
        return sys.stdin.read(1)
    import termios
    import tty
    fd = sys.stdin.fileno()
    original = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original)
