"""A short-lived visible-choice session, explicit preview/yes, exact revalidation."""
import threading,time
from dataclasses import dataclass
from .choices import Choices
from .engine.registry import Ask,Result
import unicodedata
def plain(title):
    """Mathematical bold/italic letters in video titles become ordinary letters, so the voice can read them.
    V4 (the owner, 8 Nov): a long title is not read out at all; 'it' is said instead."""
    t=" ".join(unicodedata.normalize("NFKC",title or "").split())
    return t if len(t.split())<=4 and len(t)<=32 else "it"
class SelectionCancelled(ValueError):pass
@dataclass
class Session:
    provider:object
    choices:object
    overlay:object
    stop:object
    watcher:object=None
    committing:bool=False
    play_requested:bool=False
class Selection:
    def __init__(self,provider_factory,overlay_factory,on_change=lambda:None,on_opened=None):
        self.provider_factory=provider_factory;self.overlay_factory=overlay_factory;self.on_change=on_change
        self.lock=threading.RLock();self.active=None;self.epoch=0
        self.on_opened=on_opened
    def cancel(self,wait=True):
        with self.lock:
            self.epoch+=1;session,self.active=self.active,None
        self._close(session,wait)
    @staticmethod
    def _close(session,wait=True):
        if session:
            session.stop.set()
            try:session.overlay.close(wait=wait)
            finally:
                if wait and session.watcher and session.watcher!=threading.current_thread():session.watcher.join(2)
    def _cancel_session(self,session):
        with self.lock:
            if self.active is not session:return False
            self.epoch+=1;self.active=None
        self._close(session)
        return True
    def _display(self,session,selected=None,epoch=None):
        cancelled=lambda:session.stop.is_set() or (epoch is not None and self.epoch!=epoch)
        if cancelled():raise SelectionCancelled('Selection cancelled, sir.')
        previous=session.overlay.frames;session.overlay.show(session.choices.snapshot,selected)
        end=time.monotonic()+1
        while session.overlay.frames==previous and not session.overlay.error and not cancelled() and time.monotonic()<end:time.sleep(.005)
        if cancelled():raise SelectionCancelled('Selection cancelled, sir.')
        if session.overlay.error or session.overlay.frames==previous:raise ValueError('I could not display the target preview. Nothing was selected, sir.')
    def show(self,group='videos',play=False):
        with self.lock:
            self.epoch+=1;epoch=self.epoch;previous,self.active=self.active,None
        self._close(previous)
        provider=self.provider_factory()
        with self.lock:
            if self.epoch!=epoch:raise SelectionCancelled('Selection cancelled, sir.')
        snapshot=provider.snapshot(group);choices=Choices();choices.snapshot=snapshot
        with self.lock:
            if self.epoch!=epoch:raise SelectionCancelled('Selection cancelled, sir.')
        overlay=self.overlay_factory();session=Session(provider,choices,overlay,threading.Event())
        session.play_requested=play
        try:
            self._display(session,epoch=epoch)
            with self.lock:
                if self.epoch!=epoch:raise SelectionCancelled('Selection cancelled, sir.')
                self.active=session
        except Exception:self._close(session);raise
        session.watcher=threading.Thread(target=self._watch,args=(session,),daemon=True);session.watcher.start()
        return snapshot
    def _watch(self,session):
        while not session.stop.wait(.7):
            if session.committing:continue
            try:
                original=session.choices.snapshot
                if time.monotonic()-original.at>15:raise ValueError('expired')
                fresh=session.provider.snapshot(original.group)
                if session.committing:continue
                if (fresh.page,fresh.items)!=(original.page,original.items):raise ValueError('changed')
            except Exception:
                if self._cancel_session(session):self.on_change()
                return
    def pick(self,selector,confirmed=False,confirmation=None,group=None,play=False,direct=False):
        with self.lock:session=self.active
        if session is None or (group and session.choices.snapshot.group!=group and not (group=='videos' and session.choices.snapshot.group=='results')):
            self.show(group or 'videos',play=play or bool(session and session.play_requested))
            with self.lock:session=self.active
        play=play or session.play_requested
        if time.monotonic()-session.choices.snapshot.at>15:
            self.cancel();raise ValueError('Choices expired. Ask me to number them again, sir.')
        item=session.choices.resolve(selector);snapshot=session.choices.snapshot
        proof=confirmation or {}
        if not direct and (not confirmed or proof.get('choice_token')!=snapshot.token or proof.get('choice_item')!=item.identity):
            self._display(session,item.identity)
            raise Ask('Open '+plain(item.title)+', sir?',pending={'choice_token':snapshot.token,'choice_item':item.identity})
        with self.lock:
            if self.active is not session:raise ValueError('The choices changed. Please number them again, sir.')
            session.committing=True
        try:
            fresh=session.provider.snapshot(snapshot.group)
            def invoke(item):
                with self.lock:
                    if self.active is not session or session.stop.is_set():return False
                return session.provider.invoke(item)
            report=session.choices.commit(fresh,invoke,True,session.provider.verify)
            with self.lock:current=self.active is session and not session.stop.is_set()
            if report['verified'] and self.on_opened and current:
                try:playback=self.on_opened(session.provider,play)
                except Exception:playback=None
                if play:
                    report['playing']=bool(playback and playback.ok)
                    return Result(report['playing'],('Playing '+plain(item.title)+', sir.') if report['playing'] else ('Opened '+plain(item.title)+'. Tap Play, sir.'),report,exact=True)
            if report['verified'] and play:
                report.update(playing=False,cancelled=not current)
                return Result(False,'Opened '+plain(item.title)+'. Playback '+('cancelled' if not current else 'is unavailable')+', sir.',report,exact=True)
            return Result(report['requested'],('Opened ' if report['verified'] else 'Requested ')+plain(item.title)+', sir.' if report['requested'] else 'That link could not be selected, sir.',report,exact=True)
        finally:self._cancel_session(session)
