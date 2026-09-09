# GNOME renders the recording pill without creating or focusing a client window.
# Keep the shared LevelOverlay API so streaming and error feedback stay intact.
import logging
import threading
import time
from .bridge import call


class LevelOverlay:
    def __init__(self, level_provider, click_through=True, position='bottom-center'):
        self.level_provider = level_provider
        self.position = position
        self._mode = 'hidden'
        self._text = ''
        self._until = 0
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name='gnome-overlay')
        self._thread.start()

    def _run(self):
        previous = None
        while not self._stop.wait(0.04):
            if self._until and time.monotonic() >= self._until:
                self.hide()
            data = dict(mode=self._mode, text=self._text, position=self.position,
                        level=max(0, min(1, float(self.level_provider()) * 25)))
            if data == previous:
                continue
            try:
                call('overlay', **data)
                previous = data
            except Exception:
                logging.getLogger(__name__).exception('GNOME overlay unavailable')
                self._stop.wait(1)

    def show_recording(self):
        self._mode, self._until = 'recording', 0

    def show_processing(self):
        self._mode, self._until = 'processing', 0

    def hide(self):
        self._mode, self._text, self._until = 'hidden', '', 0

    def flash_success(self):
        self._mode, self._until = 'success', time.monotonic() + 0.4

    def flash_failure(self, message=None):
        self._mode, self._text = 'failure', message or 'Transcription failed'
        self._until = time.monotonic() + 3

    def set_streaming_text(self, text):
        self._text = text or ''

    def set_position(self, name):
        self.position = name

    def shutdown(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        call('overlay', mode='hidden', text='', position=self.position, level=0)
