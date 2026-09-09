# Linux lifecycle and terminal input. Desktop processes inherit their session;
# utility commands do not discover or attach to another graphical session.
import subprocess
import sys
import shutil


def setup():
    pass


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
