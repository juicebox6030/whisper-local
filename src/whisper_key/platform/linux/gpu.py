# Probe the actual CTranslate2 runtime rather than Windows DLL locations.
# CPU is always available; unavailable GPU runtimes remain explicit in output.
import shutil
import subprocess
import os
import sys
from pathlib import Path


def runtime_library_paths():
    # NVIDIA pip wheels keep libraries outside the dynamic loader's search path.
    directories = []
    for entry in sys.path:
        for component in ('cuda_runtime', 'cublas', 'cudnn'):
            directory = Path(entry) / 'nvidia' / component / 'lib'
            if directory.is_dir() and str(directory) not in directories:
                directories.append(str(directory))
    return directories


def prepare_runtime():
    # LD_LIBRARY_PATH must be present before Python starts (glibc snapshots it).
    # Re-exec only when new wheel paths exist, never on ordinary module imports.
    previous = os.environ.get('LD_LIBRARY_PATH', '').split(os.pathsep)
    missing = [path for path in runtime_library_paths() if path not in previous]
    if missing:
        os.environ['LD_LIBRARY_PATH'] = os.pathsep.join(missing + [p for p in previous if p])
        os.execv(sys.executable, [sys.executable, '-m', 'whisper_key.main', *sys.argv[1:]])


def detect_and_print(configured_device):
    name = None
    if shutil.which('nvidia-smi'):
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                name = result.stdout.strip().splitlines()[0] if result.stdout.strip() else None
        except (OSError, subprocess.TimeoutExpired):
            pass
    try:
        import ctranslate2
        works = bool(ctranslate2.get_supported_compute_types('cuda'))
    except Exception:
        works = False
    if name:
        print(f'   NVIDIA: {name}; CTranslate2 GPU ready: {works}')
        return 'nvidia', name, works
    print(f'   Linux CTranslate2 GPU ready: {works}; configured device: {configured_device}')
    return (None, None, works)
