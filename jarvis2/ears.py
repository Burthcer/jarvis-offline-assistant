"""Ears (plan 13.9): mic + PC-sound canceller -> voice detector -> pause -> WHOLE sentence -> Whisper (with a hint) -> for Jarvis only if the name starts it.
No wake model, no guessing from pieces. All timing is counted in samples, so a recording can be replayed faster than real time and give the same answer."""
import collections
import difflib
import glob
import logging
import os
import queue
import re
import threading
import time
import wave
from dataclasses import dataclass

import numpy as np

from .canceller import BLOCK, SR, Canceller, find_delay, rms

log = logging.getLogger("jarvis2")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOCK_S = BLOCK / SR
PRE_BLOCKS = 4          # 0.5 s kept from before the voice is noticed
END_BLOCKS = 5          # 0.64 s pause ends a sentence
EARLY_BLOCKS = 3        # 0.38 s pause: start Whisper already, throw it away if he goes on
MAX_BLOCKS = 94         # 12 s cap
NOISE_S = 30            # speech "on" this long = a video or a crowd: skip Whisper until a pause
ARM_S = 8               # after "Jarvis" alone, or after a reply: the next sentence needs no name for this long
THR = 0.35
JUNK = {"you", "thank you", "thanks", "thanks for watching", "bye", "so", "uh", "um", "hmm", "okay", "ok", "yeah", "the", "i"}


@dataclass
class Heard:
    text: str            # the command, name removed ("" = the name alone)
    trigger: str         # "name" | "follow_up"
    clip_id: str
    started: float       # seconds on the sample clock
    ended: float
    raw: str = ""        # what Whisper wrote
    stt_ms: int = 0
    wait_ms: int = 0     # from the end of the sentence (wall clock) to this answer


# ---------- the name ----------
LEAD = {"hey", "hi", "ok", "okay", "yo", "hello", "so", "and", "well", "now", "right", "alright", "to", "uh", "um", "oh", "please", "sir", "a", "eh"}


def name_split(text):
    """-> (found, rest). The name must be one of the first three words ('to... Hey Jarvis, open YouTube'). Spellings: V1's list of how it wrote the owner's 'Jarvis'."""
    from jarvis.voice import _jarvisish
    words = list(re.finditer(r"[A-Za-z']+", text))
    for i, m in enumerate(words[:3]):
        if _jarvisish(m.group().lower()):
            if all(w.group().lower() in LEAD for w in words[:i]):      # only greetings and stumbles may come before it: not "I told Jarvis to..."
                return True, text[m.end():].strip(" ,.!?;:-")
            break
    return False, text


def junk(text):
    return re.sub(r"[^a-z ]", "", text.lower()).strip() in JUNK


# ---------- Whisper ----------
class Transcriber:
    def __init__(self):
        self.model = None

    def load(self):
        logging.getLogger("faster_whisper").setLevel(logging.ERROR)    # it logs a line per sentence
        from jarvis import voice as V
        gpu = V._cuda()
        from faster_whisper import WhisperModel
        path = next(iter(sum((glob.glob(g) for g in V.WHISPER_GLOBS), [])), None)
        if not path:
            raise RuntimeError("speech model not found in the Wisperno folder")
        self.model = WhisperModel(path, device="cuda" if gpu else "cpu", compute_type="int8_float16" if gpu else "int8")
        self.device = "GPU" if gpu else "CPU"
        segments, _ = self.model.transcribe(np.zeros(SR, np.float32), language="en")
        list(segments)   # Whisper is lazy: consuming segments actually warms it.
        log.info("whisper loaded on %s", self.device)

    def unload(self):
        self.model = None

    def again(self, audio):
        """A second listen with no hint and a wider search, for a clip where the name was not heard: the hint sometimes makes Whisper skip a name it did hear (V1 did this too)."""
        segs, _ = self.model.transcribe(audio.astype(np.float32) / 32768, language="en", beam_size=5, best_of=1, temperature=0.0, condition_on_previous_text=False, vad_filter=False)
        return " ".join(s.text.strip() for s in segs).strip()

    def __call__(self, audio, hint):
        segs, _ = self.model.transcribe(audio.astype(np.float32) / 32768, language="en", beam_size=1, best_of=1, temperature=0.0, condition_on_previous_text=False,
                                        initial_prompt=hint, vad_filter=False)
        return " ".join(s.text.strip() for s in segs).strip()


