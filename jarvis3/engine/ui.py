"""V2's window, pill and tray. The faces are V1's (the web page in jarvis3.engine/web with a Knowledge tab, the island, the tray); the brain behind them is V2's App.
UiApp is V1's App with its engine swapped: submit() asks jarvis3.engine.App.handle, the ears and the speaker sit behind the same `voice` calls V1's page already uses."""
import ctypes
import json
import os
import queue
import re
import threading
import time
import traceback
from datetime import datetime

from . import settings as _settings  # noqa: F401  (points V1's settings code at settings3.json)
from jarvis3.legacy import actions, settings, ui as v1
from jarvis3.legacy.store import Store

from .ai import AI, CHAT_MODEL
from .app import App
from .ears import Ears, LoopRing, MicStream, Transcriber
from .memory import Memory
from .osapi import Real
from .speaker import Speaker

from jarvis3.paths import RUNTIME, PROJECT, ASSETS
ROOT = str(RUNTIME)
WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
from jarvis3.paths import ASSETS
ICON = str(ASSETS / "jarvis-v3-reactor.ico")
OFFER_EVERY_S = 60


def _log(e=None):
    os.makedirs("logs", exist_ok=True)
    with open(os.path.join("logs", "jarvis3.engine.log"), "a", encoding="utf-8") as f:
        f.write(traceback.format_exc() + "\n")


class Voice:
    """What V1's page and settings expect of `voice`, on top of V2's ears and speaker."""

    def __init__(self, ui):
        self.ui, self.speaker, self.ears = ui, None, None
        self.listening, self.talk, self.followup = ui.cfg["voice_on"], ui.cfg["speak_replies"], False
        self.pending_speech = []
        from collections import deque
        self.consumed=deque(maxlen=64)

    @property
    def level(self):
        return self.ears.level if self.ears else 0.0

    @property
    def out_level(self):
        """How loud Jarvis's own voice is right now (0..1): the living presence pulses with it."""
        return getattr(getattr(self.speaker, 'v', None), 'out_level', 0.0) if self.speaker else 0.0

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
            if not on:self._clear_capture()
        self.ui.set_note("Listening for 'Jarvis'." if on else "Microphone is OFF: I'm not listening.")

    def _clear_capture(self):
        self.ears.invalidate_capture()
        self.ui.conversation.dismiss();self.ui.expect_answer=False
        self.ui.engine.pending=None;self.ui.engine.context_pending=None
        self.ui.engine.dialogue.cancel_timer_choices()

    def pause_listening(self,seconds=600):
        if not self.ears:return False
        self.ears.paused_until=time.monotonic()+seconds
        self._clear_capture()
        self.ui.set_note("Microphone paused for ten minutes. I'm not listening.")
        return True

    def can_listen(self):
        return bool(self.listening and self.ears and not self.ears.stop and time.monotonic()>=self.ears.paused_until)

    def accepts(self,heard):
        if not self.can_listen() or getattr(heard,'capture_epoch',0)!=self.ears.capture_epoch or self.speech_key(heard) in self.consumed:return False
        generation=getattr(heard,'conversation_generation',None)
        if generation==self.ui.conversation.generation:return True
        return self.ui.conversation.independent(generation) and self.independent_named(heard)

    @staticmethod
    def speech_key(heard):
        return (heard.capture_epoch,heard.conversation_generation,heard.started,heard.ended)

    def independent_named(self,heard):
        # Bare yes/no, undo, pronouns, player choices and arbitrary routines
        # remain bound to their original question/task, even with a name.
        if heard.trigger!='name' or not heard.text.strip():return False
        from jarvis3.control import assistant_exit
        if assistant_exit(heard.text):return True
        from .understand import instant
        allowed={'open','close','focus','window_state','timer_set','reminder_add','note_save','volume','volume_read','clock','workspace_run','workspace_resume','stop_talking'}
        try:
            hit=instant(heard.text,self.ui.engine.names)
            return bool(hit and hit[1] and all(name in allowed and (name not in ('open','close','focus') or args.get('target') in self.ui.engine.catalog) for name,args in hit[1]))
        except Exception:return False

    def consume(self,heard):
        self.consumed.append(self.speech_key(heard))

    def set_volume(self, v):
        self.speaker and self.speaker.v.set_volume(v)

    def set_speed(self, s):
        self.speaker and self.speaker.v.set_speed(s)

    def set_replies(self, r):
        self.speaker and self.speaker.v.set_replies(r)

    def set_voice(self, name):
        self.speaker and self.speaker.v.set_voice(name)

    def shutdown(self):
        self.ui.engine.dialogue.cancel_timer_choices()
        self.ui._stop_arrival_watch()
        self.ears and self.ears.shutdown()
        self.speaker and self.speaker.shutdown()
        if self.ears and not any(t.is_alive() for t in self.ears.threads):
            unload=getattr(self.ears.stt,'unload',None)
            if unload:unload()


