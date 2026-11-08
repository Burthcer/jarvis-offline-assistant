"""V2's window, pill and tray. The faces are V1's (the web page in jarvis2/web with a Knowledge tab, the island, the tray); the brain behind them is V2's App.
UiApp is V1's App with its engine swapped: submit() asks jarvis2.App.handle, the ears and the speaker sit behind the same `voice` calls V1's page already uses."""
import ctypes
import json
import os
import queue
import re
import threading
import time
import traceback
from datetime import datetime

from . import settings as _settings  # noqa: F401  (points V1's settings code at settings2.json)
from jarvis import actions, settings, ui as v1
from jarvis.store import Store

from .ai import AI, CHAT_MODEL
from .app import App
from .ears import Ears, LoopRing, MicStream, Transcriber
from .memory import Memory
from .osapi import Real
from .speaker import Speaker

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
ICON = os.path.join(ROOT, "jarvis.ico")
OFFER_EVERY_S = 60


def _log(e=None):
    os.makedirs("logs", exist_ok=True)
    with open(os.path.join("logs", "jarvis2.log"), "a", encoding="utf-8") as f:
        f.write(traceback.format_exc() + "\n")


class Voice:
    """What V1's page and settings expect of `voice`, on top of V2's ears and speaker."""

    def __init__(self, ui):
        self.ui, self.speaker, self.ears = ui, None, None
        self.listening, self.talk, self.followup = ui.cfg["voice_on"], ui.cfg["speak_replies"], False
        self.pending_speech = []

    @property
    def level(self):
        return self.ears.level if self.ears else 0.0

    def speak(self, text):
        from .preferences import quiet
        if quiet(self.ui.cfg):return
        if self.talk and text:
            if self.ears:
                self.ears.remember_reply(text)
            if self.speaker:
                self.speaker.speak(text)
            else:
                self.pending_speech.append(text)

    def flush_speech(self):
        pending, self.pending_speech = self.pending_speech, []
        for text in pending:
            self.speak(text)

    def set_listening(self, on):
        self.listening = on
        if self.ears:
            self.ears.paused_until = 0.0 if on else float("inf")
        self.ui.set_note("Listening for 'Jarvis'." if on else "Microphone is OFF: I'm not listening.")

    def set_volume(self, v):
        self.speaker and self.speaker.v.set_volume(v)

    def set_speed(self, s):
        self.speaker and self.speaker.v.set_speed(s)

    def set_replies(self, r):
        self.speaker and self.speaker.v.set_replies(r)

    def set_voice(self, name):
        self.speaker and self.speaker.v.set_voice(name)

    def shutdown(self):
        self.ears and self.ears.shutdown()
        self.speaker and self.speaker.shutdown()


