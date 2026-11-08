"""Hands-free Jarvis V4 (plan 13.9): ears -> App.handle -> speaker. One worker turns what was heard into actions, so a slow command never stops the ears.
A new command while Jarvis is talking cuts the reply off (he hears himself only through the canceller, never through text filters)."""
import logging
import queue
import threading
import time

from .ears import Ears, LoopRing, MicStream, Transcriber
from .speaker import Speaker

log = logging.getLogger("jarvis3.engine")


class VoiceApp:
    def __init__(self, app, show=print, clips_dir=None):
        self.app, self.show, self.q = app, show, queue.Queue()
        self.speaker = Speaker(on_idle=lambda: None)      # no-name follow-ups open only after the wake reply (the ears do that themselves)
        app.speech = self.speaker                      # "shut up" reaches the speaker through ctx.speech
        self.stt, self.ears, self.clips_dir = Transcriber(), None, clips_dir
        self.stats = {}
        self.expect_answer = False

    def _reply_over(self):
        if self.ears and self.ears.armed_until > 0 and (self.ears.wake_pending or self.expect_answer):
            self.ears.arm(since=self.ears.armed_from)
        self.expect_answer = False

    def start(self):
        t0 = time.time()
        self.show("Loading my ears and voice...")
        self.stt.load()
        self.speaker.load()
        loop = LoopRing()                               # what the PC plays, to subtract it from the mic
        self.ears = Ears(MicStream(self.speaker.close_out), loop, self.stt, self.q.put, hint=self._hint, clips_dir=self.clips_dir)
        self.ears.is_complete = self.app.is_complete
        self.speaker.on_idle = self._reply_over
        self.ears.start()
        self.app.set_mic = self._set_mic
        threading.Thread(target=self._work, daemon=True).start()
        threading.Thread(target=self._idle_unload, daemon=True).start()
        threading.Thread(target=self._alerts, daemon=True).start()
        threading.Thread(target=self._offers, daemon=True).start()
        self.show(f"Ready, sir ({time.time() - t0:.0f} s). Say 'Jarvis' first, then your command.")
        self.speaker.speak("Ready, sir.")

    def _set_mic(self, on):
        self.ears.paused_until = 0.0 if on else time.monotonic() + 600
        return True

    def _alerts(self):
        """Timers and reminders that come due are spoken (the owner: spoken aloud, no toast)."""
        from datetime import datetime

        from jarvis3.legacy.core import announce_due
        while True:
            time.sleep(3)
            try:
                for line in announce_due(self.app.store, datetime.now()):
                    self.show(f"[alert] {line}")
                    self.speaker.speak(line)
            except Exception:
                log.exception("alert check failed")

    def _offers(self):
        """A habit is offered as a question (never done on its own), only when Jarvis is quiet and nobody is mid-conversation."""
        while True:
            time.sleep(60)
            try:
                if not self.speaker.busy and self.q.empty():
                    line = self.app.offer()
                    if line:
                        self.show(f"[offer] {line}")
                        self.speaker.speak(line)
            except Exception:
                log.exception("habit offer failed")

    def _hint(self):
        return self.app.names.hint()

    def _work(self):
        while True:
            h = self.q.get()
            if h is None:
                return
            try:
                self.expect_answer = False
                if not h.text:                          # "Jarvis" alone
                    ms = self.speaker.wake()
                    self.stats["yes_ms"] = ms
                    self.show(f"[wake] heard {h.raw!r}; 'Yes, sir' after {ms} ms")
                    continue
                if self.speaker.busy:
                    self.speaker.stop()                 # barge-in
                r = self.app.handle(h.text, trigger=h.trigger, clip_id=h.clip_id)
                self.show(f"[{h.trigger}] {h.text!r} -> {r.text or '(silent)'}  ({r.plan.source or r.plan.kind}; heard in {h.stt_ms} ms, +{h.wait_ms} ms wait, understood in {r.ms['understand']} ms)")
                if r.text:
                    self.expect_answer = bool(r.plan.kind == 'ask' or self.app.pending)
                    if self.expect_answer:
                        self.ears.arm(since=h.ended)
                    self.ears.remember_reply(r.text)
                    self.speaker.speak(r.text)
            except Exception:
                log.exception("turn failed")
                self.show("Something went wrong with that, sir (details are in logs/jarvis3.engine.log).")

    def _idle_unload(self):
        while True:
            time.sleep(60)
            if self.app.maybe_unload():
                log.info("AI unloaded after idling")

    def stop(self):
        self.ears and self.ears.shutdown()
        self.q.put(None)
        self.speaker.shutdown()
