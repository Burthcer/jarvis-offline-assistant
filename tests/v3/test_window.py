"""Actual V3 window and page with fake PC/models/audio and disposable state."""
import os,sys,time,threading,ctypes
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
os.environ['JARVIS_SILENT']='1'
from jarvis3.paths import enter
enter()
from jarvis3.engine import ui,google_connection
from jarvis3.engine.osapi import Fake
from jarvis3.engine.ears import Ears,Job
import numpy as np
class NoAI:
    loaded=False
    def load(self):self.loaded=True
    def complete(self,*a,**k):return 'ASK: Which app, sir?'
    def unload(self):pass
ui.Real=Fake;ui.AI=lambda *a,**k:NoAI()
ui.UiApp._boot=lambda self:self.q.put(('ready','SILENT TEST'))
ui.settings.set_autostart=lambda on:None
google_connection.GoogleConnection=lambda:SimpleNamespace(status=lambda:{'connected':False,'busy':False,'message':'Not connected (test)'})
app=ui.UiApp(gui=True,tray=False)
failures=[]
def check(value,message):
    print(('PASS ' if value else 'FAIL ')+message,flush=True)
    if not value:failures.append(message)
def wait(fn):
    end=time.monotonic()+6
    while time.monotonic()<end:
        if fn():return True
        time.sleep(.05)
    return False
def js(code):return app.window.evaluate_js(code)
def capture(name):
    time.sleep(.5)  # capture settled page/theme animations, not a half-faded frame
    from System import Action
    from System.IO import MemoryStream
    from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
    stream=MemoryStream();task={};wv=app.window.native.webview
    def begin():task['future']=wv.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png,stream)
    wv.Invoke(Action(begin))
    assert task['future'].Wait(5000)
    path=ROOT/'data/v3-dev-checks'/name;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(bytes(stream.ToArray()));stream.Dispose()

def protocol(method,params):
    import json
    from System import Action
    task={};wv=app.window.native.webview
    def begin():task['future']=wv.CoreWebView2.CallDevToolsProtocolMethodAsync(method,json.dumps(params))
    wv.Invoke(Action(begin));assert task['future'].Wait(5000)
