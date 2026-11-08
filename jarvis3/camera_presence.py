"""Opt-in webcam movement watcher for the arrival greeting.

It detects MOVEMENT in front of the camera after a long still period. It does
not recognise a person, a face or a hand. Frames are never stored or sent.
The detector is one function (`motion`) so a face or ring model can replace it.
"""
import threading
import time

import numpy as np

ABSENT_S = 600       # no movement this long = nobody there
INTERVAL_S = 2.0     # one small frame every two seconds: a few ms of CPU
CONFIRM = 2          # consecutive moving samples before "someone is here"
THRESHOLD = 6.0      # mean absolute change (0-255) between two small grey frames
RETRY_S = 120        # camera missing or busy: try again later, say so once


def motion(previous, frame, threshold=THRESHOLD):
    if previous is None or previous.shape != frame.shape:
        return False
    return float(np.mean(np.abs(frame.astype(np.int16) - previous.astype(np.int16)))) >= threshold


def small_grey(frame):
    import cv2
    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    return cv2.GaussianBlur(cv2.resize(grey, (160, 120)), (5, 5), 0)


def open_camera():
    import cv2
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release(); return None
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


class CameraPresence:
    def __init__(self, opener=open_camera, clock=time.monotonic, interval=INTERVAL_S, absent_after=ABSENT_S, confirm=CONFIRM, prepare=small_grey):
        self.opener, self.clock, self.interval, self.absent_after, self.confirm, self.prepare = opener, clock, interval, absent_after, confirm, prepare
        self.status = 'off'; self.samples = 0; self.on_frame = None; self.presence_every = interval; self._last_observe = -1e9
        self._stop = threading.Event(); self._thread = None; self._lock = threading.Lock()
        self._arrived = False; self._present = True; self._last_motion = clock(); self._streak = 0; self._previous = None

    @property
    def present(self):
        return self._present

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name='jarvis-v3-camera', daemon=True); self._thread.start()

    def take(self):
        """One arrival event, consumed."""
        with self._lock:
            arrived, self._arrived = self._arrived, False
        return arrived

    def observe(self, frame):
        """Pure state machine on one frame: present -> absent after ABSENT_S still -> present again = arrival."""
        now = self.clock(); grey = self.prepare(frame); self.samples += 1
        moved = motion(self._previous, grey); self._previous = grey
        self._streak = self._streak + 1 if moved else 0
        if self._streak >= self.confirm:
            if not self._present:
                self._present = True
                with self._lock:
                    self._arrived = True
            self._last_motion = now
        elif self._present and now - self._last_motion >= self.absent_after:
            self._present = False

    def _run(self):
        cap = None
        try:
            while not self._stop.is_set():
                if cap is None:
                    cap = self.opener()
                    if cap is None:
                        self.status = 'unavailable'
                        if self._stop.wait(RETRY_S):
                            break
                        continue
                    self.status = 'watching'
                ok, frame = cap.read()
                if not ok or frame is None:
                    cap.release(); cap = None; self.status = 'unavailable'; continue
                if self.on_frame:
                    self.on_frame(frame)
                if self.clock() - self._last_observe >= self.presence_every:
                    self._last_observe = self.clock(); self.observe(frame)
                if self._stop.wait(self.interval):
                    break
        finally:
            if cap is not None:
                cap.release()
            self.status = 'off'

    def close(self):
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(5)
