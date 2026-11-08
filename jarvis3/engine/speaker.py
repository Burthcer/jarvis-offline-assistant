"""Jarvis's voice out: V1's Kokoro/Piper speech code (voice.py, read as is) without its listening half. Replies are spoken sentence by sentence and can be cut off."""
import hashlib
import logging
import os
import queue
import re
import threading
import time

from jarvis3.legacy import voice as V

log = logging.getLogger("jarvis3.engine")
from jarvis3.paths import RUNTIME, PROJECT, ASSETS
ROOT = str(RUNTIME)
CACHE = os.path.join(ROOT, "data", "cache", "tts")
FIXED = ["Ready, sir.", "Paused, sir.", "Playing, sir.", "Next one, sir.", "Previous one, sir.", "Volume up, sir.", "Volume down, sir.", "Muted, sir.", "Unmuted, sir.",
         "Goodbye, sir.", "Very good, sir.", "Screenshot taken, sir.", "Full screen, sir.", "Skipping ahead, sir.", "Going back, sir.", "Timer removed, sir.", "Which one, sir?",
         "Which timer, sir?", "How long, sir?", "When, sir?", "Shall I go ahead, sir?", "Nothing is playing that I can control, sir.", "Already muted, sir.", "Typed, sir.",
         "Louder or quieter, sir?", "Speaking slower, sir.", "Speaking faster, sir.", "Speaking louder, sir.", "Speaking quieter, sir.", "Reminder removed, sir."]
GONE_MS = 500