class Api(v1.Api):
    """V1's page calls, plus the Knowledge tab."""

    def knowledge(self):
        return self._app.knowledge()

    def diagnostics(self):
        return self._app.engine.last_report

    def submit(self, text):
        self._app.interrupt(str(text))
        super().submit(text)

    def forget_word(self, heard):
        self._app.engine.memory.alias_delete(heard)

    def forget_habit(self, pattern):
        self._app.engine.memory.habit_delete(pattern)

    def forget_routine(self, name):
        self._app.engine.memory.routine_forget(name)

    def forget_note(self, id):
        row = self._app.store.get(int(id))
        if row and row['kind'] == 'note':
            self._app.store.delete(int(id))
            self._app.q.put(('refresh', None))

    def update_note(self, id, text):
        row = self._app.store.get(int(id))
        text = str(text).strip()
        if not row or row['kind'] != 'note' or not text or len(text) > 500:
            return {'ok': False, 'message': 'Please enter a saved fact of up to 500 characters.'}
        from .abilities.personal import spoken_symbols, fact_value
        text = spoken_symbols(text)
        self._app.store.rename(int(id), text)
        self._app.engine.copy_text = fact_value(text)
        self._app.q.put(('refresh', None))
        return {'ok': True, 'snap': self._app.snapshot()}

    def save_fact(self, id, title, value, aliases=None):
        """Explicit form entry: adding a fact must never fuzzy-merge another.
        Store the familiar sentence so voice recall and updates use it too.
        """
        from jarvis.store import note_label
        from .abilities.personal import spoken_symbols, fact_value
        try:
            id = int(id) if id is not None else None
        except (ValueError, TypeError):
            return {'ok': False, 'message': 'That fact could not be found.'}
        title, value = str(title).strip(), str(value).strip()
        text = f'my {title} is {value}' if title else value
        if not value or len(title) > 60 or len(text) > 500 or '\n' in title:
            return {'ok': False, 'message': 'Enter a heading up to 60 characters and a fact up to 500 characters in total.'}
        text = spoken_symbols(text)
        with self._app.store.lock:
            if aliases is not None:
                if not isinstance(aliases,list) or len(aliases)>8 or any(not isinstance(a,str) or not a.strip() or len(a)>60 for a in aliases):
                    return {'ok':False,'message':'Use up to eight alternate names, each up to 60 characters.'}
                for alias in aliases:
                    if any(r['id']!=id for r in self._app.store.notes(alias)):
                        return {'ok':False,'message':'An alternate name already matches another fact.'}
            row = self._app.store.get(int(id)) if id is not None else None
            if id is not None and (not row or row['kind'] != 'note'):
                return {'ok': False, 'message': 'That fact was removed. Add it again.'}
            label = note_label(text)
            from jarvis.store import tokens
            if title and any(r['id']!=id and any(tokens(title)==tokens(a) for a in r['aliases']) for r in self._app.store.fact_infos()):
                return {'ok':False,'message':'That heading is already an alternate name for another fact. Edit that fact or choose another heading.'}
            if any(r['id'] != id and ((label and note_label(r['text']) == label) or r['text'] == text) for r in self._app.store.notes('')):
                return {'ok': False, 'message': 'That heading already exists. Edit that fact or choose another heading.'}
            if row:
                self._app.store.rename(int(id), text)
            else:
                row=self._app.store.add(text, kind='note', merge=False)[0]
                id=row['id']
            if aliases is not None:self._app.store.set_aliases(id,aliases)
        self._app.engine.copy_text = fact_value(text)
        self._app.q.put(('refresh', None))
        return {'ok': True, 'snap': self._app.snapshot()}

    def copy_note(self, id):
        from .abilities.personal import fact_value
        row = self._app.store.get(int(id))
        value = fact_value(row['text']) if row and row['kind'] == 'note' else ''
        return bool(value and self._app.engine.os.clipboard_write(value))

    def set_theme(self, theme):
        return self._app.set_theme(theme)

    def backups(self):
        from pathlib import Path
        folder=Path(getattr(self._app,'backup_folder',os.path.join(ROOT,'data/backups')))
        return sorted([p.name for p in folder.glob('*.zip')],reverse=True)

    def create_backup(self):
        from .backup import create
        return create(self._app.store,self._app.engine.memory,getattr(self._app,'backup_folder',os.path.join(ROOT,'data/backups')))

    def restore_backup(self,name,confirmed=False):
        if confirmed is not True:return {'ok':False,'message':'Please confirm restoring this backup.'}
        from .backup import restore
        try:
            safety=restore(self._app.store,self._app.engine.memory,getattr(self._app,'backup_folder',os.path.join(ROOT,'data/backups')),str(name))
            self._app.engine.pending=None; self._app.engine.dialogue=__import__('jarvis2.dialogue',fromlist=['Dialogue']).Dialogue()
            self._app.alerts.clear(); self._app.engine.copy_text=''
            self._app.q.put(('refresh',None))
            return {'ok':True,'message':'Restored. Your previous data is backed up as '+safety}
        except Exception as error:return {'ok':False,'message':str(error)}

    def save_routine(self,name,text):
        from types import SimpleNamespace
        from .abilities.skills import skill_teach
        from .awareness import build
        engine=self._app.engine; now=datetime.now()
        ctx=SimpleNamespace(app=engine,memory=engine.memory,now=now,snapshot=build(engine.os,engine.store,engine.catalog,now,engine.history,engine.mentioned,media=False))
        result=skill_teach({'name':str(name),'steps':str(text)},ctx)
        return {'ok':result.ok,'message':result.plain}

    def teach_name(self,heard,target):
        from .names import clean
        engine=self._app.engine; heard=clean(str(heard)); target=clean(str(target))
        if not heard or len(heard)>60 or target not in engine.catalog:return False
        engine.memory.alias_correct(heard,target,engine.catalog[target],datetime.now())
        return True

    def forget_all(self):
        return self._app.engine.memory.clear_learned()

    def set_learning(self, on):
        self._app.engine.memory.set_paused(not on)

    def preferences(self,values=None):
        if values is not None:
            import re
            for key in ('quiet_enabled','cool_mode','daily_briefing','save_voice_clips'):
                if isinstance(values.get(key),bool):self._app.cfg[key]=values[key]
            for key in ('quiet_start','quiet_end'):
                if isinstance(values.get(key),str) and re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',values[key]):self._app.cfg[key]=values[key]
            settings.save(self._app.cfg)
            if self._app.voice.ears:self._app.voice.ears.clips_dir=os.path.join(ROOT,'data/clips') if self._app.cfg.get('save_voice_clips') else None
        return {k:self._app.cfg.get(k,settings.DEFAULTS.get(k)) for k in ('quiet_enabled','quiet_start','quiet_end','cool_mode','daily_briefing','save_voice_clips')}

    def google_status(self):
        return self._app.engine.google.status()

    def connect_google(self):
        import webview
        paths=self._app.window.create_file_dialog(webview.FileDialog.OPEN,allow_multiple=False,file_types=('Google Desktop OAuth client (*.json)',))
        if not paths:return 'No file selected.'
        try:
            if os.path.getsize(paths[0])>65536:return 'That configuration file is too large.'
            with open(paths[0],encoding='utf-8') as file:configuration=json.load(file)
            self._app.engine.google.connect(configuration,lambda url:self._app.engine.os.url('edge',url))
            return 'Continue sign-in in your browser. Then refresh connection status.'
        except Exception:return 'Choose a Google Desktop OAuth client JSON file with Gmail and Calendar APIs enabled.'

    def disconnect_google(self):
        self._app.engine.google.disconnect()
        return self.google_status()

    def read_google(self,service):
        try:return {'ok':True,'items':self._app.engine.google.read(service)}
        except Exception:return {'ok':False,'message':'Could not read Google. Check your account connection and permissions.'}

    def performance(self):
        import psutil
        process=psutil.Process()
        ram=process.memory_info().rss
        for child in process.children(recursive=True):
            try:ram+=child.memory_info().rss
            except psutil.Error:pass
        samples=list(self._app.engine.timing_samples)
        times=sorted(s['understand']+s['act'] for s in samples)
        return {'ram_mb':round(ram/1024**2),'requests':len(times),'median_ms':times[len(times)//2] if times else None,'p95_ms':times[min(len(times)-1,int(len(times)*.95))] if times else None,
                'last':samples[-1] if samples else None,'speech':getattr(self._app,'last_hearing',None)}

    def read_document(self):
        import webview
        from .documents import read
        paths=self._app.window.create_file_dialog(webview.FileDialog.OPEN,allow_multiple=False,file_types=('Documents (*.txt;*.md;*.csv;*.docx;*.pdf)',))
        if not paths:return {'ok':False,'message':'No file selected.'}
        try:return {'ok':True,**read(paths[0])}
        except Exception as error:return {'ok':False,'message':str(error)}

    def refresh_apps(self):
        self._app.refresh_apps()
        return 'Refreshing installed apps in the background.'


class UiApp(v1.App):
    def __init__(self, gui=True, tray=True):
        self.store = Store(os.path.join(ROOT, "data", "jarvis.db"))
        self.cfg = settings.load()
        settings.apply(self.cfg)
        self.q = queue.Queue()
        self._catalog_refresh = threading.Lock()
        self._chatted, self._spoken = False, False
        self.history, self.recent = [], []
        self.state_name, self.text, self.hide_at, self.note = "idle", "", 0.0, "Loading my ears and voice..."
        self.alerts, self.booting = [], True
        self.window, self.page_ready, self.visible, self.sent, self._last = None, False, False, [], None
        self.island = None
        if gui:
            from jarvis.island import Island
            self.island = Island(lambda m: self.q.put(m), theme="paper")
            self.island.set_theme('dark' if self.cfg.get('theme') == 'dark' else 'paper')
        self.engine = App(Real(), self.store, AI(), Memory(os.path.join(ROOT, "data", "jarvis2.db"), os.path.join(ROOT, "data", "settings2.json")), natural=self.cfg["natural_replies"], chat_ai=AI(CHAT_MODEL, n_ctx=2048))
        from .google_connection import GoogleConnection
        self.engine.google=GoogleConnection()
        self.voice, self.brain, self.icon = Voice(self), None, None
        self.engine.on_progress = self._render
        self.expect_answer = False
        if tray:
            self._tray()
        self._add("Jarvis", "Starting up, sir. Typing already works; my ears and voice need about ten seconds.", "sys")
        self._render()
        threading.Thread(target=self._boot, daemon=True).start()

    # ----- loading the ears and the voice in the background -----
    def _boot(self):
        try:
            stt = Transcriber()
            stt.load()
            speaker = Speaker(on_idle=self._reply_over, volume=self.cfg["tts_volume"], voice=self.cfg["tts_voice"], replies=self.cfg["wake_replies"])
            speaker.load()
            speaker.v.set_speed(self.cfg["tts_speed"])
            names, sites = self.engine.common_names()
            threading.Thread(target=speaker.premake, args=(names, sites), daemon=True).start()
            self.voice.speaker = speaker
            self.engine.speech = speaker
            self.engine.ai.load()
            loop = LoopRing()
            ears = Ears(MicStream(speaker.close_out), loop, stt, self._heard, hint=lambda:self.engine.names.hint(), clips_dir=os.path.join(ROOT, "data", "clips"))
            ears.reply_words = list(self.cfg["wake_replies"])
            ears.on_problem=lambda text:self.q.put(('notice',text))
            if not self.cfg.get('save_voice_clips'):ears.clips_dir=None
            self._warming = threading.Lock()
            ears.on_state = self._warm_ai
            self.voice.ears = ears
            ears.is_complete = self.engine.is_complete
            self.engine.set_mic = lambda on: (self.voice.set_listening(on) if on else setattr(ears, "paused_until", time.monotonic() + 600)) or True
            if not self.voice.listening:
                ears.paused_until = float("inf")
            ears.start()
            self.q.put(("ready", stt.device))
            threading.Thread(target=self._housekeeping, daemon=True).start()
        except Exception as ex:
            _log(ex)
            self.q.put(("error", f"My ears or voice failed to load: {ex}"))

    def _reply_over(self):
        """Extend an already-open wake/question window from the end of speech.
        Never open a fresh window after an ordinary reply or consumed answer.
        """
        if self.voice.ears and self.voice.ears.wake_pending:
            self.voice.ears.arm(since=self.voice.ears.armed_from)
            self.q.put(('refresh', None))
        elif self.voice.ears and self.expect_answer and self.voice.ears.armed_until > 0:
            self.expect_answer = False
            self.voice.ears.arm(since=self.voice.ears.armed_from)
            self.q.put(('refresh', None))

    def _warm_ai(self, state):
        if self.cfg.get('cool_mode'):return
        if state != 'hearing' or self.engine.ai.loaded or not self._warming.acquire(blocking=False):
            return
        def warm():
            try:
                self.engine.ai.load()
            finally:
                self._warming.release()
        threading.Thread(target=warm, daemon=True).start()

    def _housekeeping(self):
        """Once a minute: free the AI after 15 idle minutes, and maybe offer a habit (a question, only while everything is quiet)."""
        while True:
            time.sleep(OFFER_EVERY_S)
            try:
                self.engine.maybe_unload(3 if self.cfg.get('cool_mode') else 15)
                sp = self.voice.speaker
                if self.state_name == "idle" and self.q.empty() and sp and not sp.busy:
                    self.q.put(("offer", None))
                if self.cfg.get('daily_briefing') and self.cfg.get('briefed_on')!=datetime.now().date().isoformat():
                    from .preferences import quiet
                    if not quiet(self.cfg) and self.state_name=='idle' and self.q.empty() and sp and not sp.busy:
                        self.cfg['briefed_on']=datetime.now().date().isoformat(); settings.save(self.cfg)
                        self.q.put(('typed','daily briefing'))
            except Exception:
                _log()

    def refresh_apps(self):
        if not self._catalog_refresh.acquire(blocking=False):return
        def refresh():
            try:
                actions.start_apps(True)
                self.q.put(('catalog',self.engine.os.catalog()))
            except Exception:self.q.put(('notice','Could not refresh installed apps.'))
            finally:self._catalog_refresh.release()
        threading.Thread(target=refresh,daemon=True).start()

    # ----- what the page shows about what Jarvis learned -----
    def _render(self):
        super()._render()
        if self.island and not self.booting and self.snapshot()['state'] == 'listening':
            self.island.show('listening')

    def _tick(self, n, wait=0.0):
        super()._tick(n, wait)
        if self.island and self.voice:
            self.island.level = min(1, max(.1, self.voice.level * 25))

    def snapshot(self):
        from .organizer import rows
        snap = super().snapshot()
        snap['theme'] = self.cfg.get('theme', 'light')
        ears = self.voice.ears
        remaining = max(0, ears.armed_until - time.monotonic()) if ears else 0
        if ears and not remaining:
            ears.wake_pending = False
        snap['listen_left'] = round(remaining, 1)
        if remaining and self.voice.listening and snap['state'] not in ('thinking',):
            snap['state'] = 'listening'
        elif snap['state'] == 'listening':
            snap['state'] = 'idle'
        snap['personal'] = self.store.fact_infos(limit=8,public=True)
        snap['events'] = [r for r in rows(self.engine.memory, 'commitments') if r['status'] == 'active']
        snap['jobs'] = rows(self.engine.memory, 'jobs')[:8]
        return snap

    def knowledge(self):
        m = self.engine.memory
        words = [w for w in m.aliases() if w["source"] == "correction" or w["uses"] >= 3]
        habits = []
        for h in m.habits():
            target, hour = h["pattern"].split(":", 1)[1].split("@")
            habits.append({**h, "text": f"You usually open {target} around {int(hour):02d}:00"})
        routines = [{"name": n, "steps": ", ".join(s["args"].get("text", "") if s["a"] == "say" else s["a"].replace("_", " ") + (f" {s['args'].get('target', '')}" if s["args"].get("target") else "") for s in m.routine_steps(n)).strip()} for n in m.routines()]
        notes = self.store.fact_infos()
        for routine in routines:
            steps=m.routine_steps(routine['name'])
            routine['sentences']=[s['args']['text'] if s['a']=='say' else s['a'].replace('_',' ')+' '+str(s['args'].get('target',s['args'].get('duration',''))) for s in steps]
            state=m._q('SELECT state FROM routine_progress WHERE name=?',routine['name'])
            routine['state']=state[0][0] if state else 'ready'
        return {"paused": m.paused, "words": words, "usage": m.usage_top(6), "habits": habits, "routines": routines, "notes": notes}

    # ----- commands -----
    def interrupt(self, text):
        if re.fullmatch(r'(?:stop|cancel) (?:my |the )?(?:plan|task)(?: #?\d+)?[.!]?', text.strip(), re.I):
            self.engine.cancel_goal.set()
        if text and self.voice.speaker:
            self.voice.speaker.stop()

    def _heard(self, heard):
        self.interrupt(heard.text)
        self.q.put(('heard', heard))

    def submit(self, text="", spoken=False, trigger="typed", clip_id=None):
        text = (text or "").strip()
        if not text:
            return
        self._spoken = spoken
        self._add("You", text, "you")
        self.state("thinking")
        try:
            r = self.engine.handle(text, trigger if spoken else "typed", clip_id)
        except Exception:
            _log()
            self.say("Something went wrong, sir. It's in the log.", "err")
            return
        calls = "; ".join(f"{c.ability}({', '.join(f'{k}={v}' for k, v in c.args.items())})" for c, _ in r.results)
        self._add("Understood as", f"{calls or r.plan.kind} [{r.plan.source or '-'}; {r.ms['understand']}+{r.ms['act']} ms; wording: {r.how or '-'}]", "sys")
        if r.error:
            self._add("Error", r.error.strip().splitlines()[-1], "err")
        self.expect_answer = bool(r.plan.kind == "ask" or self.engine.pending) and spoken
        if self.expect_answer and self.voice.ears:
            # Open BEFORE the question is spoken. Otherwise the UI appears to
            # listen while the first answer is thrown away as "too early".
            self.voice.ears.arm(since=getattr(self, '_heard_end', self.voice.ears.clock))
        if r.text:
            self.say(r.text, "jarvis" if r.ok else "err")
        else:
            self.state("idle")
        if self.engine.exit_requested:                        # "shut down": say goodbye, then close completely
            threading.Timer(1.3, self.q.put, ("quit",)).start()

    def save_settings(self, new):
        out = super().save_settings(new)
        self.engine.natural = bool(self.cfg.get("natural_replies", True))
        return out

    def set_theme(self, theme):
        if theme not in ('light', 'dark'):
            return self.cfg.get('theme', 'light')
        self.cfg['theme'] = theme
        settings.save(self.cfg)
        if self.island:
            self.island.set_theme('dark' if theme == 'dark' else 'paper')
        if self.window and self.page_ready:
            self._window_theme()
        self.q.put(('refresh', None))
        return theme

    def _voice_msg(self, kind, p):
        if kind == "ready":
            self.booting = False
            self.note = "Listening for 'Jarvis'." if self.voice.listening else "Microphone is OFF."
            if self.voice.pending_speech:
                self.voice.flush_speech()
            else:
                self.voice.speak("Ready, sir.")
            self._add("Jarvis", f"Ready ({p}). Say \"Jarvis\" and your command, e.g. \"Jarvis, open YouTube\". Or just \"Jarvis\" and wait for me.", "sys")
            self._render()
        elif kind == "heard":
            self.last_hearing={'transcribe_ms':p.stt_ms,'delivery_ms':p.wait_ms}
            self._heard_end = p.ended
            self.expect_answer = False
            if not p.text:                                    # the name alone
                self.text = ''
                self.state('listening')
                from .preferences import quiet
                ms = self.voice.speaker.wake() if self.voice.speaker and not quiet(self.cfg) else None
                self._add("Wake word", f"heard {p.raw!r}; 'Yes, sir' reached the speaker in {ms} ms.", "sys")
            else:
                self.submit(p.text, spoken=True, trigger=p.trigger, clip_id=p.clip_id)
        elif kind == 'refresh':
            self._render()
        elif kind == 'notice':
            self.set_note(p)
        elif kind == 'catalog':
            self.engine.set_catalog(p)
            self.set_note("Installed apps refreshed. Listening for 'Jarvis'.")
        elif kind == "offer":
            line = self.engine.offer()
            if line:
                self.say(line)
        elif kind == "add_timer":
            from types import SimpleNamespace

            from .abilities.timers import timer_set
            timer_set({"duration": int(p)}, SimpleNamespace(store=self.store, now=datetime.now()))
            self._render()
        elif kind == "error":
            self.booting = False
            self._add("Voice", p, "err")
            self.set_note(p)
        else:
            super()._voice_msg(kind, p)

    def _fire(self):
        """A timer or reminder comes due: it is SPOKEN and shown on the pill, and the window stays where it is."""
        rows = []
        said = v1.announce_due(self.store, fired=rows)
        if not rows:
            return
        for r in rows:
            timer = r["kind"] == "timer"
            self.alerts.append({"id": r["id"], "kind": r["kind"], "title": f"Your {r['text'].replace('-', ' ')} timer is up" if timer else r["text"],
                                "sub": "Time's up, sir." if timer else "Reminder, sir.", "face": "00:00" if timer else datetime.now().strftime("%H:%M")})
        self.say("\n".join(said), "rem")

    def alert_action(self,what):
        if self.alerts:
            row=self.store.get(self.alerts[0]['id'])
            repeat=self.store.db.execute('SELECT days FROM repeats WHERE item_id=?',(row['id'],)).fetchone() if row else None
            if repeat:
                self.alerts.pop(0)
                if what=='snooze':
                    from datetime import timedelta
                    self.store.add(row['text'],datetime.now()+timedelta(minutes=5),'reminder',merge=False)
                return
        super().alert_action(what)

    def quit(self):
        try:
            self.engine.ai.unload()
            if self.engine.chat_ai:
                self.engine.chat_ai.unload()
        except Exception:
            pass
        super().quit()

    def _on_shown(self):
        super()._on_shown()
        self._window_theme()

    def _window_theme(self):
        dark = self.cfg.get('theme') == 'dark'
        for attr, color in ((20, int(dark)), (35, 0x001D1917 if dark else 0x00E8F0F3), (36, 0x00E8F0F3 if dark else 0x0028231C)):
            value = ctypes.c_int(color)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(self._hwnd()), attr, ctypes.byref(value), 4)


def launch(app, debug=False):
    import webview
    url = "file:///" + os.path.join(WEB, "app.html").replace("\\", "/")
    # .NET Uri treats '?' in file URLs as part of the filename, so use a
    # fragment for startup state. Otherwise WebView2 loads app.html%3Ftheme=...
    url += '#theme=' + app.cfg.get('theme', 'light')
    w = app.window = webview.create_window("Jarvis V2", url, js_api=Api(app), width=1180, height=760, min_size=(720, 520), background_color="#17191d" if app.cfg.get('theme') == 'dark' else "#f3f0e8")
    w.events.closing += app._on_closing
    w.events.shown += app._on_shown
    w.events.minimized += lambda: app._push("window.jarvisMotionPaused=true;dispatchEvent(new Event('jarvismotionchange'))")
    w.events.restored += lambda: app._push("window.jarvisMotionPaused=false;dispatchEvent(new Event('jarvismotionchange'))")
    threading.Thread(target=app.run, daemon=True).start()
    webview.start(debug=debug, private_mode=True)
    os._exit(0)


def main():
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Jarvis2.Assistant")
    os.makedirs("data", exist_ok=True)
    app=UiApp();app.refresh_apps();launch(app)
