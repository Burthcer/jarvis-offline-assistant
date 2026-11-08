"""Voice (M4): wake word -> spoken "Yes, sir" -> listen -> speech-to-text -> text goes to the same handle() as typing.
All offline. One background thread listens; the UI only receives events: emit(kind, payload).
Kinds: ready, status, state, wake, near, heard, error."""
import collections
import ctypes
import difflib
import glob
import os
import queue
import random
import re
import subprocess
import sys
import threading
import time

import numpy as np

from . import actions

SR, CHUNK = 16000, 1280  # mic rate; 80 ms per step (what the wake model expects)
WAKE = "hey_jarvis_v0.1"
THRESH, VERIFY = 0.5, 0.10  # score that wakes at once / weaker score that must be confirmed by the speech model first
EXPECT = "Jarvis."  # told to the speech model when checking who is being spoken to. On the owner's real clips: "Jarvis" written right 7/7, against "Got this", "Generous"... without it
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPLIES = ["At your service, sir.", "Yes, sir.", "I'm listening, sir."]
PIPER = os.path.join(ROOT, "data", "models", "piper", "en_GB-alan-medium.onnx")
# the owner's Wisperno models are only ever READ from here, never changed or moved
WHISPER_GLOBS = [r"C:\Users\USER\Desktop\Wisperno-pro\models\models--mobiuslabsgmbh--faster-whisper-large-v3-turbo\snapshots\*",
                 os.path.expandvars(r"%LOCALAPPDATA%\Programs\Wisperno\models\models--mobiuslabsgmbh--faster-whisper-large-v3-turbo\snapshots\*")]
CUDA_LIBS = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Wisperno\_internal\torch\lib")  # cublas for the GPU, read-only
PROMPT = "Vocabulary: Jarvis, remind me, reminder, timer, tomorrow, YouTube, YouTube Music, LinkedIn, dev.to, Luma, Gemini, Netflix, Amazon, Claude, Claude console, ChatGPT, Antigravity, Wispr Flow, Wisperno Pro, IHatePDF, Obsidian, Task Manager, volume, mute, lo-fi."
# Wisperno's own settings: trim the silence first, so Whisper can't invent "Thank you" out of nothing (and has less to read: faster)
VAD = {"threshold": 0.35, "min_speech_duration_ms": 150, "min_silence_duration_ms": 1200, "speech_pad_ms": 500}
JUNK = {"you", "thank you", "thanks", "thank you.", "thanks for watching", "bye", "."}


VOICE = {"length": 1.06, "noise": 0.85, "noise_w": 1.0}  # Piper (fallback voice) settings
KOKORO = (os.path.join(ROOT, "data", "models", "kokoro", "kokoro-v1.0.onnx"), os.path.join(ROOT, "data", "models", "kokoro", "voices-v1.0.bin"))
# Kokoro sounds far more human than Piper. British male voices; "piper_alan" = the old robotic-ish fallback.
VOICES = {"jarvis": "Jarvis style (calm, polished: default)", "bm_george": "George (deep, refined)", "bm_fable": "Fable (warm)", "bm_lewis": "Lewis", "bm_daniel": "Daniel", "piper_alan": "Alan (old voice)"}


def _cuda():
    """Make the GPU libraries visible to the speech model. Returns True if they loaded."""
    try:
        os.environ["PATH"] = CUDA_LIBS + os.pathsep + os.environ["PATH"]
        os.add_dll_directory(CUDA_LIBS)
        for n in ("cublasLt64_12.dll", "cublas64_12.dll"):
            ctypes.WinDLL(os.path.join(CUDA_LIBS, n))
        return True
    except OSError:
        return False


def _fast(kind):
    """Windows' low-delay audio route (WASAPI, ~3 ms instead of ~90-180 ms): kwargs for a sounddevice stream, or {} to use the default."""
    try:
        import sounddevice as sd
        h = next(h for h in sd.query_hostapis() if h["name"] == "Windows WASAPI")
        return {"device": h[f"default_{kind}_device"], "latency": "low", "extra_settings": sd.WasapiSettings(auto_convert=True)}
    except Exception:
        return {}


# how the speech recogniser actually wrote the owner's "Jarvis" (from his saved clips)
ALIASES = {"charles", "charlie", "travis", "darvis", "darviss", "jervis", "javis", "jarvas", "jarviss", "jarves", "jairus", "jarvish", "jarbis", "jarvee", "jarvi", "jarvie", "jarvy", "harvis", "hervis", "charvis", "garvis"}


def _jarvisish(w):
    """jarvis, jervis, charvis, garvis, darvis... (accents and mishearings)"""
    return bool(w) and (w in ALIASES or (w[0] != "s" and re.search(r"r[vbf]+[aeiouy]*[szx]h?$|^[jgdy][ae]+i?r+[aeiou]+s$", w) is not None)  # the heart of the name: -rvis, -rbis, -rvous, garrus, jairus...
                        or (w[0] in "jgcyhsdt" and difflib.SequenceMatcher(None, w, "jarvis").ratio() >= 0.72))


