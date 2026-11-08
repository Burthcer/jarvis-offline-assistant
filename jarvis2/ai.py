"""The only file that touches llama (plan 13.3). Loads on first use, unloads when idle, refuses a prompt that doesn't fit (V1 hid that overflow)."""
import logging
import os
import time
import threading
import weakref
from functools import wraps

log = logging.getLogger("jarvis2")
MODELS = r"C:\Users\USER\Desktop\Wisperno-pro\models"
DEFAULT_MODEL = os.path.join(MODELS, "Qwen2.5-1.5B-Instruct-Q8_0.gguf")  # read-only, Wisperno's file: decides what to DO (fast, 0.2 s)
CHAT_MODEL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "models", "llm", "Qwen3-4B-Instruct-2507-Q4_K_M.gguf")   # answers (about 3 GB, loaded when asked, freed after 3 idle minutes)

# The two existing models take turns using the GPU. A shared lock also stops
# speech-triggered warm-up from unloading a model while it is answering.
GPU_LOCK = threading.RLock()
MODELS_IN_USE = weakref.WeakSet()


def serialized(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        with GPU_LOCK:
            return fn(*args, **kwargs)
    return run


class AIError(Exception):
    pass


class AI:
    def __init__(self, path=DEFAULT_MODEL, n_ctx=4096):
        self.path, self.n_ctx, self.llm, self.last_used, self.load_s, self.prompt_tokens = path, n_ctx, None, 0.0, 0.0, 0
        with GPU_LOCK:
            MODELS_IN_USE.add(self)

    @property
    def loaded(self):
        return self.llm is not None

    @serialized
    def load(self):
        if self.llm:
            return
        for other in list(MODELS_IN_USE):
            if other is not self:
                other.unload()
        t0 = time.time()
        from jarvis.brain import _dlls  # Wisperno's CUDA libraries, read-only
        _dlls()
        from llama_cpp import Llama
        self.llm = Llama(model_path=self.path, n_gpu_layers=-1, n_ctx=self.n_ctx, use_mmap=False,
                         n_batch=128, n_ubatch=128, flash_attn=True, verbose=False)
        self.load_s = time.time() - t0
        self.last_used = time.time()          # idle time counts from the load (it was 0, so the first check unloaded a model nobody had used yet)
        log.info("ai loaded %s in %.1fs", os.path.basename(self.path), self.load_s)

    @serialized
    def unload(self):
        if self.llm:
            self.llm.close()
            self.llm = None
            log.info("ai unloaded")

    @serialized
    def unload_if_idle(self, minutes):
        if self.llm and time.time() - self.last_used > minutes * 60:
            self.unload()
            return True
        return False

    @serialized
    def complete(self, messages, temperature=0.0, max_tokens=90):
        self.load()
        text = "".join(m["content"] + "\n" for m in messages)
        n = len(self.llm.tokenize(text.encode("utf-8"))) + 8 * len(messages)
        if n + max_tokens >= self.n_ctx:
            log.error("PROMPT TOO LONG: %d + %d >= n_ctx %d", n, max_tokens, self.n_ctx)
            raise AIError(f"prompt too long ({n} tokens)")
        out = self.llm.create_chat_completion(messages, temperature=temperature, max_tokens=max_tokens, stop=["\n\n"])
        self.last_used, self.prompt_tokens = time.time(), out["usage"]["prompt_tokens"]
        return out["choices"][0]["message"]["content"]