class Speaker:
    def __init__(self, on_idle=lambda: None, volume=0.8, voice="jarvis", replies=None):
        self.on_idle = on_idle
        self.v = V.Voice(self._emit, volume=volume, listening=False, speak=True, watch=False, voice=voice, replies=replies)
        self.silent = os.environ.get("JARVIS_SILENT") == "1"            # tests: nothing may ever come out of the owner's speakers
        if self.silent:
            self.v.sink = lambda audio: None
        self.ready = False
        self.on_tune=lambda values:None
        self.cues=queue.Queue(maxsize=8)
        self.cue_busy=False
        self.cue_gate=threading.RLock()
        self.after_cues=[]
        self.cue_stop=False
        self.cue_thread=threading.Thread(target=self._cue_worker,daemon=True)
        self.cue_thread.start()

    def cue(self,kind,started=lambda:None,on_error=lambda:None):
        if not self.ready or self.silent:return False
        with self.cue_gate:
            try:self.cues.put_nowait((kind,started,on_error));self.cue_busy=True;return True
            except queue.Full:on_error();return False

    def _cue_worker(self):
        from jarvis3.feedback import cue_audio
        while not self.cue_stop:
            item=self.cues.get()
            if item is None:return
            kind,started,on_error=item
            try:
                if not self.output_available():raise RuntimeError('Windows output is muted or unavailable')
                from types import SimpleNamespace
                self.v._play(cue_audio(kind,self.v.sr),started=SimpleNamespace(set=started))
            except Exception:on_error()
            finally:
                if kind=='wake':self.on_idle()
                with self.cue_gate:
                    if self.cues.empty():
                        self.cue_busy=False
                        pending,self.after_cues=self.after_cues,[]
                        for text in pending:self.v.speak(text)

    def output_available(self):
        import comtypes
        from pycaw.pycaw import AudioUtilities
        comtypes.CoInitialize()
        try:
            endpoint=AudioUtilities.GetSpeakers().EndpointVolume
            return not endpoint.GetMute() and endpoint.GetMasterVolumeLevelScalar()>0
        finally:comtypes.CoUninitialize()

    def _emit(self, kind, payload=None):
        if kind == "state" and payload == "idle":
            self.on_idle()                       # the reply is over: ears allow a follow-up without the name
        elif kind in ("error", "status"):
            log.info("speaker %s: %s", kind, payload)

    def _disk_cache(self):
        """A sentence is made once ever: Kokoro takes 0.65 s per sentence, which is the delay the owner felt on every reply."""
        v, make = self.v, self.v._make
        os.makedirs(CACHE, exist_ok=True)

        def cached(text, speed=None):
            import numpy as np
            f = os.path.join(CACHE, hashlib.sha1(f"{v.voice_name}|{speed or v.speed}|{text}".encode()).hexdigest()[:24] + ".npy")
            if len(text) < 140 and os.path.exists(f):
                try:
                    return np.load(f)
                except Exception:
                    pass
            a = make(text, speed)
            if len(text) < 140:
                np.save(f, a)
            return a
        v._make = cached

    def premake(self, names, sites):
        """The sentences he hears most, made in the background the first time (then they come from disk): open/close each app and site, volume levels, the fixed ones."""
        phrases = list(FIXED)
        for n in names + sites:
            phrases += [f"Opening {n}, sir.", f"Closing {n}, sir."]
        phrases += [f"Volume set to {p} percent, sir." for p in range(5, 101, 5)]
        for text in phrases:
            if self.v.stop:
                return
            for part in [p for p in re.split(r"(?<=[.!?])\s+", V.speakable(text)) if p.strip()]:
                self.v._synth(part)

    def load(self):
        v, t = self.v, time.time()
        v._load_tts()
        self._disk_cache()
        v.clips = [v._synth(r, 1.3) for r in v.replies]           # "Yes, sir" and friends, made now so they start at once
        if not self.silent:
            v._open_out()
        v.ready = True
        v.loaded.set()
        self.speech_thread=threading.Thread(target=v._speaker, daemon=True)
        self.speech_thread.start()
        self.ready = True
        log.info("speaker ready in %.1fs", time.time() - t)

    @property
    def busy(self):
        return time.time() < self.v.quiet_until

    def speak(self, text):
        if self.cue_stop:return
        with self.cue_gate:
            if self.cue_busy:
                self.after_cues=(self.after_cues+[text])[-4:]
                return
        while self.v.speakq.qsize()>=4:
            try:self.v.speakq.get_nowait()
            except queue.Empty:break
        self.v.speak(text)

    def wake(self):
        """'Jarvis' alone: a ready-made 'Yes, sir' clip. -> milliseconds from the call to the sound reaching the speaker."""
        t0 = time.perf_counter()
        self.v.stats.pop("yes_ms", None)
        clip = self.v._pick_clip()
        self.v.cut = False
        self.v.quiet_until = time.time() + 600
        started = threading.Event()

        def go():
            try:
                self.v._play(clip, t0=t0, started=started)
            finally:
                self.v.quiet_until = time.time() + 0.5
                self.on_idle()
        threading.Thread(target=go, daemon=True).start()
        started.wait(2)
        return self.v.stats.get("yes_ms")

    def close_out(self):
        """Let go of the sound device (it is reopened by the next sentence): PortAudio is about to restart because the default device changed."""
        with self.v.out_lock:
            try:
                self.v.out and self.v.out.close()
            except Exception:
                pass
            self.v.out = None

    def tune(self, change):
        v = self.v
        if change in ("slower", "faster"):
            v.set_speed(round(v.speed + (0.1 if change == "faster" else -0.1),2))
        else:
            v.set_volume(round(v.volume + (0.1 if change == "louder" else -0.1),2))
        self.on_tune({'tts_speed':v.speed,'tts_volume':v.volume})
        return True

    def stop(self):
        """Cut the reply off now (a new command, or 'shut up')."""
        self.v.cut = True
        with self.cue_gate:self.after_cues.clear()
        try:
            while True:
                self.v.speakq.get_nowait()
        except queue.Empty:
            pass

    def shutdown(self):
        self.ready=False
        self.cue_stop=True
        self.v.cut=True
        try:self.cues.put_nowait(None)
        except queue.Full:pass
        self.v.shutdown()
        for thread in (self.cue_thread,getattr(self,'speech_thread',None)):
            if thread and thread is not threading.current_thread():thread.join(1)
        self.close_out()