class Job:
    def __init__(self, audio, a, b):
        self.audio, self.a, self.b = audio, a, b
        self.text, self.done, self.final, self.ms, self.final_at, self.continuous, self.second = None, False, False, 0, 0.0, False, False
        self.lock = threading.Lock()
        self.cancelled = False
        self.speech_end_wall = 0.0
        self.voice_a = a  # actual onset, unlike a which includes pre-roll


# ---------- the ears ----------
class Ears:
    """mic: .read() -> int16 array of BLOCK samples (None = the end of a recording). ref: .get(start, n) -> the PC's sound at the same sample clock (None = no loopback).
    on_heard(Heard) is called from a worker thread. hint() -> the short vocabulary text Whisper is told to expect."""

    def __init__(self, mic, ref, transcriber, on_heard, hint=lambda: "Jarvis.", clips_dir=None, name_only=False):
        self.mic, self.ref, self.stt, self.on_heard, self.hint, self.clips_dir = mic, ref, transcriber, on_heard, hint, clips_dir
        self.canceller = Canceller()
        self.lag = None
        self.max_delay = 8                # blocks: more than 1 s behind is not believable
        self.delay = 0                    # blocks the mic is held back (only when the PC-sound clock runs behind the mic's)
        self.jobs = queue.Queue(maxsize=16)
        self.stop = False
        self.armed_until = 0.0            # wall clock
        self.armed_from = 0.0             # sample clock: a follow-up must START after the reply ended, or it is the reply's own echo
        self.wake_pending = False
        self.armed_to = 0.0
        self.clock = 0.0                  # sample clock, seconds
        getattr(ref, "sync", lambda: None)()          # the PC-sound clock starts with the mic's
        self.history = collections.deque(maxlen=int(10 * SR / BLOCK))   # raw mic blocks, for finding the delay
        self.level = 0.0
        self.stats = collections.Counter()
        self.threads = []
        self.paused_until = 0.0           # wall clock: 'microphone off' lasts ten minutes at most
        self.is_complete = lambda text: False   # the app says: this is a whole command, nothing more is coming (open X, pause, volume 40...)
        self.on_state = lambda s: None    # "listening" | "hearing" (for a screen)
        self.on_problem = lambda text: None
        self.reply_words = ["Yes, sir", "At your service, sir", "I'm listening, sir"]      # the wake replies: heard back through the mic they are not a command
        self.recent_replies = collections.deque(maxlen=12)

    # ----- control -----
    def arm(self, seconds=ARM_S, since=None):
        """The next sentence needs no name for a while: after 'Jarvis' alone (since = when that sentence ended: he may talk over the 'Yes, sir'),
        or after Jarvis asked him something (since = None: it must start after the question ended, or it is the question's own echo).
        Arming again while still armed only extends the time."""
        armed = time.monotonic() < self.armed_until
        self.armed_until = time.monotonic() + seconds
        self.armed_to = self.clock + seconds
        if not armed or since is not None:
            self.armed_from = since if since is not None else self.clock + 0.4      # 0.4 s for the speaker's tail and the room

    def remember_reply(self, text):
        """Keep only recent spoken sentences, to recognise our question's echo
        while still accepting the user's answer over the end of that question.
        Matching ignores punctuation, never guesses from similar words.
        """
        expires = self.clock + max(12, len(text.split()) / 2 + ARM_S)
        for sentence in re.split(r'(?<=[.!?])\s+', text):
            words = re.findall(r"[a-z0-9']+", sentence.lower())
            if len(words) >= 3:
                self.recent_replies.append((words, expires))

    def _without_reply(self, text, started):
        for words, expires in list(self.recent_replies):
            if started > expires:
                continue
            pattern = r"^\W*" + r"[\W_]+".join(map(re.escape, words)) + r"\b[\W_]*"
            text = re.sub(pattern, '', text, count=1, flags=re.I)
        return text.strip()

    def start(self):
        for fn in (self._worker, self._run):
            t = threading.Thread(target=fn, daemon=True)
            t.start()
            self.threads.append(t)

    def in_followup(self, started, now=None):
        now = time.monotonic() if now is None else now
        # Eligibility is when he STARTED speaking, not when a long/noisy
        # recording or delayed STT finally delivered the words.
        return self.armed_until > 0 and started >= self.armed_from and (now < self.armed_until or started < self.armed_to)

    def join(self, timeout=None):
        self.threads[-1].join(timeout)         # the loop ends when a recording runs out
        self.jobs.join()

    def shutdown(self):
        self.stop = True

    # ----- the loop -----
    def _aligned_ref(self, k):
        """The PC sound for mic block k and the block before it, shifted by the delay the mic hears it with."""
        if self.ref is None or self.lag is None:       # no loopback, or the mic can't hear the PC's sound (earphones): nothing to cancel
            return np.zeros(2 * BLOCK, np.float32)
        shift = self.lag - 400                  # 25 ms early, so the filter sees the room's echoes too
        start = (k - 1) * BLOCK - shift
        return self.ref.get(start, 2 * BLOCK) if start >= 0 else np.zeros(2 * BLOCK, np.float32)

    def _find_lag(self, k):
        n = len(self.history) * BLOCK
        if self.ref is None or n < SR * 6:
            return
        start = (k + 1) * BLOCK - n
        mic = np.concatenate(list(self.history)).astype(np.float32)
        lag = find_delay(mic, self.ref.get(start, n))
        if lag is not None and (self.lag is None or abs(lag - self.lag) > 160):      # 10 ms: the estimate wobbles by a few ms, and moving the sound under the filter undoes what it learned
            log.info("delay to the PC's sound: %d ms", round(lag / SR * 1000))
            if self.lag is not None:
                self.canceller.reset()
            self.lag = lag
            self.delay = min(self.max_delay, max(0, -(-(400 - lag) // BLOCK)))              # ceil((400 - lag) / BLOCK): the PC-sound window of a block must already have arrived
            self.stats["delay_found"] += 1

    def _run(self):
        pre = collections.deque(maxlen=PRE_BLOCKS)
        pending = collections.deque()
        seg, start_k, last_active, k = [], None, -1, 0
        early, run_start, last_end, voice_start = None, 0, -99, 0
        diag = {"n": 0, "mic": 0.0, "clean": 0.0, "ref": 0.0, "t": time.monotonic()}
        while not self.stop:
            try:
                x = self.mic.read()
            except Exception as e:                                  # unplugged or blocked: say so and try again
                log.error("microphone problem: %s", e)
                time.sleep(2)
                continue
            if x is None:
                break
            if time.monotonic() < self.paused_until:                 # microphone switched off by voice: keep reading, hear nothing
                x = np.zeros_like(x)
            self.level = rms(x) / 32768
            pending.append(x)
            if len(pending) <= self.delay:                           # the PC's sound reaches us later than the mic's: hold the mic back until it is here
                continue
            x = pending.popleft()
            self.history.append(x)
            self.clock = (k + 1) * BLOCK_S
            if k % 150 == 20 or (self.lag is None and k % 25 == 20):       # every ~20 s, or every 3 s until it is known
                self._find_lag(k)
            ref2 = self._aligned_ref(k)
            clean, probs = self.canceller.feed(x, ref2)
            if self.canceller.cancelling:                            # what the canceller really achieves, logged once a minute while the PC is playing something
                diag["n"] += 1
                diag["mic"] += float(np.mean(x.astype(np.float32) ** 2)); diag["clean"] += float(np.mean(clean ** 2)); diag["ref"] += float(np.mean(ref2 ** 2))
            if time.monotonic() - diag["t"] > 60:
                if diag["n"] >= 20:
                    db = 10 * np.log10(max(diag["mic"], 1) / max(diag["clean"], 1))
                    log.info("canceller: PC sound rms %.0f, mic rms %.0f -> %.0f (%.1f dB removed), delay %s ms, mic held back %d blocks, %d gaps in the PC-sound stream",
                             np.sqrt(diag["ref"] / diag["n"]), np.sqrt(diag["mic"] / diag["n"]), np.sqrt(diag["clean"] / diag["n"]), db,
                             None if self.lag is None else round(self.lag / SR * 1000), self.delay, getattr(self.ref, "resyncs", 0))
                diag = {"n": 0, "mic": 0.0, "clean": 0.0, "ref": 0.0, "t": time.monotonic()}
            clean = clean.astype(np.int16)
            if max(probs) > THR:
                if start_k is None:
                    voice_start = k
                    start_k, seg = k - len(pre), list(pre)
                    if start_k - last_end > 1:                       # a new run of talk, not the rest of one the 12 s cap cut in two
                        run_start = start_k
                    self.on_state("hearing")
                seg.append(clean)
                if early is not None:
                    early.cancelled = True
                last_active, early = k, None                         # he is still talking: an early try is void
            elif start_k is not None:
                seg.append(clean)
            else:
                pre.append(clean)
            if start_k is not None:
                pause = k - last_active
                if pause >= EARLY_BLOCKS and early is None and len(seg) < MAX_BLOCKS:
                    early = self._submit(seg, start_k, last_active, voice_start)
                quick = early is not None and early.done and not early.final and pause >= EARLY_BLOCKS and self._complete(early.text)
                if pause >= END_BLOCKS or len(seg) >= MAX_BLOCKS or quick:
                    self._end(seg, start_k, last_active, early, continuous=pause < EARLY_BLOCKS and len(seg) >= MAX_BLOCKS, voice_start=voice_start)
                    last_end, seg, start_k, early = k, [], None, None
                    pre.clear()
            k += 1
        self.stop = True

    def _complete(self, text):
        try:
            found, rest = name_split(text or "")
            return bool((found and rest and self.is_complete(rest)) or (time.monotonic() < self.armed_until and self.is_complete(text or '')))
        except Exception:
            return False

    def _clip(self, seg, start_k, last_active):
        return np.concatenate(seg[:last_active - start_k + 2])      # up to the last voiced block, plus one block of tail

    def _submit(self, seg, start_k, last_active, voice_start=None):
        audio = self._clip(seg, start_k, last_active)
        job = Job(audio, start_k * BLOCK_S, (last_active + 1) * BLOCK_S)
        job.voice_a = (voice_start if voice_start is not None else start_k) * BLOCK_S
        job.speech_end_wall = time.monotonic() - max(0, self.clock - job.b) - self.delay * BLOCK_S
        try:self.jobs.put_nowait(job)
        except queue.Full:
            job.cancelled=True; job.done=True; job.text=''
            self.stats['overload']+=1
            self.on_problem('My hearing queue is full. Please wait a moment and repeat the last command, sir.')
        return job

    def _end(self, seg, start_k, last_active, early, continuous=False, voice_start=None):
        self.on_state("listening")
        job = early if early is not None and early.audio.shape == self._clip(seg, start_k, last_active).shape else self._submit(seg, start_k, last_active, voice_start)
        job.continuous = continuous
        with job.lock:
            job.final, job.final_at = True, time.monotonic()
            if job.done:
                self._decide(job)

    # ----- Whisper in its own thread: the mic is never kept waiting -----
    def _worker(self):
        while True:
            try:
                job = self.jobs.get(timeout=0.2)
            except queue.Empty:
                if self.stop and self.jobs.empty():
                    return
                continue
            try:
                if job.cancelled:
                    continue
                t = time.perf_counter()
                job.text = self.stt(job.audio, self.hint())
                if not job.cancelled and not name_split(job.text)[0] and not job.continuous and not self.in_followup(job.voice_a) and 0.6 < len(job.audio) / SR < 7:
                    again = self.stt.again(job.audio)                  # no name heard: listen once more, differently
                    if name_split(again)[0]:
                        log.info("second listen found the name: %r (first listen: %r)", again, job.text)
                        job.text, job.second = again, True
                job.ms = round((time.perf_counter() - t) * 1000)
            except Exception:
                log.exception("whisper failed")
                job.text = ""
            finally:
                with job.lock:
                    job.done = True
                    if job.final and not job.cancelled:
                        self._decide(job)
                self.jobs.task_done()

    # ----- is it for Jarvis? -----
    def hint_echo(self, text):
        """Whisper sometimes reads the vocabulary it was given back out of noise ('Jarvis, Google, WhatsApp'): words that are all from the hint are not a command."""
        words = set(re.findall(r"[a-z0-9]+", text.lower()))
        return len(words) >= 2 and words <= set(re.findall(r"[a-z0-9]+", self.hint().lower())) | {"jarvis", "hey"}

    def decide(self, text, now=None, started=1e9, continuous=False):
        """-> (command, trigger) or None. Pure, so it can be tested without audio. started = when the sentence began on the sample clock."""
        now = time.monotonic() if now is None else now
        text = self._without_reply(text or '', started)
        if not text or junk(text) or self.hint_echo(text):
            return None
        found, rest = name_split(text)
        if found:
            if junk(rest):
                rest = ''  # "Jarvis, uh..." is a wake, not an AI request.
            return rest, "name"
        if continuous:                                      # talk with no pause (music or a video under his voice): the name may start a sentence in the middle
            sentences = re.findall(r"[^.?!]+[.?!]*", text)
            for i, sentence in enumerate(sentences):
                f, r = name_split(sentence.strip())
                if f:
                    return " ".join([r] + [x.strip() for x in sentences[i + 1:]]).strip(" ,"), "name"
        if self.in_followup(started, now):
            replies = [r'[\W_]*'.join(re.findall(r'[a-z]+', r.lower())) for r in self.reply_words + ['I am listening sir']]
            rest = re.sub(r"^\W*(?:" + "|".join(replies) + r")\b[\W]*", "", text.lower()).strip()
            if not rest:                                   # that was Jarvis' own "Yes, sir" coming back through the mic
                return None
            return (text[len(text) - len(rest):] if len(rest) < len(text) else text), "follow_up"
        return None

    def _decide(self, job):
        text = (job.text or "").strip()
        out = self.decide(text, started=job.voice_a, continuous=job.continuous)
        armed = time.monotonic() < self.armed_until
        log.info("heard %r%s%s -> %s", text, " [second listen]" if job.second else "", " [no pause]" if job.continuous else "",
                 "ignored (no name, echo or empty%s)" % (", outside listening start" if armed and job.voice_a < self.armed_from else "") if out is None else f"{out[1]}: {out[0]!r}")
        log.info("hearing stt=%dms delivery=%dms second=%s", job.ms, round((time.monotonic() - job.final_at) * 1000), job.second)
        if out is None:
            self.stats["ignored"] += 1
            return
        cmd, trig = out
        if trig == "name" and not cmd:
            self.arm(since=job.b)                          # "Jarvis" alone: wake reply, then the next sentence needs no name, even if he speaks over the reply
            self.wake_pending = True
        else:
            self.armed_until = 0.0
            self.wake_pending = False
        cid = self._save(job)
        h = Heard(cmd, trig, cid, job.a, job.b, text, job.ms, round((time.monotonic() - (job.speech_end_wall or job.final_at)) * 1000))
        self.stats["heard"] += 1
        try:
            self.on_heard(h)
        except Exception:
            log.exception("on_heard failed")

    def _save(self, job):
        if not self.clips_dir:
            return ""
        os.makedirs(self.clips_dir, exist_ok=True)
        cid = time.strftime("%Y%m%d-%H%M%S") + f"-{int(job.a * 1000) % 100000}"
        with wave.open(os.path.join(self.clips_dir, cid + ".wav"), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(job.audio.astype(np.int16).tobytes())
        old = sorted(glob.glob(os.path.join(self.clips_dir, "*.wav")))[:-40]       # only the last 40 clips are kept
        for f in old:
            os.remove(f)
        return cid


# ---------- real sources ----------
class ArraySource:
    """A recording as a mic (and as the PC's sound): replayed as fast as the machine can go."""

    def __init__(self, audio):
        self.a, self.i = audio.astype(np.int16), 0

    def read(self):
        if self.i >= len(self.a):
            return None
        x = self.a[self.i:self.i + BLOCK]
        self.i += BLOCK
        return x if len(x) == BLOCK else np.concatenate([x, np.zeros(BLOCK - len(x), np.int16)])

    def get(self, start, n):
        out = np.zeros(n, np.float32)
        lo, hi = max(start, 0), min(start + n, len(self.a))
        if hi > lo:
            out[lo - start:hi - start] = self.a[lo:hi]
        return out


def default_devices():
    """(default microphone id, default speaker id) from Windows' own audio list. Asking PortAudio would mean restarting it, which cuts off the speaker."""
    import comtypes
    from pycaw.pycaw import AudioUtilities as A
    comtypes.CoInitialize()
    try:
        return A.GetMicrophone().GetId(), A.GetSpeakers().id
    finally:
        comtypes.CoUninitialize()


class MicStream:
    """The default microphone, 16 kHz mono. Follows the Windows default: Windows' list is checked every 8 s; on a change (earphones plugged in or out)
    `before_restart` runs (the speaker lets go of PortAudio), PortAudio restarts and the mic opens on the new default."""

    def __init__(self, before_restart=lambda: None):
        self.s, self.before, self.changed = None, before_restart, False
        try:
            self.ids = default_devices()
        except Exception:
            log.exception("can't read the default audio devices")
            self.ids = None
        self._open(False)
        threading.Thread(target=self._watch, daemon=True).start()

    def _open(self, restart=True):
        import sounddevice as sd
        if self.s is not None:
            try:
                self.s.close()
            except Exception:
                pass
        if restart:
            self.before()
            sd._terminate(); sd._initialize()                       # PortAudio only notices a new default device after a restart
        self.s = sd.InputStream(samplerate=SR, channels=1, dtype="int16", blocksize=BLOCK)
        self.s.start()
        log.info("microphone opened: %s", sd.query_devices(kind="input")["name"])

    def _watch(self):
        while True:
            time.sleep(8)
            try:
                now = default_devices()
                if self.ids and now != self.ids:
                    log.info("default audio device changed")
                    self.ids, self.changed = now, True
            except Exception:
                log.exception("device check failed")

    def read(self):
        if self.changed:
            self.changed = False
            self._open()
        try:
            data, _ = self.s.read(BLOCK)
        except Exception:
            self._open()
            raise
        return data[:, 0].copy()


class Resampler:
    """Any device rate -> 16 kHz, chunk after chunk, with no join at the chunk edges: the canceller needs one unbroken signal."""

    def __init__(self, rate):
        from math import gcd

        from scipy.signal import firwin, lfilter_zi
        self.rate, g = rate, gcd(rate, SR)
        self.up, self.down = SR // g, rate // g
        self.b = firwin(97, 7600, fs=rate) if self.up == 1 else None
        self.zi = lfilter_zi(self.b, 1.0) * 0 if self.up == 1 else None
        self.skip = 0

    def __call__(self, x):
        from scipy.signal import lfilter, resample_poly
        if self.up != 1:                                     # ponytail: 44.1 kHz devices join chunks less cleanly; a stateful filter if one ever shows up
            return resample_poly(x, self.up, self.down).astype(np.float32)
        y, self.zi = lfilter(self.b, 1.0, x, zi=self.zi)
        out = y[self.skip::self.down]
        self.skip = (self.skip - len(x)) % self.down
        return out.astype(np.float32)


class LoopRing:
    """What the default speaker is playing (WASAPI loopback, PyAudioWPatch), as 16 kHz mono on the same sample clock as the mic.
    Chunks are laid end to end by COUNTING samples. The wall clock only places the first chunk and any chunk after a real gap: a callback arrives a few ms early or late,
    and placing each chunk by the clock left holes and overlaps that broke the canceller live, although it worked on recordings."""
    RESYNC = SR // 4                                         # 0.25 s off: a real gap in the sound, not a late callback

    def __init__(self, seconds=40, start=True):
        self.size, self.t0, self.filled, self.pos, self.resyncs = seconds * SR, time.perf_counter(), 0, None, 0
        self.buf = np.zeros(self.size, np.float32)
        self.lock = threading.Lock()
        self.error = None
        if start:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def sync(self):
        with self.lock:
            self.t0, self.filled, self.pos = time.perf_counter(), 0, None
            self.buf[:] = 0

    def _now(self):
        return int((time.perf_counter() - self.t0) * SR)

    def _advance(self, idx):
        """Silence may have no callbacks: clear the ring up to now so old sound is never read back."""
        if idx > self.filled:
            a, n = self.filled % self.size, min(idx - self.filled, self.size)
            if a + n <= self.size:
                self.buf[a:a + n] = 0
            else:
                self.buf[a:] = 0; self.buf[:a + n - self.size] = 0
            self.filled = idx

    def _write(self, x):
        with self.lock:
            now = self._now()
            if self.pos is None or abs(now - (self.pos + len(x))) > self.RESYNC:
                self.resyncs += self.pos is not None
                self.pos = now - len(x)
            self._advance(self.pos)
            self.buf[np.arange(self.pos, self.pos + len(x)) % self.size] = x
            self.pos += len(x)
            self.filled = max(self.filled, self.pos)

    def get(self, start, n):
        with self.lock:
            self._advance(self._now())
            return self.buf[np.arange(start, start + n) % self.size].copy()

    def _run(self):
        try:
            import pyaudiowpatch as pa
            p = pa.PyAudio()
            info = p.get_default_wasapi_loopback()
            rate, ch = int(info["defaultSampleRate"]), int(info["maxInputChannels"])
            rs = Resampler(rate)

            def cb(data, frames, t, status):
                self._write(rs(np.frombuffer(data, np.int16).reshape(-1, ch).astype(np.float32).mean(1)))
                return None, pa.paContinue
            s = p.open(format=pa.paInt16, channels=ch, rate=rate, input=True, input_device_index=info["index"], frames_per_buffer=rate // 20, stream_callback=cb)
            log.info("PC sound (loopback): %s", info["name"])
            while s.is_active():
                time.sleep(1)
        except Exception as e:
            self.error = str(e)
            log.error("loopback failed: %s", e)