def is_wake(text):
    """Does the transcript contain 'Jarvis' anywhere?"""
    return any(_jarvisish(w) for w in re.findall(r"[a-z]+", text.lower()))


GREET = {"hey", "hi", "ok", "okay", "yo", "hello", "a", "oh", "hay", "hei", "eh", "hiya"}


def after_wake(text):
    """'Hey Jarvis, open YouTube' -> 'open YouTube'; 'Jarvis.' -> ''; None if the sentence doesn't START with the name
    (so 'my friend Jarvis lives in Pune' is not for us)."""
    toks = text.split()
    for i, t in enumerate(toks[:2]):  # the name as one word first: "Hey Jarvis, open YouTube" must keep "open"
        w = re.sub(r"[^a-z]", "", t.lower())
        if _jarvisish(w) and (i == 0 or re.sub(r"[^a-z]", "", toks[0].lower()) in GREET):
            return " ".join(toks[i + 1:]).strip(" ,.!?")
    best = None  # the name split into pieces: "A jar is open Luma", "Hey jar vis open..."; the best-fitting split wins
    for n in (2, 3):
        joined = re.sub(r"[^a-z]", "", "".join(toks[:n]).lower())
        r = max(difflib.SequenceMatcher(None, joined, "jarvis").ratio() - 0.78, difflib.SequenceMatcher(None, joined, "heyjarvis").ratio() - 0.8)
        if len(toks) >= n and r >= 0 and (best is None or r > best[0]):
            best = (r, n)
    return " ".join(toks[best[1]:]).strip(" ,.!?") if best else None


# complete commands that need nothing more: acted on the moment they are understood
QUICK = re.compile(r"volume (?:up|down|\d+)|(?:un)?mute|pause|resume|next (?:song|track)|(?:set )?(?:a )?timer for .*\b(?:seconds?|minutes?|hours?)")
MORE = re.compile(r"remind me .+|what do (?:i|we) have\b.*|what's on .+|set a timer\b.*|search .+")
NOT_FOR_US = {"i", "i'll", "i'm", "you", "you'll", "we", "we'll", "we're", "he", "she", "they", "it", "it's", "to", "can", "can't", "could", "should", "would",
              "will", "won't", "don't", "did", "didn't", "let's", "lets", "and", "but", "or", "if", "when", "then", "the", "a", "not", "never", "must", "might",
              "also", "so", "now", "okay", "ok", "alright", "right", "actually", "just", "please", "maybe", "yeah", "yes", "no", "well", "like", "hmm", "um", "uh"}


def _plain(cmd):
    return re.sub(r"[.,!?]+", "", cmd).strip().lower()


def _complete(cmd):
    return bool(cmd) and (actions.direct(cmd) is not None or QUICK.fullmatch(_plain(cmd)) is not None)


def rescue(text):
    """The name got misheard but a clear command follows: 'Harness, open YouTube' -> 'open YouTube'. The words in front must at least
    SOUND a bit like the name, so a command said to nobody ('Also open YouTube', 'open YouTube') is not taken."""
    toks = text.split()
    for i in (1, 2, 3):
        cmd = " ".join(toks[i:]).strip(" ,.!?")
        said = [re.sub(r"[^a-z']", "", t.lower()) for t in toks[:i]]
        if said[-1:] and said[-1] in NOT_FOR_US:
            return None
        if _complete(cmd) or MORE.fullmatch(_plain(cmd)):
            name = "".join(w for w in said if w not in GREET)
            return cmd if len(name) >= 3 and difflib.SequenceMatcher(None, name, "jarvis").ratio() >= 0.4 else None
    return None