def run():
    try:
        check(wait(lambda:app.page_ready),'real page and bridge loaded')
        check(wait(lambda:not app.booting and app.q.empty()),'fake startup finished before motion checks')
        app.text=''
        check(js("document.title==='Jarvis V4' && document.querySelector('.brand').textContent.includes('V4')"),'V4 name appears in the app')
        check(js("!!window.presence && getComputedStyle(document.querySelector('.companionMark')).display!=='none' && getComputedStyle(document.querySelector('.reactorVoice')).display==='none'"),'V4: the reactor circle is driven live, its speaking bars are gone')
        for width in (1180, 960, 720):
            protocol('Emulation.setDeviceMetricsOverride',{'width':width,'height':760,'deviceScaleFactor':1,'mobile':False})
            check(js("""(() => {
                const top=document.querySelector('.top'), nav=top.querySelector('nav'), tools=top.querySelector('.tools');
                const n=nav.getBoundingClientRect(), t=tools.getBoundingClientRect();
                const last=nav.lastElementChild.getBoundingClientRect();
                const fits=last.right <= n.right+1 && tools.lastElementChild.getBoundingClientRect().right <= innerWidth;
                return fits && (innerWidth >= 900 ? Math.abs(n.top-t.top)<8 : n.top>=t.bottom);
            })()"""),f'header fits at {width}px')
        protocol('Emulation.clearDeviceMetricsOverride',{})
        app.state('idle');time.sleep(.15)
        before=js("presence.frames");time.sleep(.3)
        check(js("presence.frames")>before,'the presence is alive at rest (it breathes)')
        for state in ('listening','thinking','speaking'):
            if state=='listening':
                app.voice.ears=Ears(None,None,None,lambda h:None)
                app.voice.ears.armed_until=time.monotonic()+30;app.voice.ears.wake_pending=True;app.voice.ears.level=.032
            else:app.voice.ears=None
            app.state(state);time.sleep(.12)
            if state=='listening':
                check(wait(lambda:js("presence.snapshot().mic>.4")),'his voice swells the presence')
                app.voice.ears.level=0
                check(wait(lambda:js("presence.snapshot().mic<.1")),'it settles as his voice gets quieter')
                check(js("!document.getElementById('wave')"),'no separate waveform beneath it')
            elif state=='thinking':
                check(wait(lambda:js("presence.mode==='thinking'")),'thinking spins the rings fast');a=js("getComputedStyle(document.querySelector('.reactorSegments')).transform");time.sleep(.15);check(js("getComputedStyle(document.querySelector('.reactorSegments')).transform")!=a,'the segment ring is turning')
            else:
                js("jarvis.voice(.9)")
                check(wait(lambda:js("presence.snapshot().voice>.5")),"speaking pulses with Jarvis's own voice level")
                check(js("getComputedStyle(document.querySelector('.reactorVoice')).display==='none' && getComputedStyle(document.querySelector('.reactorGlyph')).opacity>0.5"),'speaking keeps the J: no bars anywhere')
                js("jarvis.voice(0)")
            capture('brand-'+state+'.png')
        js("window.jarvisMotionPaused=true;dispatchEvent(new Event('jarvismotionchange'))")
        time.sleep(.08)
        before=js("presence.frames");time.sleep(.25)
        check(js("presence.frames")==before,'minimised/hidden: the presence stops drawing')
        js("window.jarvisMotionPaused=false;dispatchEvent(new Event('jarvismotionchange'))")
        protocol('Emulation.setEmulatedMedia',{'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
        time.sleep(.15);before=js("presence.frames");time.sleep(.25)
        check(js("presence.frames")==before,'reduced-motion preference: one still frame, nothing moving')
        protocol('Emulation.setEmulatedMedia',{'features':[]})
        app.state('idle')
        # Exercise capture-derived state through the real page, not manual
        # state labels. A prefix paints feedback without authorising a turn.
        ear=Ears(None,None,None,lambda h:None);app.voice.ears=ear;ear.on_wake=app._wake
        generation=app.conversation.generation
        ear._capture_begin(100,generation)
        job=Job(np.zeros(2048,np.int16),100,101);job.voice_a=100;job.kind='wake_probe';job.conversation_generation=generation
        ear._notify_wake(job)
        check(wait(lambda:js("document.getElementById('orb').classList.contains('listening')")),'accepted capture displays listening in actual page')
        check(js("document.getElementById('orb').dataset.mode==='recording'"),'active capture selects the recording animation')
        check(not ear.armed_until and not app.engine.os.log,'prefix feedback grants no action or follow-up permission')
        ear._capture_phase(100,'decoding');app._render()
        check(wait(lambda:js("document.getElementById('orb').classList.contains('thinking')")),'final speech decoding displays thinking in actual page')
        check(js("document.getElementById('orb').dataset.mode==='decoding'"),'decoding selects its own animation')
        ear._capture_finish(job);app._render();ear.shutdown();app.voice.ears=None
        check(wait(lambda:js("document.getElementById('orb').classList.contains('idle')")),'finished capture clears actual-page listening feedback')
        check(js("document.getElementById('note').textContent==='Say “Jarvis”'"),'header tells you when the wake word is needed')
        ear=Ears(None,None,None,lambda h:None);app.voice.ears=ear
        ear.hands_free_s=180;ear.arm(180,since=0);ear.hands_free_until=ear.armed_until;app._render()
        check(wait(lambda:js("document.getElementById('note').textContent.startsWith('Hands-free')")),'header shows the active hands-free window')
        app.voice.pause_listening();app._render()
        check(wait(lambda:js("document.getElementById('note').textContent==='Mic paused'")),'header distinguishes microphone pause')
        ear.shutdown();app.voice.ears=None
        check(not app.store.notes(''),'V2 personal facts were not imported')
        js("window.pywebview.api.submit('open notepad')")
        check(wait(lambda:any(x[:2]==('open','notepad') for x in app.engine.os.log)),'typed command runs through private V3 engine')
        js("document.getElementById('themeToggle').click()")
        check(wait(lambda:app.cfg['theme']=='dark' and js("document.documentElement.dataset.theme==='dark'")),'separate dark theme saves')
        check(js("getComputedStyle(document.documentElement).getPropertyValue('--text').trim()==='#f3f0e8'"),'dark theme has the intended readable text colour')
        capture('home-dark.png')
        js("document.querySelector('[data-page=settings]').click()")
        js("document.querySelector('[data-to=g-self]').click()")
        check(js("[...document.querySelectorAll('#g-self .systemSection')].every(d=>!d.open) && !document.getElementById('v3Status').textContent"),'system and diagnostics start collapsed')
        js("document.querySelector('#diagnosticSection > summary').click();document.querySelector('#refreshV3 > summary').click()")
        check(wait(lambda:js("document.getElementById('v3Status').textContent.includes('Jarvis V4 development')")),'opening listening steps loads the release report')
        check(js("document.getElementById('v3Status').textContent.includes('verified')"),'actual request outcome is visible')
        js("document.querySelector('#showDiagnostics > summary').click()")
        check(wait(lambda:js("document.getElementById('diagnostics').textContent.includes('notepad')")),'opening last request loads the report')
        js("document.querySelector('#diagnosticSection > summary').click();document.querySelector('[data-to=g-hear]').click()")
        js("const prefix=document.getElementById('v3Prefix');prefix.checked=false;prefix.dispatchEvent(new Event('change'))")
        check(wait(lambda:not app.cfg['prefix_wake']),'voice toggle saves without a Save button')
        js("const cues=document.getElementById('v3Cues');cues.checked=false;cues.dispatchEvent(new Event('change'))")
        check(wait(lambda:not app.cfg['prefix_wake'] and not app.cfg['audible_cues']),'V3 options persist independently')
        before=app.cfg['conversation_followups'];js("document.getElementById('v3Followups').click()")
        check(wait(lambda:app.cfg['conversation_followups']!=before),'conversation option saves from actual page')
        js("document.getElementById('v3Interrupts').click()")
        check(wait(lambda:not app.cfg['early_interrupts']),'early interruption can be disabled from the actual page')
        check(not js("document.getElementById('v3Clipboard').checked") and not getattr(app.engine.os,'clipboard_reads',0),'clipboard context starts off without reading')
        js("document.getElementById('v3Clipboard').click()")
        check(wait(lambda:app.cfg['clipboard_context']),'clipboard opt-in saves from the actual page')
        app.engine.os.clipboard_text='my Literal clipboard is contact a@example.com or b@example.com; at the rate remains text.\r\n'+('long context ' * 65)
        clip=app.engine.os.clipboard_text
        js("window.pywebview.api.submit('save a note from my clipboard')")
        check(wait(lambda:any(r['text']==clip for r in app.store.notes(''))),'clipboard capture saves exact literal text through actual bridge')
        captured=next(r for r in app.store.notes('') if r['text']==clip)
        js("document.querySelector('[data-page=knowledge]').click()")
        check(wait(lambda:js("document.querySelectorAll('#k_notes .factRow').length>0")),'captured note appears in Knowledge')
        js("[...[...document.querySelectorAll('#k_notes .factRow')].find(r=>r.textContent.includes('Literal clipboard')).querySelectorAll('button')].find(b=>b.textContent==='Edit').click()")
        check(js("document.querySelector('#k_notes textarea').value")==clip.replace('\r\n','\n'),'literal editor preserves whitespace and full content')
        js("document.querySelector('#k_notes form').requestSubmit()")
        check(wait(lambda:not js("document.querySelector('#k_notes textarea')!==null")),'long captured note can be saved in Knowledge')
        js('window.pywebview.api.copy_note('+str(captured['id'])+')')
        check(wait(lambda:('clipboard',clip) in app.engine.os.log),'Knowledge copy returns complete captured note to fake clipboard')
        js("document.querySelector('[data-page=settings]').click()")
        js("document.getElementById('v3Clipboard').click()")
        check(wait(lambda:not app.cfg['clipboard_context']),'clipboard context can be turned off again')
        app._voice_tuned({'tts_speed':1.3,'tts_volume':.8})
        check(wait(lambda:js("Number(document.getElementById('s_tts_speed').value)===1.3")),'spoken speed synchronises the Settings slider')
        js("document.getElementById('workspaceName').value='study';document.getElementById('workspaceAliases').value='College work';document.getElementById('workspaceApps').value='notepad';document.getElementById('workspaceUrls').value='https://example.com/';document.getElementById('workspaceForm').requestSubmit()")
        check(wait(lambda:js("document.getElementById('workspaceList').textContent.includes('study')")),'workspace form saves without launching apps')
        check(wait(lambda:any('college work' in r.get('aliases',[]) for r in __import__('jarvis3.workspaces',fromlist=['profiles']).profiles(app.engine.memory))),'alternate workspace names save from actual page')
        check(not any(x[0]=='url' for x in app.engine.os.log),'saving workspace has no launch effects')
        js("document.getElementById('musicUrl').value='https://www.youtube.com/watch?v=test&list=RDtest';document.getElementById('musicBrowser').value='chrome';document.getElementById('musicForm').requestSubmit()")
        check(wait(lambda:app.cfg.get('music_url')=='https://www.youtube.com/watch?v=test&list=RDtest' and app.cfg.get('music_browser')=='chrome'),'default music choice saves from actual Settings page')
        import tempfile
        with tempfile.TemporaryDirectory(prefix='v3-own-picker-') as project:
            with patch.object(app.window,'create_file_dialog',return_value=(project,)):
                js("document.getElementById('chooseWorkspaceFolder').click()")
                check(wait(lambda:js("document.getElementById('workspaceFolders').textContent.includes('v3-own-picker-')")),'project folder picker adds chosen path to the actual page')
            js("document.getElementById('workspaceForm').requestSubmit()")
            from jarvis3.workspaces import profiles
            check(wait(lambda:any(project in r.get('folders',[]) for r in profiles(app.engine.memory))),'picked project folder saves with profile')
            check(not any(x[0]=='folder_path' for x in app.engine.os.log),'choosing/saving a folder does not open it')
        check(js("document.querySelectorAll('#settings .settingsGroup:not([hidden])').length===1 && document.querySelector('.jump button[aria-pressed=true]').dataset.to==='g-hear'"),'settings shows one selected group')
        capture('settings.png')
        js("document.querySelector('[data-page=home]').click()")
        check(js("!document.querySelector('.homeKnowledge').open && document.getElementById('sideTimers').parentElement.nextElementSibling.matches('.homeKnowledge')"),'home knowledge starts collapsed below timers')
        js("document.querySelector('.homeKnowledge summary').click();document.getElementById('allFacts').click()")
        check(js("!document.getElementById('knowledge').hidden && !document.querySelector('#knowledgeFactForm form')"),'manage facts opens Knowledge with the editor closed')
        js("document.querySelector('[data-page=knowledge]').click();document.getElementById('addFact').click();document.querySelector('#knowledgeFactForm input').value='university';document.querySelector('#knowledgeFactForm textarea').value='V3 test college';document.querySelector('#knowledgeFactForm form').requestSubmit()")
        check(wait(lambda:bool(app.store.notes('university'))),'fact form saves into V3 database')
        check(wait(lambda:js("!document.getElementById('addFact').hidden && !document.querySelector('#knowledgeFactForm form')")),'saving closes the editor and restores Add fact')
        js("window.pywebview.api.submit('copy my university')")
        check(wait(lambda:('clipboard','V3 test college') in app.engine.os.log),'fact copying uses fake clipboard')
        js("document.getElementById('addLink').click();document.querySelector('#knowledgeFactForm input').value='Dashboard';document.querySelector('#knowledgeFactForm textarea').value='example.com/Dash?view=Work';document.querySelector('#knowledgeFactForm form').requestSubmit()")
        check(wait(lambda:bool(app.store.notes('dashboard'))),'Add link saves a named website')
        app.store.add('my personal website is https://example.org/About', kind='note', merge=False)
        for request, url in [('open the dashboard', 'https://example.com/Dash?view=Work'), ('open my website', 'https://example.org/About')]:
            check(app.engine.is_instant(request), request + ' needs no model')
            js('window.pywebview.api.submit(' + repr(request) + ')')
            check(wait(lambda:('url', 'edge', url) in app.engine.os.log), request + ' opens the exact saved URL on the fake PC')
        capture('knowledge.png')
        js("document.querySelector('[data-page=plans]').click()")
        check(js("!document.getElementById('plans').hidden"),'existing organiser retained')
        from datetime import datetime
        retained = {'a':'open', 'args':{'target':'youtube', 'browser':'chrome'}}
        app.engine.memory.routine_save('fixture', [
            {'a':'say', 'args':{'text':'volume 25'}}, retained,
            {'a':'say', 'args':{'text':'open notepad'}},
        ], datetime.now())
        effects = list(app.engine.os.log)
        js("document.querySelector('[data-page=routines]').click()")
        check(wait(lambda:js("document.querySelectorAll('.routineCard .routineChip').length===3")),'saved routine shows ordered pills')
        js("[...document.querySelectorAll('.routineCard button')].find(b=>b.textContent==='Edit').click()")
        check(js("document.getElementById('routineEditor').open && [...document.querySelectorAll('#routinePills input')].map(i=>i.value).join('|').startsWith('volume 25|open')"),'Edit opens the selected routine in place with its order intact')
        capture('routine-editor.png')
        js("document.querySelector('#routinePills input').value='volume 40';document.getElementById('newRoutine').requestSubmit()")
        check(wait(lambda:app.engine.memory.routine_get('fixture')[0]['args']['text']=='volume 40'),'editing a pill saves the new command')
        check(app.engine.memory.routine_get('fixture')[1:] == [retained, {'a':'say', 'args':{'text':'open notepad'}}],'unchanged steps keep their order and saved browser')
        check(wait(lambda:js("!document.getElementById('routineEditor').open && document.querySelector('.routineChip').textContent==='volume 40'")),'save closes the editor and refreshes the routine card')
        js("document.getElementById('createRoutine').click();document.getElementById('routineName').value='new fixture';document.getElementById('addRoutineApp').click();document.querySelector('#routinePills input').value='Notepad';document.getElementById('addRoutineCommand').click();document.querySelector('#routinePills li:last-child input').value='volume 35';document.getElementById('newRoutine').requestSubmit()")
        check(wait(lambda:app.engine.memory.routine_get('new fixture')==[{'a':'say','args':{'text':'open Notepad'}},{'a':'say','args':{'text':'volume 35'}}]),'new app and command pills save in order')
        check(app.engine.os.log==effects,'editing and saving routines does not run them')
        print('V3 UI ALL PASSED' if not failures else 'V3 UI FAILURES '+repr(failures),flush=True)
    except Exception:
        import traceback;traceback.print_exc();failures.append('exception')
    finally:os._exit(1 if failures else 0)
threading.Thread(target=run,daemon=True).start()
ui.launch(app)
