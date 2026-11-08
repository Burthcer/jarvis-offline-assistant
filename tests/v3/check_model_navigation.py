"""One short trial of the REAL local chat model (Qwen3 4B) on FAKE screens: does it answer navigation steps in valid JSON with the right number,
and write sensible short drafts? No real window, no sound."""
import os, sys, time, subprocess
os.environ['JARVIS_SILENT'] = '1'
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # GPU: loads the 4B chat model (~2.9 GB) for about 10 s; run only when nothing else uses the GPU
from types import SimpleNamespace
from jarvis3.engine.ai import AI, CHAT_MODEL
from jarvis3.engine.abilities import tasks, drafts
from jarvis3.engine.registry import Ask
from jarvis3.screen_index import ScreenIndex, Element
tasks.SETTLE_S = 0
gpu = lambda: subprocess.run(['nvidia-smi', '--query-gpu=memory.used,temperature.gpu', '--format=csv,noheader'], capture_output=True, text=True).stdout.strip()

def el(n, k='ButtonControl', y=0): return Element(n, k, (0, y, 300, y + 30))
class Src:
    def __init__(self, items, after): self.items, self.after, self.invoked = items, after, []
    def scan(self): return ('w', 'x'), list(self.items)
    def invoke(self, e): self.invoked.append(e.name); self.items = self.after; return True

discord = [el('Direct Messages', 'TreeItemControl'), el('Gaming Hub', 'TreeItemControl', 40), el('CS Study Group', 'TreeItemControl', 80), el('Add a Server', y=120), el('Settings', y=160)]
youtube = [el('Home', 'HyperlinkControl'), el('Shorts', 'HyperlinkControl', 40), el('Subscriptions', 'HyperlinkControl', 80), el('Search', 'EditControl', 120),
           el('Lofi hip hop radio - beats to relax/study to', 'HyperlinkControl', 200), el('Mix - Arijit Singh', 'HyperlinkControl', 240), el('Mix - Chill Synthwave', 'HyperlinkControl', 280),
           el('Sign in', y=320), el('Settings', y=360)]
cases = [  # (screen, goal, step, the right answer: element name, or an action)
    (discord, 'open discord and go to my college server', 'go to my college server', 'CS Study Group'),
    (discord, 'open discord and open the server for gamers', 'open the server for gamers', 'Gaming Hub'),
    (youtube, 'open youtube and put on something relaxing to study', 'put on something relaxing to study', 'Lofi hip hop radio - beats to relax/study to'),
    (youtube, 'open youtube and show my subscriptions', 'show my subscriptions', 'Subscriptions'),
    (youtube, 'open youtube and play an arijit song', 'play an arijit song', 'Mix - Arijit Singh'),
    (youtube, 'open youtube and open my playlist of jazz', 'open my playlist of jazz', 'ASK'),   # not on screen: should ask, not guess
]
print('GPU before:', gpu())
ai = AI(CHAT_MODEL, n_ctx=2048)
t = time.time(); ai.load(); print(f'load {time.time()-t:.1f}s, GPU loaded:', gpu())
right = 0
for screen, goal, step, want in cases:
    src = Src(screen, [el('changed')]); s = ScreenIndex(src)
    ctx = SimpleNamespace(os=SimpleNamespace(ui_screen=lambda s=s: s, ui_press=lambda k: None, ui_type=lambda x: None), app=SimpleNamespace(task=None), ai=ai)
    task = tasks.Task(goal, [step]); ctx.app.task = task
    t = time.time()
    try:
        out = tasks._model_step(ctx, task, step, False); got = src.invoked[0] if src.invoked else f'no click ({out})'
    except Ask as a:
        got = 'ASK: ' + a.question
    ok = (got == want) or (want == 'ASK' and got.startswith('ASK'))
    right += ok
    print(f"{'OK ' if ok else 'BAD'} {time.time()-t:4.1f}s  '{step}' -> {got}  (want {want})")
print(f'navigation {right}/{len(cases)}  prompt tokens last {ai.prompt_tokens}')
for contact, what, style in (('Rahul', "I'm out and cannot reply", 'short'), ('Mum', 'I will be home by 8, dont wait for dinner', ''), ('Professor Mehta', 'can I submit the assignment tomorrow because I was ill', 'polite')):
    t = time.time(); text = drafts.write(SimpleNamespace(ai=ai), drafts.Draft(contact, what, style)); print(f'draft {time.time()-t:.1f}s  {contact}: {text!r}')
print('GPU after:', gpu())
ai.unload(); time.sleep(1); print('GPU unloaded:', gpu())