DAYS = dict(zip("Mon Tue Wed Thu Fri Sat Sun".split(), "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()))
MONTHS = dict(zip("Jan Feb Mar Apr Jun Jul Aug Sep Oct Nov Dec".split(), "January February March April June July August September October November December".split()))
# words that mean "I'm not finished": if a command ends on one, keep listening a little longer
DANGLING = re.compile(r"\b(?:to|at|for|on|in|by|the|a|an|and|about|of|with|then|until|till|after|before|open|search|play|remind me|set a timer)$")


def _master(a):
    """Make a reply properly loud: bring it to full level with a gentle limiter (no harsh clipping). float -1..1 -> int16."""
    if not len(a):
        return np.zeros(0, dtype=np.int16)
    a = np.asarray(a, dtype=np.float32) / (np.abs(a).max() + 1e-9) * 1.6
    return (np.tanh(a) / np.tanh(1.6) * 32000).astype(np.int16)


def _sheen(a, sr):
    """A faint polished, synthetic room (a few very short echoes), like a film AI. Subtle on purpose."""
    out = np.array(a, dtype=np.float32)
    for ms, g in ((11, 0.22), (23, 0.12), (37, 0.06)):
        d = int(sr * ms / 1000)
        out[d:] += g * np.asarray(a, dtype=np.float32)[:-d]
    return out


def speakable(text):
    """Written reply -> what sounds natural when read aloud."""
    t = re.sub(r"#\d+\s*", "", text)
    t = re.sub(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b", lambda m: DAYS[m[1]], t)
    t = re.sub(r"\b(Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", lambda m: MONTHS[m[1]], t)
    t = re.sub(r"\b(\d{1,2}):00\b", r"\1", t)  # 5:00 pm -> 5 pm
    t = re.sub(r"\b(\d{1,2}):(\d{2})\b", r"\1 \2", t)
    t = re.sub(r"(\d)\s?([ap])m\b", lambda m: f"{m[1]} {m[2].upper()} M", t)  # read the letters: P M
    t = re.sub(r"(\d)-(\w)", r"\1 \2", t)  # 10-minute -> 10 minute
    t = re.sub(r"\s*\n\s*", ". ", t)
    t = re.sub(r"[*_`|]", "", t)
    return re.sub(r"\.\s*\.", ".", t)[:600]


class Voice:
    def __init__(self, emit, volume=0.8, speed=1.0, listening=True, speak=True, watch=True, replies=None, voice="jarvis"):
        self.emit, self.volume, self.speed, self.listening, self.talk, self.watch = emit, volume, speed, listening, speak, watch
        self.voice_name = voice if voice in VOICES else "jarvis"
        self.kokoro, self.tts_lock = None, threading.Lock()
        self.replies = self._tidy(replies)
        self.level = 0.0  # live mic loudness 0..1, read by the UI
        self.ready = False
        self.stop = False
        self.quiet_until = 0.0  # don't listen while we (or just after we) speak: we'd hear ourselves
        self.stats = {}
        self.sink = None  # tests: a function that receives audio instead of the speakers
        self.mic = None  # tests: an object with read(n) -> (array, overflow)
        self.out, self.out_lock, self.loaded = None, threading.Lock(), threading.Event()
        self.speakq = queue.Queue()
        self.devices = None
        self.dev_changed = False
        self.said = []  # (time, text) of what Jarvis recently said: if the mic "hears" it back, that's me, not the user
        self.last_clip = -1  # never use the same wake reply twice in a row
        self.followup = False  # set by the UI when Jarvis's reply is a question
        self.nf = 60.0  # the room's background noise level (rms): speech has to be clearly louder
        self.rms_hist = collections.deque(maxlen=75)  # last 6 s of loudness, to learn nf (up OR down: the mic level can change any time)
        self.gain = 1.0  # laptop mics are quiet: recordings are boosted so the speech detector and Whisper get a healthy signal
        self.cache = {}  # (text, voice, speed) -> ready-made audio
        self.prewarm = None  # set by the app: wakes the AI's GPU when someone starts talking
        self._warmed = 0.0
        self.cut = False  # a new command arrived: stop the reply that is playing

    def _remember(self, text):
        self.said = (self.said + [(time.time(), re.sub(r"[^a-z ]", "", text.lower()))])[-8:]

    def _is_echo(self, text):
        t = re.sub(r"[^a-z ]", "", text.lower()).strip()
        return len(t) >= 12 and any(time.time() - when < 25 and len(s) >= 6 and (t in s or s in t or difflib.SequenceMatcher(None, t, s).ratio() > 0.75)
                                   for when, s in self.said)

    def _pick_clip(self):
        i = random.choice([k for k in range(len(self.clips)) if k != self.last_clip] or [0])
        self.last_clip = i
        self._remember(self.replies[i])
        return self.clips[i]

    def _boost(self, x):
        return np.clip(x.astype(np.float32) * self.gain, -32768, 32767).astype(np.int16)

    def _speech(self, x):
        """Is someone speaking in this chunk? Needs the detector's vote (boosted first; 0.35 because far-field laptop mics read weak)
        AND to be clearly louder than the room's background noise."""
        vote = self.vad.predict(self._boost(x), frame_size=640) > 0.35
        return bool(vote) and float(np.sqrt(np.mean(x.astype(np.float32) ** 2))) > max(1.8 * self.nf, 90)

    def _read(self, s):
        data, _ = s.read(CHUNK)
        x = data[:, 0]
        self.level = float(np.sqrt(np.mean(x.astype(np.float32) ** 2))) / 32768
        return x

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()
        threading.Thread(target=self._speaker, daemon=True).start()

    def shutdown(self):
        self.stop = True
        self.speakq.put(None)

    # ---- settings the user can change by voice or in settings ----
    def set_volume(self, v):
        self.volume = min(1.0, max(0.2, v))

    def set_speed(self, s):
        self.speed = min(1.6, max(0.6, s))

    @staticmethod
    def _tidy(replies):
        return [r.strip().rstrip(".!") + "." for r in (replies or REPLIES) if r.strip()] or REPLIES

    def set_replies(self, replies):
        self.replies = self._tidy(replies)
        if self.ready:
            self.clips = [self._synth(r, 1.3) for r in self.replies]
            self.last_clip = -1

    def set_listening(self, on):
        self.listening = on
        self.emit("status", "Microphone listening for 'Hey Jarvis'." if on else "Microphone is OFF: I'm not listening.")

    # ---- loading ----
    def _load(self):
        t = time.time()
        self.emit("status", "Voice: loading models (a few seconds)...")
        gpu = _cuda()
        from faster_whisper import WhisperModel
        path = next(iter(sum((glob.glob(g) for g in WHISPER_GLOBS), [])), None)
        if not path:
            raise RuntimeError("speech model not found in the Wisperno folder")
        try:
            if not gpu:
                raise RuntimeError("no gpu libs")
            self.stt, self.device = WhisperModel(path, device="cuda", compute_type="int8_float16"), "GPU"  # int8: ~half the GPU memory, leaves room for the AI
        except Exception:
            self.stt, self.device = WhisperModel(path, device="cpu", compute_type="int8"), "CPU (slow)"
        self._load_tts()
        import openwakeword
        from openwakeword.model import Model
        from openwakeword.vad import VAD
        self.oww = Model(wakeword_models=[os.path.join(openwakeword.__path__[0], "resources", "models", WAKE + ".onnx")], inference_framework="onnx")
        self.vad = VAD()
        self.clips = [self._synth(r, 1.3) for r in self.replies]  # pre-made so "Yes, sir" starts instantly; brisk so it is over quickly and rarely overlaps the user
        self.stt.transcribe(np.zeros(SR, dtype=np.float32), language="en")  # first call is slow: do it now
        if self.sink is None:
            try:
                self._open_out()  # open the speaker now so the very first "Yes, sir" is instant
            except Exception:
                pass
        self.stats["load_s"] = round(time.time() - t, 1)
        self.ready = True
        self.loaded.set()
        if self.sink is None:
            threading.Thread(target=self._premake, daemon=True).start()

    def _load_tts(self):
        """Kokoro (human-sounding) if its files are here, else Piper."""
        self.kokoro = None
        if self.voice_name != "piper_alan" and all(os.path.isfile(f) for f in KOKORO):
            try:
                from kokoro_onnx import Kokoro
                self.kokoro, self.sr = Kokoro(*KOKORO), 24000
                return
            except Exception as e:
                self.emit("status", f"Human voice failed to load ({str(e)[:60]}); using the old voice.")
        from piper import PiperVoice
        self.tts = PiperVoice.load(PIPER)
        self.sr = self.tts.config.sample_rate

    def set_voice(self, name):
        if name not in VOICES or name == self.voice_name:
            return
        self.voice_name = name
        if self.ready:
            with self.tts_lock:
                self._load_tts()
            with self.out_lock:  # the sample rate may have changed: reopen the speaker
                try:
                    self.out and self.out.close()
                except Exception:
                    pass
                self.out = None
            self.clips = [self._synth(r, 1.3) for r in self.replies]

    def _synth(self, text, speed=None):
        """Cached: the same reply ("Volume up, sir.") is made once (~0.65 s of work) and then starts instantly."""
        key = (text, self.voice_name, speed or self.speed)
        if key not in self.cache:
            if len(self.cache) > 300:
                self.cache.clear()
            self.cache[key] = self._make(text, speed)
        return self.cache[key]

    def _premake(self):
        """Make the most common replies in the background right after loading, so even the first one starts at once."""
        from .actions import BYE, SITES, _name
        common = [f"Opening {_name(k)} in {b.title()}, sir." for k, (b, _, _) in SITES.items()] + [
            f"{verb} {n}, sir." for n in ("Claude", "ChatGPT", "Antigravity", "Wispr Flow", "Wisperno Pro", "IHatePDF", "Obsidian", "Task Manager", "YouTube", "Discord", "WhatsApp") for verb in ("Opening", "Closing")] + [
            BYE, "Volume up, sir.", "Volume down, sir.", "Muted, sir.", "Unmuted, sir.", "Next track, sir.", "Previous track, sir.",
            "Paused, sir.", "Playing, sir.", "Timer cancelled, sir.", "Up or down, sir?", "Very well, sir.", "My pleasure, sir.",
            "At your service, sir.", "Opening Chrome, sir.", "Opening Edge, sir.", "Opening Notepad, sir.", "Opening Calculator, sir."]
        for text in common:
            for part in re.split(r"(?<=[.!?])\s+", speakable(text)):
                if self.stop:
                    return
                self._synth(part)

    def _make(self, text, speed=None):
        if self.kokoro is not None:
            jarvis = self.voice_name == "jarvis"
            if jarvis and getattr(self, "_style", None) is None:  # a blend of the two smoothest British voices
                self._style = 0.6 * self.kokoro.get_voice_style("bm_george") + 0.4 * self.kokoro.get_voice_style("bm_fable")
            with self.tts_lock:  # 0.95 (0.9 for the Jarvis style) = a touch calmer than Kokoro's default pace
                a, _ = self.kokoro.create(text, voice=self._style if jarvis else self.voice_name,
                                          speed=min(2.0, max(0.5, (0.9 if jarvis else 0.95) * (speed or self.speed))), lang="en-gb")
            return _master(_sheen(a, self.sr) if jarvis else a)
        from piper import SynthesisConfig
        # noise_scale / noise_w_scale = how much the pitch and rhythm vary (factory 0.667 / 0.8 sounds flat); length 1.06 = a calmer pace
        cfg = SynthesisConfig(length_scale=VOICE["length"] / (speed or self.speed), noise_scale=VOICE["noise"], noise_w_scale=VOICE["noise_w"])
        a = np.frombuffer(b"".join(c.audio_int16_bytes for c in self.tts.synthesize(text, syn_config=cfg)), dtype=np.int16)
        return _master(a.astype(np.float32) / 32768)

    # ---- speaking ----
    def _open_out(self):
        import sounddevice as sd
        for kw in (_fast("output"), {}):  # the fast route first, the plain default if it won't open
            try:
                self.out = sd.OutputStream(samplerate=self.sr, channels=1, dtype="int16", **kw)
                self.out.start()
                self.stats["device_ms"] = round(self.out.latency * 1000)
                return
            except Exception:
                self.out = None
        raise RuntimeError("no sound output")

    def _play(self, audio, t0=None, started=None, cut=False):
        """Play int16 audio at the voice's rate (blocks until queued). Sets `started` and stats['yes_ms'] right before the audio goes to the device."""
        x = (audio.astype(np.float32) * self.volume).clip(-32768, 32767).astype(np.int16)
        if self.sink is not None:
            if t0:
                self.stats["yes_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            started and started.set()
            for i in range(0, len(x), self.sr // 10):
                if cut and self.cut:
                    return
                self.sink(x[i:i + self.sr // 10])
            return
        with self.out_lock:
            for _ in range(2):
                try:
                    if self.out is None:
                        self._open_out()
                    if t0:
                        self.stats["yes_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                    started and started.set()
                    for i in range(0, len(x), self.sr // 10):  # small pieces: a reply can be cut off when a new command arrives
                        if cut and self.cut:
                            return
                        if self.out.write(x[i:i + self.sr // 10]):
                            self.stats["gaps"] = self.stats.get("gaps", 0) + 1
                    return
                except Exception:  # device went away (unplugged earphones): reopen on the new default
                    try:
                        self.out and self.out.close()
                    except Exception:
                        pass
                    self.out = None
        started and started.set()
        raise RuntimeError("can't play sound")

    def speak(self, text):
        if self.talk and text:
            said = speakable(text)
            self._remember(said)
            self.quiet_until = time.time() + 600  # don't listen from the moment we start to speak (the speaker thread shortens this when done)
            self.speakq.put(said)

    def _speaker(self):
        self.loaded.wait()
        while not self.stop:
            text = self.speakq.get()
            if text is None:
                return
            self.quiet_until = time.time() + 600  # until we finish
            self.cut = False
            try:  # sentence by sentence, so the first one starts almost at once
                for part in [p for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]:
                    if self.cut:
                        break
                    self._play(self._synth(part), cut=True)
            except Exception as e:
                self.emit("error", f"Couldn't speak: {e}")
            if self.speakq.empty():
                self.quiet_until = time.time() + 0.5  # room echo and the speaker's tail die away
                self.emit("state", "idle")

    # ---- listening ----
    def _run(self):
        try:
            self._load()
        except Exception as e:
            self.emit("error", f"Voice failed to load: {e}")
            return
        self.emit("ready", self.device)
        self.emit("status", "Microphone listening for 'Hey Jarvis'." if self.listening else "Microphone is OFF: I'm not listening.")
        if self.watch:
            threading.Thread(target=self._watch_devices, daemon=True).start()
        while not self.stop:
            try:
                if self.mic is not None:
                    self._loop(self.mic)
                    return
                import sounddevice as sd
                if self.dev_changed:  # PortAudio only notices a new default device after a restart
                    with self.out_lock:
                        sd._terminate(); sd._initialize()
                s = sd.InputStream(samplerate=SR, channels=1, dtype="int16", blocksize=CHUNK)  # ponytail: the fast route gave the mic no gain (160 ms vs 80 ms)
                s.start()
                try:
                    self.dev_changed = False
                    self._loop(s)
                finally:
                    s.close()
            except Exception as e:  # mic unplugged or blocked: say so and try again
                self.emit("status", f"Microphone problem ({str(e)[:80]}). Retrying...")
                time.sleep(2)

    def _loop(self, s):
        """Listen in whole sentences: Jarvis reacts at the END of what you say, never in the middle.
        A sentence is for Jarvis if the wake model fired in it, or the speech model hears "Jarvis" at its start."""
        pre = collections.deque(maxlen=12)  # ~1 s from just before speech is noticed, so a softly spoken "Jarvis" isn't cut off
        seg, voiced, quiet, fired, best = [], 0, 0, None, 0.0
        guess, spoke = None, False
        while not self.stop and not self.dev_changed:
            x = self._read(s)
            busy = time.time() < self.quiet_until  # we are talking: keep listening (back-to-back commands), our voice just doesn't count as background
            if not busy:
                self.rms_hist.append(self.level * 32768)
                if len(self.rms_hist) % 5 == 0:  # the quietest fifth of the last 6 s = the room's background level
                    self.nf = max(20.0, float(np.percentile(self.rms_hist, 20)))
            if not self.listening:
                seg, fired, best = [], None, 0.0
                pre.clear()
                continue
            if self.followup and not busy:  # Jarvis just asked a question: listen for the answer, no "Jarvis" needed
                self.followup, seg, fired, best = False, [], None, 0.0
                self.emit("state", "listening")
                self.oww.reset()
                self._warmed = 0.0
                self._wake_gpu()  # the answer comes in a moment: have the GPU ready (a cold one took ~1 s for "up")
                self._finish(s, self._capture(s, wait=7, short=2))  # 2: a one-word answer ("up") can be that short
                continue
            score = float(max(self.oww.predict(x).values(), default=0.0))
            talk = self._speech(x) or score >= 0.3
            if not seg:
                if not talk:
                    pre.append(x)
                    continue
                seg, voiced, quiet, fired, best = list(pre) + [x], 1, 0, None, score
                guess, spoke = None, busy
                pre.clear()
                self._wake_gpu()
            else:
                seg.append(x)
                best = max(best, score)
                # once someone is talking, a gentler test: quiet words in the middle of a sentence must not split it
                talk = talk or self._loud(x, 1.5, 70)
                voiced, quiet = (voiced + 1, 0) if talk else (voiced, quiet + 1)
                spoke = spoke or busy
            if score >= THRESH and fired is None:
                fired = voiced  # how much had been said when the wake model fired
            if quiet == 0:
                guess = None  # still talking: an earlier guess is out of date
            elif quiet == 3 and voiced >= 3:  # a short pause: start writing it down NOW, it is probably the end
                guess = self._guess(seg, fired)
            # end of the sentence: a complete command understood during the pause, 0.4 s of quiet (0.56 s if the wake model hasn't fired), or 8 s of talk
            if (guess and self._finished(guess.get("text"))) or quiet >= (5 if fired is not None else 7) or len(seg) > 8 * SR // CHUNK:
                done, seg = seg, []
                if voiced >= 3:  # shorter = a click or a cough
                    self._sentence(s, done, best, fired, voiced, spoke, guess)
                self.oww.reset()

    def _guess(self, seg, fired):
        out = {}
        audio = np.concatenate(seg)
        out["job"] = threading.Thread(target=lambda: out.setdefault("text", self._stt(audio) if fired is not None else self._heard(audio)), daemon=True)
        out["job"].start()
        return out

    def _finished(self, text):
        """Did that pause end a complete command for us? Then there is nothing to wait for."""
        if not text:
            return False
        text = self._strip_echo(text)
        return _complete(after_wake(text)) or _complete(rescue(text))

    def _sentence(self, s, seg, best, fired, voiced, spoke=False, guess=None):
        t0 = time.perf_counter()
        audio = np.concatenate(seg)
        peak = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2))) * 2
        if peak > 120:
            self.gain = float(np.clip(3000 / peak, 1, 6))
        if fired is not None and voiced - fired <= 2:  # just "Jarvis" / "Hey Jarvis": answer straight away
            return self._wake_reply(s, t0, best, "model")
        if fired is None and not spoke and len(audio) > 6 * SR:  # long talk the wake model never noticed: not for us
            return
        # ponytail: every short sentence in the room gets one quick GPU transcription (~0.2 s); fine for one person, revisit if a TV runs all day
        if guess:
            guess["job"].join(3)
        text = (guess or {}).get("text")
        text = self._strip_echo(text if text is not None else self._stt(audio) if fired is not None else self._heard(audio))
        cmd = after_wake(text)
        if cmd is None and spoke:  # our own reply may be in front: "Opening YouTube, sir. Jarvis, open Netflix"
            toks = text.split()
            at = next((i for i, t in enumerate(toks) if _jarvisish(re.sub(r"[^a-z]", "", t.lower()))), None)
            if at is None:
                return  # only our own voice
            cmd = after_wake(" ".join(toks[at:]))
        if cmd is None:
            cmd = rescue(text)
        if cmd is None:
            if fired is None:  # nobody said "Jarvis" at the start
                close = any(difflib.SequenceMatcher(None, w, "jarvis").ratio() >= 0.55 for w in re.findall(r"[a-z]+", text.lower()))
                if best >= VERIFY or close:  # log and keep it: if it WAS "Jarvis", this shows how it got misheard
                    self.emit("near", {"score": round(best, 2), "heard": text})
                if best >= VERIFY or close or len(text.split()) <= 6:
                    self._keep(audio, best, text)
                return
            cmd = re.sub(r"^\W*(?:hey|hi|ok|okay|yo|hello)\b[\s,.!?]*", "", text)  # the wake model was sure; the name was just misspelled
        if self._is_echo(cmd):  # our own sentence coming back through the mic ("I'm afraid X isn't on my list")
            return
        via = "model" if fired is not None else "check"
        if not re.search(r"[a-z]{2}", cmd, re.I) and fired is None and voiced * CHUNK / SR > 1.3:
            # "Jarvis" was heard but the rest got lost (weak signal): a second, vocabulary-guided listen of the same sentence
            cmd = after_wake(self._strip_echo(self._stt(audio))) or cmd
        if not re.search(r"[a-z]{2}", cmd, re.I) or cmd.lower().strip(" .,!?") in ("sir", "please", "there"):
            return self._wake_reply(s, t0, best, via)
        self.emit("wake", {"score": round(float(best), 2), "via": via + "+said it all", "yes_ms": 0, "device_ms": 0, "heard": text})
        if DANGLING.search(re.sub(r"[.,!?\s]+$", "", cmd.lower())):  # stopped mid-way ("Jarvis, remind me to..."): wait for the rest
            self.emit("state", "listening")
            more = self._capture(s, wait=3)
            if more is not None:
                cmd = (cmd.rstrip(" .,") + " " + self._strip_echo(self._stt(more))).strip()
        self.emit("state", "thinking")
        self.cut = True
        for part in re.split(r"[.,!?]*\s+(?=(?:hey\s+)?jarvis\b[,.]?\s+\w)", cmd, flags=re.I):  # "Jarvis, open X. Jarvis, open Y" said in one go
            self.emit("heard", after_wake(part) or part)

    def _wake_reply(self, s, t0, best, via):
        self.cut = True
        warm = self._warm()
        audio = self._reply_and_listen(s, t0, (), (best, via))
        warm.join(3)
        self._finish(s, audio)

    def _heard(self, clip):
        """Is this for Jarvis? Listen expecting the name: that hears a mumbled "Jarvis" (the owner's real clips, 7/7). But told to expect it, the model
        sometimes leaves a clear "Jarvis" out of what it writes, as already said. So if the name isn't there, listen once more without the hint."""
        audio = clip.astype(np.float32) / 32768

        def listen(hint):
            segs, _ = self.stt.transcribe(audio, language="en", beam_size=1, condition_on_previous_text=False, initial_prompt=hint, vad_filter=True, vad_parameters=VAD)
            return " ".join(x.text.strip() for x in segs).strip()
        text = listen(EXPECT)
        if not text or after_wake(text) is not None:
            return text
        plain = listen(None)
        return plain if after_wake(plain) is not None or is_wake(plain) else text

    def _keep(self, clip, score, text):
        """Save the last few uncertain wake-word clips ON THIS LAPTOP ONLY, so a wake word that fails can be diagnosed. Newest 30 kept."""
        if self.sink is not None:  # a test run: its made-up speech must not push out the owner's real clips
            return
        try:
            import wave
            d = os.path.join(ROOT, "logs", "wake_clips")
            os.makedirs(d, exist_ok=True)
            safe = re.sub(r"[^a-z0-9]+", "_", text.lower())[:30]
            with wave.open(os.path.join(d, f"{time.strftime('%m%d_%H%M%S')}_{score:.2f}_{safe}.wav"), "wb") as w:  # date first: the oldest really sorts first
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(clip.tobytes())
            for old in sorted(os.listdir(d), key=lambda f: os.path.getmtime(os.path.join(d, f)))[:-30]:
                os.remove(os.path.join(d, old))
        except OSError:
            pass

    def _loud(self, x, k=1.8, floor=90):
        return float(np.sqrt(np.mean(x.astype(np.float32) ** 2))) > max(k * self.nf, floor)

    def _reply_and_listen(self, s, t0=None, before=(), wake=None):
        """Say a wake reply while STILL recording (people often start talking over it), then listen for the command.
        Our own reply caught in the recording is removed from the text afterwards (_strip_echo)."""
        started = threading.Event()  # the clip plays on its own thread so we can report the moment it starts
        th = threading.Thread(target=self._play, args=(self._pick_clip(), t0, started), daemon=True)
        th.start()
        started.wait(2)
        if wake:
            self.emit("wake", {"score": round(float(wake[0]), 2), "via": wake[1], "yes_ms": self.stats.get("yes_ms", 0), "device_ms": self.stats.get("device_ms", 0)})
        self.emit("state", "listening")
        during = list(before)
        while th.is_alive():
            during.append(self._read(s))
        during += [self._read(s) for _ in range(4)]  # the echo's tail, still recorded
        self.quiet_until = 0.0
        self.oww.reset()
        self._clip_t = time.time()
        # Did they talk over the reply? Loudness can't tell (our echo is as loud as a quiet voice), so transcribe that stretch
        # in the background, minus our own words, while we keep listening for a fresh command.
        over = {}
        job = threading.Thread(target=lambda: over.setdefault("text", self._strip_echo(self._stt(np.concatenate(during)), keep=False)), daemon=True)
        job.start()
        audio = self._capture(s, lead=during, early=lambda: bool(over.get("text")))
        job.join(5)
        if audio is None and over.get("text"):  # they said it all while we were talking
            return np.concatenate(during)
        return audio

    def _strip_echo(self, text, keep=True):
        """Remove our own wake reply ("Yes, sir") picked up by the mic. If nothing is left: the original text when keep
        (the user may really have said "yes sir"), else ""."""
        out = text
        for r in self.replies:
            words = re.findall(r"[a-z']+", r.lower())
            core = [w for w in words if w != "sir"] if len(words) > 2 else words  # "at your service" / "i'm listening"; "yes sir" stays whole
            # the echo is often half-heard: "At your service, soon." -> allow a garbled last word instead of "sir"
            out = re.sub(r"\b" + r"[\s,.!?]*".join(map(re.escape, core)) + r"\b[\s,.!?]*(?:(?:sir|soon|so|sure|sire|sur|serve|sa)\b[\s,.!?]*)?",
                         " ", out, flags=re.I)
        out = re.sub(r"\s+", " ", out).strip(" ,.")
        return out if re.search(r"[a-z]", out, re.I) else (text if keep else "")

    def _wake_gpu(self):
        """Speech just started: get the GPU out of its idle state now, so writing down the sentence takes ~0.2 s instead of ~0.5 s
        when it ends (measured). At most every 2 s."""
        if time.time() - self._warmed > 2:
            self._warmed = time.time()
            self._warm()
            self.prewarm and self.prewarm()

    def _warm(self):
        """Wake the GPU out of its low-power state while the user is still talking (a cold first job takes ~1 s instead of ~0.25 s)."""
        t = threading.Thread(target=lambda: list(self.stt.transcribe(np.zeros(SR, dtype=np.float32), language="en")[0]), daemon=True)
        t.start()
        return t

    def _finish(self, s, audio, depth=0):
        if audio is None:
            self.emit("status", "I heard the wake word but no command followed.")
            self.emit("state", "idle")
            return
        self.emit("state", "thinking")
        text = self._strip_echo(self._stt(audio))
        if text and not self._strip_echo(text, keep=False) and time.time() - getattr(self, "_clip_t", 0) < 8:
            text = ""  # only our own "Yes, sir" came back through the mic: that's not a command
        if text and self._is_echo(text):  # that was Jarvis's own voice coming back through the microphone
            self.emit("status", "Ignored a sound that was my own voice.")
            self.emit("state", "idle")
            return
        if text and depth < 1 and re.fullmatch(r"(?:(?:hey|ok|okay)[, ]+)?jarvis[.!?, ]*", text.strip().lower()):
            # only the name was said: answer, then listen for the command
            return self._finish(s, self._reply_and_listen(s), depth + 1)
        if text and depth < 2 and DANGLING.search(re.sub(r"[.,!?\s]+$", "", text.lower())):
            more = self._capture(s, wait=3)  # the sentence stops mid-way ("remind me to..."): give them a moment to finish it
            if more is not None:
                audio = np.concatenate([audio, more])
                text = self._strip_echo(self._stt(audio))
        if text:
            self.cut = True
            self.emit("heard", text)
        else:
            self.emit("status", "I couldn't make out that, sir.")
            self.emit("state", "idle")

    def _capture(self, s, seed=None, wait=5, lead=None, early=None, short=3):
        """Record until about 0.56 s of quiet after speech. None if nobody spoke within `wait` s.
        `seed` = sound already heard that counts as speech; `lead` = sound recorded during our reply, kept in front of the result."""
        if hasattr(self.vad, "reset_states"):
            self.vad.reset_states()
        chunks, speech, quiet, start = list(seed or []), bool(seed), 0, time.time()  # raw sound goes to Whisper; the boost is only for the speech detector
        voiced = 3 if seed else 0
        while time.time() - start < 15 and not self.stop:
            x = self._read(s)
            chunks.append(x)
            if self._speech(x):
                speech, quiet, voiced = True, 0, voiced + 1
            elif speech:
                quiet += 1
                if quiet >= 7 and voiced < short:  # just a blip (the end of our own "Yes", a click): not speech, keep waiting
                    speech, quiet, voiced, chunks = False, 0, 0, chunks[-4:]
            if not speech:
                chunks = chunks[-4:]  # keep a little lead-in only
                if time.time() - start > wait or (early and time.time() - start > 0.8 and early()):  # early: the command already came
                    return None
            elif quiet >= 7:
                break
        return np.concatenate(list(lead or []) + chunks) if speech else None

    def _stt(self, audio):
        t = time.perf_counter()
        segs, _ = self.stt.transcribe(audio.astype(np.float32) / 32768, language="en", beam_size=1, initial_prompt=PROMPT, condition_on_previous_text=False,
                                      vad_filter=True, vad_parameters=VAD)
        text = " ".join(s.text.strip() for s in segs).strip()
        self.stats["stt_ms"] = round((time.perf_counter() - t) * 1000)
        self.stats.setdefault("stt_all", []).append(self.stats["stt_ms"])
        plain = re.sub(r"[^a-z ]", "", text.lower()).strip()
        if len(audio) < SR * 0.3 or plain in JUNK or plain.startswith("vocabulary"):  # whisper makes up text on near-silence
            return ""
        return text

    def _watch_devices(self):
        """Follow the Windows default mic/speaker: ask a tiny separate process every 8 s (our own sound
        library can't see changes while it's running). ponytail: ~1% of one core; swap for a COM call if it matters."""
        code = "import sounddevice as s;print(s.query_devices(kind='input')['name']);print(s.query_devices(kind='output')['name'])"
        while not self.stop:
            try:
                names = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=8,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.split("\n")[:2]
                if self.devices and names != self.devices:
                    self.dev_changed = True
                    with self.out_lock:
                        try:
                            self.out and self.out.close()
                        except Exception:
                            pass
                        self.out = None
                    self.emit("status", f"Sound device changed: now using {names[0]}.")
                self.devices = names
            except Exception:
                pass
            time.sleep(8)