class Api(v1.Api):
    """V1's page calls, plus the Knowledge tab."""

    def knowledge(self):
        return self._app.knowledge()

    def diagnostics(self):
        return self._app.engine.last_report

    def workspaces(self):
        from jarvis3.workspaces import profiles
        return profiles(self._app.engine.memory)

    def music_settings(self,values=None):
        from jarvis3.music import destination
        if values is not None:
            if not isinstance(values,dict):return {'ok':False,'message':'Choose a music link and browser.'}
            try:
                url=destination(values.get('url','')) if values.get('url','').strip() else ''
                browser=values.get('browser','edge')
                if browser not in ('edge','chrome'):raise ValueError('Choose Edge or Chrome.')
                self._app.cfg.update(music_url=url,music_browser=browser);settings.save(self._app.cfg)
            except (ValueError,TypeError,AttributeError):return {'ok':False,'message':'Use a full https YouTube video, mix or playlist link.'}
        return {'ok':True,'url':self._app.cfg.get('music_url',''),'browser':self._app.cfg.get('music_browser','edge'),'message':'Saved.' if values is not None else ''}

    def choose_workspace_folder(self):
        import webview
        from jarvis3.workspaces import folder_path
        paths=self._app.window.create_file_dialog(webview.FileDialog.FOLDER,allow_multiple=False)
        if not paths:return None
        path=folder_path(paths[0])
        if not hasattr(self._app,'_picked_workspace_folders'):self._app._picked_workspace_folders=set()
        self._app._picked_workspace_folders.add(path)
        return path

    def save_workspace(self,name,apps,urls,browser,folders=None,aliases=None):
        from jarvis3.workspaces import save,profiles,folder_path
        try:
            folders=[] if folders is None else folders
            if not isinstance(folders,list):raise ValueError('Invalid folders')
            folders=[folder_path(p) for p in folders]
            allowed=getattr(self._app,'_picked_workspace_folders',set())|{p for row in profiles(self._app.engine.memory) for p in row.get('folders',[])}
            if any(p not in allowed for p in folders):raise ValueError('Choose folders using the picker first')
            save(self._app.engine.memory,name,apps,urls,browser,self._app.engine.catalog,folders,aliases)
            return {'ok':True,'message':'Saved. The first run will show the steps and ask before opening anything.'}
        except (ValueError,TypeError):return {'ok':False,'message':'Check the name, installed apps and website links. Use up to eight steps.'}

    def v3_status(self,values=None):
        if values:
            for key in ('audible_cues','prefix_wake','conversation_followups','arrival_greeting','minimal_feedback','do_not_disturb','early_interrupts','clipboard_context','only_my_voice','camera_arrival'):
                if isinstance(values.get(key),bool):self._app.cfg[key]=values[key]
            minutes=values.get('hands_free_minutes')
            if isinstance(minutes,(int,float)) and not isinstance(minutes,bool):self._app.cfg['hands_free_minutes']=min(60,max(0,int(minutes)))
            self._app._apply_voice_options()
            self._app._sync_arrival_option()
            settings.save(self._app.cfg)
            pending=getattr(self._app.engine,'context_pending',None)
            if not self._app.cfg['clipboard_context'] and pending and pending.get('kind')=='clipboard':self._app.engine.context_pending=None
            if self._app.voice.ears:self._app.voice.ears.prefix_wake=self._app.cfg['prefix_wake']
            reason=self._app.conversation.reason
            if (reason=='reply' and not self._app.cfg['conversation_followups']) or (reason=='arrival' and not self._app.cfg['arrival_greeting']) or (reason=='interrupt' and not self._app.cfg['early_interrupts']):
                self._app.conversation.dismiss()
                if self._app.voice.ears:self._app.voice.ears.armed_until=0;self._app.voice.ears.barge_until=0
        from jarvis3 import VERSION
        return {'version':f'V{VERSION}','phase':'Jarvis V4 development',
                'audible_cues':self._app.cfg['audible_cues'],'prefix_wake':self._app.cfg['prefix_wake'],
                **{k:self._app.cfg[k] for k in ('conversation_followups','arrival_greeting','minimal_feedback','do_not_disturb','early_interrupts','clipboard_context')},
                'conversation':self._app.conversation.snapshot(),
                'only_my_voice':self._app.cfg.get('only_my_voice',False),'voice':self._app._voice_status(),
                'camera_arrival':self._app.cfg.get('camera_arrival',False),'camera':self._app._camera.status if self._app._camera else 'off',
                'hands_free_minutes':self._app.cfg.get('hands_free_minutes',0),
                'events':self._app.feedback.snapshot()}

    def submit(self, text):
        from jarvis3.control import assistant_exit
        if assistant_exit(text):self._app._request_shutdown();return
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
        text = str(text)
        if not row or row['kind'] != 'note' or not text.strip() or len(text) > 4096 or '\0' in text:
            return {'ok': False, 'message': 'Please enter a saved fact of up to 4096 characters.'}
        from .abilities.personal import row_value
        self._app.store.rename(int(id), text)
        self._app.engine.copy_text = row_value(self._app.store.get(int(id)),self._app.store)
        self._app.q.put(('refresh', None))
        return {'ok': True, 'snap': self._app.snapshot()}

    def save_fact(self, id, title, value, aliases=None, link=False):
        """Explicit form entry: adding a fact must never fuzzy-merge another.
        Store the familiar sentence so voice recall and updates use it too.
        """
        from jarvis3.legacy.store import note_label
        try:
            id = int(id) if id is not None else None
        except (ValueError, TypeError):
            return {'ok': False, 'message': 'That fact could not be found.'}
        title, value = str(title).strip(), str(value)
        if link:
            from .knowledge import describe, website_url
            url = website_url(value)
            if not title or not url or describe(f'my {title} is {url}')['type'] != 'website':
                return {'ok': False, 'message': 'Enter a short name and a valid website address.'}
            value = url
        text = f'my {title} is {value}' if title else value
        if not value.strip() or len(title) > 60 or len(value)>4096 or any(ord(c)<32 for c in title) or '\0' in text:
            return {'ok': False, 'message': 'Enter a heading up to 60 characters and information up to 4096 characters.'}
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
            from jarvis3.legacy.store import tokens
            if title and any(r['id']!=id and any(tokens(title)==tokens(a) for a in r['aliases']) for r in self._app.store.fact_infos()):
                return {'ok':False,'message':'That heading is already an alternate name for another fact. Edit that fact or choose another heading.'}
            if any(r['id'] != id and ((label and note_label(r['text']) == label) or r['text'] == text) for r in self._app.store.notes('')):
                return {'ok': False, 'message': 'That heading already exists. Edit that fact or choose another heading.'}
            if row:
                self._app.store.rename(int(id), text)
            else:
                row=self._app.store.add(text, kind='note', merge=False)[0]
                id=row['id']
            if title:
                self._app.store.db.execute("INSERT INTO note_meta(note_id,source) VALUES(?,'user') ON CONFLICT(note_id) DO UPDATE SET source='user'",(id,));self._app.store.db.commit()
            if aliases is not None:self._app.store.set_aliases(id,aliases)
        from .abilities.personal import row_value
        self._app.engine.copy_text = row_value(self._app.store.get(id),self._app.store)
        self._app.q.put(('refresh', None))
        return {'ok': True, 'snap': self._app.snapshot()}

    def copy_note(self, id):
        from .abilities.personal import row_value
        row = self._app.store.get(int(id))
        value = row_value(row,self._app.store) if row and row['kind'] == 'note' else ''
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
            self._app.engine.pending=None; self._app.engine.dialogue=__import__('jarvis3.engine.dialogue',fromlist=['Dialogue']).Dialogue()
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

    def save_routine_pills(self, name, revision, entries):
        from types import SimpleNamespace
        from .awareness import build
        from .routine_editor import save
        engine = self._app.engine
        now = datetime.now()
        snapshot = build(engine.os, engine.store, engine.catalog, now, engine.history, engine.mentioned, media=False)
        ctx = SimpleNamespace(app=engine, memory=engine.memory, now=now, snapshot=snapshot)
        return save(str(name), revision, entries, ctx)

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
        self.store = Store(os.path.join(ROOT, "data", "facts.db"))
        self.cfg = settings.load()
        settings.apply(self.cfg)
        from jarvis3.control import ControlQueue,CANCEL_INFERENCE
        CANCEL_INFERENCE.clear()
        self.q = ControlQueue()
        self._shutdown_requested=threading.Event()
        self._closing=threading.Event()
        self._catalog_refresh = threading.Lock()
        self._chatted, self._spoken = False, False
        self.history, self.recent = [], []
        self.state_name, self.text, self.hide_at, self.note = "idle", "", 0.0, "Loading my ears and voice..."
        self.alerts, self.booting = [], True
        self.window, self.page_ready, self.visible, self.sent, self._last = None, False, False, [], None
        self.island = None
        if gui:
            from jarvis3.legacy.island import Island
            self.island = Island(lambda m: self.q.put(m), theme="paper")
            self.island.set_theme('dark' if self.cfg.get('theme') == 'dark' else 'paper')
        self.engine = App(Real(), self.store, AI(), Memory(os.path.join(ROOT, "data", "learning.db"), os.path.join(ROOT, "data", "settings3.json")), natural=self.cfg["natural_replies"], chat_ai=AI(CHAT_MODEL, n_ctx=2048))
        self.engine.context_options=self.cfg
        from .google_connection import GoogleConnection
        self.engine.google=GoogleConnection()
        self.voice, self.brain, self.icon = Voice(self), None, None
        from jarvis3.feedback import Feedback
        self.feedback=Feedback(self._cue)
        from jarvis3.conversation import Conversation,Arrival
        self.conversation=Conversation();self.arrival=Arrival()
        self._arrival_lock=threading.RLock();self._arrival_stop=threading.Event();self._arrival_thread=None
        self._arrival_source=None;self._arrival_attempted=False;self._arrival_enabled=bool(self.cfg.get('arrival_greeting'))
        self._arrival_epoch=0;self._arrival_pending=None;self._camera=None;self._voice_gate=None
        self._command_token=None
        self.engine.on_verified=self._verified
        from jarvis3.selection import Selection
        from jarvis3.overlay import TargetOverlay
        from jarvis3.browser_choices import BrowserChoices
        from jarvis3.music import Music
        provider=lambda:BrowserChoices(self.engine.os.a.backend)
        self.engine.music=Music(self.cfg,self.engine.os.url,provider,self.engine.stop_requested.is_set)
        self.engine.selection=Selection(provider,TargetOverlay,lambda:self.q.put(('notice','The visible choices changed. Ask me to number them again.')),self.engine.music.adopt)
        self.engine.os.screen_overlay=lambda:TargetOverlay(name='Screen',expires=30)   # V4: badges only over a 'which one?' shortlist
        self.engine.on_progress = self._render
        self.expect_answer = False
        if tray:
            self._tray()
        self._add("Jarvis", "Starting up, sir. Typing already works; my ears and voice need about ten seconds.", "sys")
        self._render()
        threading.Thread(target=self._boot, daemon=True).start()

    # ----- loading the ears and the voice in the background -----
    def _boot(self):
        stt=speaker=loop=ears=None
        try:
            stt = Transcriber()
            stt.load()
            if self._closing.is_set():raise RuntimeError('V3 voice startup cancelled')
            speaker = Speaker(on_idle=self._reply_over, volume=self.cfg["tts_volume"], voice=self.cfg["tts_voice"], replies=self.cfg["wake_replies"])
            speaker.load()
            speaker.on_tune=self._voice_tuned
            speaker.v.set_speed(self.cfg["tts_speed"])
            names, sites = self.engine.common_names()
            threading.Thread(target=speaker.premake, args=(names, sites), daemon=True).start()
            self.voice.speaker = speaker
            self.engine.speech = speaker
            self.engine.ai.load()
            loop = LoopRing()
            ears = Ears(MicStream(speaker.close_out), loop, stt, self._heard, hint=lambda:self.engine.names.hint(), clips_dir=os.path.join(ROOT, "data", "clips"))
            ears.reply_words = list(self.cfg["wake_replies"])
            ears.on_wake=self._wake
            ears.can_interrupt=lambda:bool(self.cfg.get('early_interrupts',True) and speaker.busy)
            ears.on_interrupt=self._early_interrupt
            ears.followup_filter=self._followup_allowed
            ears.conversation_generation=lambda:self.conversation.generation
            ears.prefix_wake=self.cfg['prefix_wake']
            self._apply_voice_options(ears)
            ears.on_problem=lambda text:self.q.put(('notice',text))
            if not self.cfg.get('save_voice_clips'):ears.clips_dir=None
            self._warming = threading.Lock()
            ears.on_state = self._warm_ai
            self.voice.ears = ears
            ears.is_complete = self.engine.is_complete
            self.engine.set_mic = self._set_mic
            if not self.voice.listening:
                ears.paused_until = float("inf")
            ears.start()
            self.q.put(("ready", stt.device))
            threading.Thread(target=self._housekeeping, daemon=True).start()
            self._arrival_thread=threading.Thread(target=self._arrival_watch,daemon=True)
            self._arrival_thread.start()
        except Exception as ex:
            _log(ex)
            for obj,method in ((ears,'shutdown'),(loop,'close'),(speaker,'shutdown'),(stt,'unload'),(self.engine.ai,'unload'),(self.engine.chat_ai,'unload')):
                if obj is not None:
                    try:getattr(obj,method)()
                    except Exception:_log()
            self.voice.ears=self.voice.speaker=None
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
        elif self.voice.ears and self.conversation.reason in ('reply','arrival','interrupt') and self.voice.ears.armed_until>0:
            self.conversation.open(self.conversation.reason)
            self.voice.ears.arm(since=self.voice.ears.armed_from)

    def _followup_allowed(self,text,eligible=False):
        # Explicit wake/question windows preserve first overlapping reply handling.
        if self.voice.ears.wake_pending or self.expect_answer:return True
        if self.voice.ears.hands_free_active():
            from jarvis3.conversation import DISMISS
            return bool(DISMISS.fullmatch(text.strip())) or self.engine.is_instant(text)   # known commands only: never chat, never the model
        return self.conversation.allowed(text,self.engine.is_complete,eligible=eligible)

    def _apply_voice_options(self,ears=None):
        ears=ears or self.voice.ears
        if not ears:return
        seconds = 60 * int(self.cfg.get('hands_free_minutes', 0) or 0)
        if seconds != ears.hands_free_s:
            ears.end_hands_free()
            ears.hands_free_s = seconds
        if not self.cfg.get('only_my_voice'):ears.voice_gate=None;return
        from jarvis3.voice_gate import VoiceGate
        gate=self._voice_gate or VoiceGate();self._voice_gate=gate
        if gate.ready():
            ears.voice_gate=gate
            ears.on_foreign=lambda text,score:self.q.put(('notice',f"Ignored, not your voice ({score:.2f}): {text}"))
        else:
            ears.voice_gate=None;self.cfg['only_my_voice']=False;self.q.put(('notice',gate.error))

    def _voice_status(self):
        ears=self.voice.ears
        if not self.cfg.get('only_my_voice'):return 'off'
        if ears and ears.voice_gate:return 'on, learned from your three stage-1 recordings'
        return self._voice_gate.error if self._voice_gate and self._voice_gate.error else 'waiting for the ears'

    def _open_conversation(self,reason):
        self.conversation.open(reason)
        if self.voice.ears:self.voice.ears.arm(since=self.voice.ears.clock if reason=='arrival' else getattr(self,'_heard_end',self.voice.ears.clock))

    def _sync_arrival_option(self):
        enabled=bool(self.cfg.get('arrival_greeting')) and not self._arrival_stop.is_set()
        with self._arrival_lock:
            if enabled==self._arrival_enabled:return
            self._arrival_enabled=enabled;self._arrival_epoch+=1;self._arrival_pending=None
            source=self._arrival_source;self._arrival_source=None;self._arrival_attempted=False
            self.arrival.away=False
        if source:source.close()

    def _stop_arrival_watch(self):
        self._arrival_stop.set()
        camera=self._camera;self._camera=None
        if camera:camera.close()
        with self._arrival_lock:
            self._arrival_epoch+=1;self._arrival_pending=None
            source=self._arrival_source;self._arrival_source=None
        if source:source.close()
        thread=self._arrival_thread
        if thread and thread is not threading.current_thread():thread.join(2)

    def _queue_arrival(self,kind,expected=None):
        with self._arrival_lock:
            source=self._arrival_source
            if not self.cfg.get('arrival_greeting') or not self._arrival_enabled or self._arrival_stop.is_set():return
            if expected is not None and expected!=(self._arrival_epoch,source):return
            payload={'at':time.monotonic(),'generation':self.conversation.generation,'option_epoch':self._arrival_epoch,
                     'session_generation':source.generation if source and source.available else None,'source':kind}
            self._arrival_pending=payload
            self.q.put(('arrival',payload))
            return payload

    def _arrival_permitted(self,source,idle):
        from .preferences import quiet
        sp=self.voice.speaker
        return bool(idle is not None and self.voice.can_listen() and self.voice.talk and sp and not sp.busy
                    and self.state_name=='idle' and not self.cfg.get('do_not_disturb') and not quiet(self.cfg)
                    and not (self.voice.ears and self.voice.ears.armed_until>time.monotonic())
                    and not (source and source.available and source.locked)
                    and not self._closing.is_set() and not self._shutdown_requested.is_set())

    def _arrival_tick(self):
        from jarvis3.conversation import desktop_idle
        from jarvis3.session_return import SessionReturn
        self._sync_arrival_option()
        with self._arrival_lock:
            if not self._arrival_enabled or self._arrival_stop.is_set():return
            create=not self._arrival_attempted
            if create:
                self._arrival_attempted=True;self._arrival_source=SessionReturn()
            source=self._arrival_source;epoch=self._arrival_epoch
        if create:source.start()
        unlocked=source.take() if source else False  # consume even while quiet/mic-off/busy
        unlocked=self._camera_arrived() or unlocked   # movement after ten still minutes counts like a return
        with self._arrival_lock:
            if epoch!=self._arrival_epoch or source is not self._arrival_source:return
        idle=desktop_idle();permitted=self._arrival_permitted(source,idle) and self.q.empty()
        if self.arrival.poll(idle,permitted,unlocked=unlocked):self._queue_arrival('unlock' if unlocked else 'idle',(epoch,source))

    def _camera_sync(self):
        """The camera runs only while arrival-by-movement is on."""
        want=bool(self.cfg.get('camera_arrival') and self.cfg.get('arrival_greeting'))
        camera=self._camera
        if want and not self._arrival_stop.is_set():
            if camera is None:
                from jarvis3.camera_presence import CameraPresence
                camera=self._camera=CameraPresence();camera.start()
            return
        if camera is not None:
            self._camera=None;camera.close()

    def _camera_arrived(self):
        camera=self._camera
        return bool(camera and self.cfg.get('camera_arrival')) and camera.take()


    def _arrival_watch(self):
        try:
            while not self._arrival_stop.wait(1):
                if self._closing.is_set():break
                try:self._camera_sync();self._arrival_tick()
                except Exception:_log()
        finally:self._stop_arrival_watch()

    def _dispatch_arrival(self,payload):
        from jarvis3.conversation import desktop_idle
        with self._arrival_lock:
            if payload is not self._arrival_pending or not isinstance(payload,dict):return
            self._arrival_pending=None  # a queue ticket is consumed even if later suppressed
            source=self._arrival_source
            if self._arrival_stop.is_set() or not self.cfg.get('arrival_greeting') or payload['option_epoch']!=self._arrival_epoch:return
            if payload['generation']!=self.conversation.generation or not 0<=time.monotonic()-payload['at']<=15:return
            current=source.generation if source and source.available else None
            if current!=payload['session_generation'] or (payload['source']=='unlock' and current is None):return
            if self.q.empty() and self._arrival_permitted(source,desktop_idle()):
                self._open_conversation('arrival');self.say('What can I do for you, sir?')

    def _warm_ai(self, state, event=None):
        # VAD speech alone is not addressed to Jarvis. Only the current accepted
        # wake can spend resources warming the existing action model.
        if state!='wake' or self.cfg.get('cool_mode') or not self._wake_current(event):return
        warming=getattr(self,'_warming',None)
        if self.engine.ai.loaded or warming is None or not warming.acquire(blocking=False):return
        event=dict(event)
        def warm():
            try:
                if not self.cfg.get('cool_mode') and self._wake_current(event):self.engine.ai.load()
            finally:
                warming.release()
        threading.Thread(target=warm, daemon=True).start()

    def _housekeeping(self):
        """Once a minute: free the AI after 15 idle minutes, and maybe offer a habit (a question, only while everything is quiet)."""
        while not self._closing.wait(OFFER_EVERY_S):
            try:
                self.engine.maybe_unload(3 if self.cfg.get('cool_mode') else 15)
                sp = self.voice.speaker
                # Phase 1 does not initiate proactive conversations.
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
            self.island.level = min(1, max(0, self.voice.level * 25))

    def snapshot(self):
        from .organizer import rows
        snap = super().snapshot()
        snap['theme'] = self.cfg.get('theme', 'light')
        ears = self.voice.ears
        remaining = max(0, ears.armed_until - time.monotonic()) if ears else 0
        if ears and not remaining:
            ears.wake_pending = False
        snap['listen_left'] = round(remaining, 1)
        snap['mic_paused'] = bool(snap['mic'] and ears and time.monotonic() < ears.paused_until)
        snap['hands_free_active'] = bool(remaining and ears.hands_free_active() and self.voice.can_listen())
        snap['awaiting_answer'] = bool(remaining and self.expect_answer)
        capture=ears.capture_feedback() if ears else None
        if capture and not self.conversation.independent(capture['generation']):capture=None
        snap['capture_phase']=capture['phase'] if capture else None
        listening=bool(remaining or (capture and capture['phase']=='recording')) and self.voice.can_listen()
        decoding=bool(capture and capture['phase']=='decoding') and self.voice.can_listen()
        busy=bool(self.voice.speaker and self.voice.speaker.busy)
        if snap['state']!='thinking' and not busy:
            if decoding:snap['state']='thinking'
            elif listening:snap['state']='listening'
        if snap['state']=='listening' and not listening:
            snap['state'] = 'idle'
        snap['personal'] = self.store.fact_infos(limit=8,public=True)
        snap['events'] = [r for r in rows(self.engine.memory, 'commitments') if r['status'] == 'active']
        snap['jobs'] = rows(self.engine.memory, 'jobs')[:8]
        return snap

    def knowledge(self):
        from .routine_editor import pills, version
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
            routine['pills'] = list(pills(steps))
            routine['revision'] = version(steps)
            routine['sentences']=[s['args']['text'] if s['a']=='say' else s['a'].replace('_',' ')+' '+str(s['args'].get('target',s['args'].get('duration',''))) for s in steps]
            state=m._q('SELECT state FROM routine_progress WHERE name=?',routine['name'])
            routine['state']=state[0][0] if state else 'ready'
        return {"paused": m.paused, "words": words, "usage": m.usage_top(6), "habits": habits, "routines": routines, "notes": notes}

    # ----- commands -----
    def _cue(self,kind,token,started):
        from .preferences import quiet
        sp=self.voice.speaker
        if not self.cfg.get('audible_cues',True) or quiet(self.cfg) or not self.voice.talk or not sp:return False
        return sp.cue(kind,started,lambda:self.q.put(('notice','The action status is on screen; its audio cue could not play.')))

    def _wake_valid(self,event):
        if not isinstance(event,dict) or not self.voice.can_listen() or self._closing.is_set() or self._shutdown_requested.is_set():return False
        return (event.get('capture_epoch')==self.voice.ears.capture_epoch
                and self.conversation.independent(event.get('conversation_generation')))

    def _wake_current(self,event):
        if not self._wake_valid(event):return False
        capture=self.voice.ears.capture_feedback()
        return bool(capture and (event.get('capture_epoch'),event.get('sample_onset'),event.get('conversation_generation'))
                    ==(capture['epoch'],capture['onset'],capture['generation']))

    def _wake(self,event):
        if not self._wake_valid(event):return
        self._warm_ai('wake',event)
        if self.voice.speaker:self.voice.speaker.stop()
        self.feedback.cue('wake','wake-'+event['id'])
        self.q.put(('wake_status',event))

    def _early_interrupt(self,event):
        if self._closing.is_set() or self._shutdown_requested.is_set():return
        self.conversation.open('question' if self.engine.pending else 'interrupt')
        if self.voice.speaker:self.voice.speaker.stop()
        self.q.put(('refresh',None))

    def _verified(self,results):
        token=self._command_token
        if token is None:return
        from jarvis3.effects import status
        checks=[status(c,r,self.engine) for c,r in results]
        ok=all(v is True for v in checks)
        self._unverified=any(v is None for v in checks)
        self.feedback.record('verified' if ok else 'requested-unverified' if self._unverified else 'failed',token,steps=len(results))
        self._cue_queued=False
        if self._spoken and not all(r.facts.get('silent') for _,r in results) and (ok or any(not r.ok for _,r in results)):
            self._cue_queued=self.feedback.cue('success' if ok else 'error',token)

    def _voice_tuned(self,values):
        self.cfg.update(values)
        settings.save(self.cfg)
        self._push('jarvis.voicePreferences('+json.dumps(values)+')')

    def interrupt(self, text):
        if re.fullmatch(r'(?:stop|cancel) (?:the |my )?workspace[.!]?',text.strip(),re.I):self.engine.workspace_cancel.set()
        if re.fullmatch(r'(?:stop|cancel) (?:my |the )?(?:plan|task)(?: #?\d+)?[.!]?', text.strip(), re.I):
            self.engine.cancel_goal.set()
        if text and self.voice.speaker:
            self.voice.speaker.stop()

    def _heard(self, heard):
        if not self.voice.accepts(heard):return
        from jarvis3.control import assistant_exit
        if assistant_exit(heard.text):self.voice.consume(heard);self._request_shutdown();return
        self.interrupt(heard.text)
        self.q.put(('heard', heard))

    def _set_mic(self,on):
        if not self.voice.ears:return False
        if not on:return self.voice.pause_listening()
        self.voice.set_listening(True)
        return True

    def _request_shutdown(self):
        if self._shutdown_requested.is_set():return
        self._shutdown_requested.set()
        from jarvis3.control import CANCEL_INFERENCE
        CANCEL_INFERENCE.set()
        self.engine.stop_requested.set();self.engine.cancel_goal.set();self.engine.workspace_cancel.set()
        self.engine.exit_requested=True;self.engine.pending=None;self.conversation.dismiss()
        self.engine.selection.cancel(wait=False)
        if self.voice.speaker:self.voice.speaker.stop()
        if self.voice.ears:self.voice.ears.cancel_output.set();self.voice.ears.stop=True
        self.q.urgent('quit')

    def submit(self, text="", spoken=False, trigger="typed", clip_id=None):
        text = (text or "").strip()
        if not text:
            return
        from jarvis3.conversation import DISMISS
        if DISMISS.fullmatch(text):
            self.conversation.dismiss();self.expect_answer=False;self.engine.pending=None
            self.engine.dialogue.cancel_timer_choices()
            self.engine.selection.cancel()
            if self.voice.ears:
                self.voice.ears.end_hands_free()
                self.voice.ears.armed_until=0;self.voice.ears.wake_pending=False
                self.voice.ears.barge_until=0
            self.state('idle');return
        barge_turn=spoken and self.conversation.reason=='interrupt'
        self.conversation.begin()
        self._spoken = spoken
        self._command_token=self.feedback.begin()
        self._unverified=False
        self._add("You", text, "you")
        self.state("thinking")
        try:
            r = self.engine.handle(text, trigger if spoken else "typed", clip_id)
        except Exception:
            _log()
            self.feedback.record('exception',self._command_token)
            if spoken:self.feedback.cue('error',self._command_token)
            self.say("Something went wrong, sir. It's in the log.", "err")
            return
        if self._shutdown_requested.is_set():return
        calls = "; ".join(f"{c.ability}({', '.join(f'{k}={v}' for k, v in c.args.items())})" for c, _ in r.results)
        self._add("Understood as", f"{calls or r.plan.kind} [{r.plan.source or '-'}; {r.ms['understand']}+{r.ms['act']} ms; wording: {r.how or '-'}]", "sys")
        if r.error:
            self._add("Error", r.error.strip().splitlines()[-1], "err")
        self.expect_answer = bool(r.plan.kind == "ask" or self.engine.pending or any(result.facts.get('awaiting_choice') for _,result in r.results)) and spoken
        if not r.results:self.feedback.record('waiting' if self.expect_answer else 'no-action',self._command_token)
        if self.expect_answer and self.voice.ears:
            # Open BEFORE the question is spoken. Otherwise the UI appears to
            # listen while the first answer is thrown away as "too early".
            self.voice.ears.arm(since=getattr(self, '_heard_end', self.voice.ears.clock))
            self.conversation.open('question')
        elif barge_turn and r.ok and r.results and not self.engine.exit_requested:
            self._open_conversation('interrupt')
        elif spoken and r.ok and r.results and self.cfg.get('conversation_followups') and not self.engine.exit_requested:
            self._open_conversation('reply')
        if r.text:
            minimal=bool(spoken and self.cfg.get('minimal_feedback') and r.ok and r.results and not self.expect_answer and getattr(self,'_cue_queued',False) and all(c.ability in ('open','close','focus','volume','media','window_state','tab_close','tab_focus','note_copy','note_save') for c,_ in r.results))
            if minimal:self._add('Jarvis',r.text,'jarvis');self.state('listening' if self.voice.ears and self.voice.ears.armed_until else 'idle')
            else:self.say(r.text, "jarvis" if r.ok else "err")
        else:
            self.state("idle")
        if self.engine.exit_requested:                        # "shut down": say goodbye, then close completely
            threading.Timer(1.3, self.q.put, ("quit",)).start()

    def save_settings(self, new):
        out = super().save_settings(new)
        self.engine.natural = bool(self.cfg.get("natural_replies", True))
        self.engine.context_options=self.cfg
        self.engine.music.cfg=self.cfg
        self._sync_arrival_option()
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
            if not self.voice.accepts(p):return
            self.voice.consume(p)
            self.last_hearing={'transcribe_ms':p.stt_ms,'delivery_ms':p.wait_ms}
            self._heard_end = p.ended
            self.expect_answer = False
            if not p.text:                                    # the name alone
                self.text = ''
                self.state('listening')
                self._add("Wake word", 'V3 heard the name; the command window is open. Wake cue is separate from completion.', "sys")
            else:
                self.submit(p.text, spoken=True, trigger=p.trigger, clip_id=p.clip_id)
        elif kind == 'wake_status':
            if not self._wake_current(p):return
            capture=self.voice.ears.capture_feedback()
            if not capture:return
            self.set_note('V3 heard the wake word. '+('Recording the full command…' if capture['phase']=='recording' else 'Reading the recorded command…'))
        elif kind == 'arrival':
            self._dispatch_arrival(p)
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
        self._closing.set()
        from jarvis3.control import CANCEL_INFERENCE
        CANCEL_INFERENCE.set();self.engine.stop_requested.set()
        self.engine.selection.cancel()
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
    w = app.window = webview.create_window("Jarvis V4", url, js_api=Api(app), width=1180, height=760, min_size=(720, 520), background_color="#17191d" if app.cfg.get('theme') == 'dark' else "#f3f0e8")
    w.events.closing += app._on_closing
    w.events.shown += app._on_shown
    w.events.minimized += lambda: app._push("window.jarvisMotionPaused=true;dispatchEvent(new Event('jarvismotionchange'))")
    w.events.restored += lambda: app._push("window.jarvisMotionPaused=false;dispatchEvent(new Event('jarvismotionchange'))")
    threading.Thread(target=app.run, daemon=True).start()
    webview.start(debug=debug, private_mode=True)
    os._exit(0)


def main():
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Jarvis4")
    os.makedirs("data", exist_ok=True)
    app=UiApp();app.refresh_apps();launch(app)
