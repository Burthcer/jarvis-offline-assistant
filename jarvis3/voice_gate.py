"""Opt-in owner-voice gate for V3: a similarity score, NOT identity security.

Uses the approved CPU ONNX voice-check export (see jarvis3/lab/README.md).
Enrols only from the owner's existing stage-1 quiet recordings; never opens a mic.
Clips shorter than one second cannot be judged and pass unscored.
"""
import json
import wave
from pathlib import Path

import numpy as np

from jarvis3.paths import PROJECT, DATA

MODEL = PROJECT / 'data/v3/lab/model'
PROFILE = DATA / 'voice_profile.json'
RECORDING = PROJECT / 'data/gold/audio/quiet.wav'
INDEX = PROJECT / 'data/gold/audio/session.json'
THRESHOLD = .25   # the lab's fixed verification default: 103/103 owner clips, 0/11 other voices


class VoiceGate:
    def __init__(self, model=MODEL, profile=PROFILE, threshold=THRESHOLD):
        self.model_dir, self.profile_path, self.threshold = Path(model), Path(profile), threshold
        self.model = None; self.profile = None; self.error = ''

    @property
    def available(self):
        return (self.model_dir / 'voice-check-fp32.onnx').exists() and (self.model_dir / 'export.json').exists()

    def sha(self):
        return json.loads((self.model_dir / 'export.json').read_text(encoding='utf-8'))['onnx_sha256']

    def load(self):
        if self.model is None:
            from jarvis3.lab.voice_check_onnx import OnnxVoiceCheck
            self.model = OnnxVoiceCheck(self.model_dir)
        return self.model

    def load_profile(self):
        try:
            data = json.loads(self.profile_path.read_text(encoding='utf-8'))
            if data.get('model') != self.sha():
                self.error = 'The saved voice profile belongs to another model.'; return False
            self.profile = np.asarray(data['vector'], dtype=np.float32); return True
        except (OSError, ValueError, KeyError):
            return False

    def enroll_from_recordings(self, recording=RECORDING, index=INDEX, takes=3):
        """the owner's first three quiet stage-1 takes. Refuses when missing; never records."""
        try:
            with wave.open(str(recording)) as w:
                if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (16000, 1, 2):
                    raise ValueError('format')
                audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
            rows = json.loads(Path(index).read_text(encoding='utf-8'))['sections']['quiet']['takes'][:takes]
        except (OSError, ValueError, KeyError, EOFError):
            self.error = 'Your stage-1 recordings are missing, so I cannot learn your voice.'; return False
        model = self.load()
        model.enroll([audio[round(t['start'] * 16000):round(t['end'] * 16000)] for t in rows])
        self.profile = np.asarray(model.profile, dtype=np.float32)
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.profile_path.write_text(json.dumps({'model': self.sha(), 'takes': [t['id'] for t in rows],
                                                 'vector': [float(x) for x in self.profile]}), encoding='utf-8')
        return True

    def ready(self):
        """Load or build the profile. False with .error when it cannot be used."""
        if not self.available:
            self.error = 'The voice-check model is not installed.'; return False
        return self.profile is not None or self.load_profile() or self.enroll_from_recordings()

    def check(self, audio):
        """audio: int16-scaled samples at 16 kHz -> (accepted, score), or None when too short to judge."""
        if self.profile is None or len(audio) < 16000:
            return None
        vector = self.load().embedding(np.asarray(audio, dtype=np.float32) / 32768)
        if vector is None:
            return None
        score = float(np.dot(self.profile, vector))
        return score >= self.threshold, score
