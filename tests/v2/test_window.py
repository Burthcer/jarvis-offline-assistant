"""V2's REAL window and pill on screen, with a pretend PC, a scripted AI, no microphone and no real data (nothing real opens, nothing real is changed).
It types into the page, presses its buttons through the page, and takes pictures of OUR OWN window only.
Run: py -3.12 tests/v2/test_window.py <folder for pictures>"""
import ctypes
import os
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [ROOT, os.path.join(ROOT, "tests", "v2")]
import webview  # noqa: F401  (must load before the folder changes below)

out = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else tempfile.mkdtemp()
os.makedirs(out, exist_ok=True)
from harness import CLOCK  # noqa: E402, F401
from jarvis.store import Store  # noqa: E402

import jarvis2.ui as ui  # noqa: E402
from jarvis2.memory import Memory  # noqa: E402
from jarvis2.osapi import Fake  # noqa: E402

os.chdir(tempfile.mkdtemp())
if '--dark-start' in sys.argv:
    import json
    os.makedirs('data', exist_ok=True)
    with open('data/settings2.json','w',encoding='utf-8') as f:
        json.dump({'theme':'dark'}, f)
ctypes.windll.shcore.SetProcessDpiAwareness(2)
ui.settings.set_autostart = lambda on: None


class Script:
    loaded = True
    out = {"open bluebird": 'open(target="bluebird")', "keep a ten second timer": 'timer_set(duration="ten second")',
           "open notepad and set a timer for 10 minutes": 'open(target="notepad")\ntimer_set(duration="10 minutes")'}

    def complete(self, msgs, temperature=0.0, max_tokens=90):
        return self.out[msgs[-1]["content"].split("]\n", 1)[-1]]

    def load(self):
        pass

    def unload(self):
        pass

    def unload_if_idle(self, m):
        return False


ui.Real, ui.AI, ui.Store, ui.Memory = Fake, (lambda *a, **k: Script()), lambda p: Store(":memory:"), lambda *a: Memory(":memory:", os.path.join(os.getcwd(), "s2.json"))
ui.UiApp._boot = lambda self: self.q.put(("ready", "TEST"))
app = ui.UiApp(gui=True, tray=False)
app.backup_folder=os.path.join(os.getcwd(),'backups')
app.engine.natural = False
quit_called = []
app.quit = lambda: quit_called.append(1)
fails = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails.append(what)


def js(code):
    return app.window.evaluate_js(code)


def wait(cond, secs=6):
    for _ in range(int(secs * 10)):
        if cond():
            return True
        time.sleep(0.1)
    return False


def say(text):
    n = len(app.history)
    app.window.evaluate_js(f"window.pywebview.api.submit({text!r})")
    wait(lambda: any(h[1] == "Jarvis" for h in app.history[n:]) or any(h[1] == "Understood as" for h in app.history[n:]))
    time.sleep(0.4)
    return [h for h in app.history[n:] if h[1] == "Jarvis"]


def grab_window(name):
    app.open_main()
    time.sleep(0.5)
    # Capture the WebView's own rendered surface. PrintWindow returns black
    # for GPU-composited WebView2; this never samples the owner's desktop pixels.
    from System import Action
    from System.IO import MemoryStream
    from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
    wv = app.window.native.webview
    stream, task = MemoryStream(), {}
    def begin():
        task['capture'] = wv.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, stream)
    wv.Invoke(Action(begin))
    try:
        assert task['capture'].Wait(5000), 'own-window capture timed out'
        with open(os.path.join(out, name + '.png'), 'wb') as f:
            f.write(bytes(stream.ToArray()))
    finally:
        stream.Dispose()


def run():
    try:
        check(wait(lambda: app.page_ready), "page opened and connected")
        check(js("document.title === 'Jarvis' && !!document.getElementById('input') && typeof window.jarvis === 'object'"), 'production launch loads actual page and scripts, not an error page')
        check(js("document.documentElement.dataset.theme") == ('dark' if '--dark-start' in sys.argv else 'light'), 'saved theme loads correctly at actual startup')
        if '--dark-start' in sys.argv:
            js("document.getElementById('themeToggle').click()")
            check(wait(lambda: app.cfg.get('theme') == 'light'), 'dark startup can switch to light')
        check(wait(lambda: not app.booting), "starting-up state ends when the ears are ready")
        check(js("!!document.getElementById('themeToggle')"), 'theme switch available on Home')
        js("document.getElementById('themeToggle').click()")
        check(wait(lambda: app.cfg.get('theme') == 'dark' and js("document.documentElement.dataset.theme === 'dark'")), 'Home switches to dark mode')
        check(ui.settings.load().get('theme') == 'dark' and app.voice.listening and app.voice.talk, 'theme persists without disabling hearing or speech')
        check(js("!!document.querySelector('canvas.page-dither') && !!document.querySelector('canvas.page-trail')"), 'actual website dither and pointer-trail canvases loaded')
        if not js("matchMedia('(prefers-reduced-motion:reduce)').matches"):
            before = js("document.querySelector('canvas.page-dither').toDataURL()")
            time.sleep(.3)
            check(before != js("document.querySelector('canvas.page-dither').toDataURL()"), 'dark background actually changes between frames')
            js("(() => {const b=document.getElementById('themeToggle').getBoundingClientRect();dispatchEvent(new PointerEvent('pointermove',{clientX:b.x+b.width/2,clientY:b.y+b.height/2,pointerType:'mouse'}));})()")
            time.sleep(.3)
            check(js("parseFloat(document.getElementById('themeToggle').style.getPropertyValue('--sc')) > 1.04"), 'website spring magnifies buttons near the pointer')
            check(js("Array.from(document.querySelectorAll('.top .tab')).every(b => Math.abs(parseFloat(b.style.getPropertyValue('--tx')) || 0) < .1)"), 'theme button does not push the navigation row')
            js("document.documentElement.dispatchEvent(new Event('mouseleave'))")
            time.sleep(.5)
            js("(() => {const b=document.getElementById('mic').getBoundingClientRect();dispatchEvent(new PointerEvent('pointermove',{clientX:b.x+b.width/2,clientY:b.y+b.height/2,pointerType:'mouse'}));})()")
            time.sleep(.3)
            check(js("parseFloat(document.getElementById('mic').style.getPropertyValue('--sc')) > 1.04"), 'microphone keeps the website spring effect')
            check(js("['#say button','#addRem button'].every(sel=>{const b=document.querySelector(sel);return Math.abs(parseFloat(b.style.getPropertyValue('--tx'))||0)<.1 && (parseFloat(b.style.getPropertyValue('--sc'))||1)<1.001})"), 'hovering microphone leaves Send and Add in other cards completely still')
        grab_window('home-dark')
        js("document.documentElement.dispatchEvent(new Event('mouseleave'));document.getElementById('themeToggle').click()")
        check(wait(lambda: app.cfg.get('theme') == 'light'), 'Home switches back to light')
        if not js("matchMedia('(prefers-reduced-motion:reduce)').matches"):
            before = js("document.querySelector('canvas.page-dither').toDataURL()")
            time.sleep(.3)
            check(before != js("document.querySelector('canvas.page-dither').toDataURL()"), 'light background actually changes between frames')
            js("window.jarvisMotionPaused=true;dispatchEvent(new Event('jarvismotionchange'))")
            time.sleep(.1)
            before=js("document.querySelector('canvas.page-dither').toDataURL()")
            time.sleep(.2)
            check(before == js("document.querySelector('canvas.page-dither').toDataURL()"), 'background pauses when the window is not in use')
            js("window.jarvisMotionPaused=false;dispatchEvent(new Event('jarvismotionchange'))")
        r = say("open youtube")
        check(r and "YouTube" in r[-1][2], f"typed command through V2: {r[-1][2] if r else None}")
        check(js("document.getElementById('log').textContent.includes('Opening YouTube')"), "the answer is on the page")
        say("remember my Gmail is student.name@gmail.com")
        check(wait(lambda: js("document.getElementById('personalCards').textContent.includes('student.name@gmail.com')")), "a saved fact creates a home card")
        check(not any('gmail' in r['text'].lower() for r in app.store.upcoming(datetime.now())), "facts do not become reminders")
        say('remember my Gmail is updated.student@college.test')
        check(wait(lambda: js("document.getElementById('personalCards').textContent.includes('updated.student@college.test') && !document.getElementById('personalCards').textContent.includes('student.name@gmail.com')")), 'updated fact card replaces old value')
        js("document.querySelector('#personalCards .factActions button').click();document.querySelector('#personalCards textarea').value='edited@college.test';document.querySelector('#personalCards form').requestSubmit()")
        check(wait(lambda: js("document.getElementById('personalCards').textContent.includes('edited@college.test') && !document.getElementById('personalCards').textContent.includes('updated.student@college.test')")), 'Home fact can be edited and saved directly')
        js("document.querySelectorAll('#personalCards .factActions button')[1].click()")
        check(wait(lambda: ('clipboard','edited@college.test') in app.engine.os.log), 'Home Copy button uses fake clipboard with just the value')
        from jarvis2.ears import Ears
        ear = Ears(None,None,None,lambda h:None)
        ear.arm(since=10); ear.wake_pending=True
        app.voice.ears=ear
        app.text=''; app.state('idle')
        check(wait(lambda: app.island.mode == 'listening' and js("document.getElementById('stateSub').textContent.includes('seconds')")), 'wake window shows listening pill and countdown')
        frames=app.island.frames
        time.sleep(.25)
        check(app.island.frames > frames, 'listening pill actually animates')
        grab_window('listening-light')
        ear.armed_until=0; ear.wake_pending=False
        app.voice.ears=None; app.state('idle')
        grab_window("home")
        say('track Techfest on 20 November')
        say('12 November at 5 pm')
        js("document.querySelector('[data-page=plans]').click()")
        check(wait(lambda: js("document.getElementById('eventCards').textContent.includes('Techfest')")), 'event creates a Plans card')
        say('plan: open notepad and set a timer for 10 minutes')
        check(wait(lambda: js("document.getElementById('jobCards').textContent.includes('open notepad')")), 'plan preview appears on Plans page')
        say('yes')
        check(wait(lambda: js("document.getElementById('jobCards').textContent.includes('done')")), 'plan runs and progress reaches done')
        check(js("document.documentElement.scrollWidth <= window.innerWidth"), 'Plans page has no horizontal overflow')
        grab_window('plans')
        js("document.querySelector('[data-page=home]').click()")
        say("open bluebird")
        r = say("no I meant chrome")
        check(r and "chrome" in r[-1][2].lower() and app.engine.memory.alias_active("bluebird") is not None, f"a correction teaches a word: {r[-1][2] if r else None}")
        js("document.querySelector('[data-page=knowledge]').click()")
        time.sleep(1.0)
        txt = js("document.getElementById('k_words').textContent")
        check("bluebird" in txt and "Chrome" in txt.title() or "chrome" in txt, f"Knowledge tab lists the learned word: {txt[:60]!r}")
        check("youtube" in js("document.getElementById('k_usage').textContent").lower(), "Knowledge tab shows what is used most")
        js("document.querySelector('#k_notes .factActions button').click();document.querySelector('#k_notes textarea').value='knowledge.edit@college.test';document.querySelector('#k_notes form').requestSubmit()")
        check(wait(lambda: js("document.getElementById('k_notes').textContent.includes('knowledge.edit@college.test')")), 'Knowledge saved facts can be edited directly')
        js("document.querySelector('#k_notes .factActions button').click();document.querySelector('#k_notes input[aria-label=\"Fact alternate names\"]').value='student mail';document.querySelector('#k_notes form').requestSubmit()")
        check(wait(lambda: bool(app.store.notes('student mail')) and app.store.fact_info(app.store.notes('student mail')[0])['aliases']==['student mail']), 'fact alternate names save through the actual editor')
        js("document.getElementById('addFact').click();document.querySelector('#knowledgeFactForm input').value='personal Gmail';document.querySelector('#knowledgeFactForm textarea').value='personal@example.test'")
        grab_window('fact-editor')
        js("document.querySelector('#knowledgeFactForm form').requestSubmit()")
        check(wait(lambda: js("document.getElementById('k_notes').textContent.includes('personal@example.test')")), 'Knowledge Add fact saves a new heading and value')
        js("document.querySelectorAll('#k_notes .factActions button')[3].click();document.querySelector('#k_notes input').value='work email';document.querySelector('#k_notes textarea').value='work@example.test';document.querySelector('#k_notes form').requestSubmit()")
        check(wait(lambda: js("document.getElementById('k_notes').textContent.includes('work email') && !document.getElementById('k_notes').textContent.includes('personal Gmail')")), 'editing changes the heading itself, without leaving an old duplicate')
        check(len(app.store.notes('')) == 2, 'two distinct email facts stay separate')
        js("document.querySelector('[data-page=home]').click();document.getElementById('addHomeFact').click();document.querySelector('#homeFactForm input').value='course';document.querySelector('#homeFactForm textarea').value='CS';document.querySelector('#homeFactForm form').requestSubmit()")
        check(wait(lambda: js("document.getElementById('personalCards').textContent.includes('CS')")), 'Home Add fact saves and shows a new card')
        js("document.getElementById('allFacts').click()")
        check(wait(lambda: js("!document.getElementById('knowledge').hidden && document.getElementById('k_notes').textContent.includes('CS')")), 'All saved facts opens Knowledge with the new information')
        grab_window("knowledge")
        js("document.querySelector('#k_words .tiny-btn').click()")
        time.sleep(0.8)
        check(app.engine.memory.alias_active("bluebird") is None, "deleting a word on the page deletes it for real")
        js("document.getElementById('k_learn').click()")
        time.sleep(0.6)
        check(app.engine.memory.paused, "the Learning switch pauses learning")
        js("document.getElementById('k_learn').click()")
        time.sleep(0.4)
        check(not app.engine.memory.paused, "and resumes it")
        say("save that as test mode")
        say("keep a ten second timer")
        r = say("save that as test mode")
        check(app.engine.memory.routines() == ["test mode"], f"a routine is saved by voice: {app.engine.memory.routines()}")
        js("document.querySelector('[data-page=knowledge]').click()")
        time.sleep(0.8)
        check("test mode" in js("document.getElementById('k_routines').textContent"), "the routine shows on the page")
        js("document.querySelector('#k_wipe button').click()")
        time.sleep(0.3)
        js("document.querySelector('#k_wipe .solid').click()")
        time.sleep(0.8)
        check(app.engine.memory.routines() == [] and app.engine.memory.usage_total("youtube") == 0, "forget everything (asks first) clears routines and counts")
        js("document.querySelector('[data-page=settings]').click()")
        time.sleep(0.8)
        check(js("document.getElementById('s_tts_voice').options.length") >= 1, "Settings tab loads")
        js("document.getElementById('cool_mode').checked=true;document.getElementById('savePreferences').click()")
        check(wait(lambda: app.cfg.get('cool_mode') is True), 'cooler idle preference saves without changing models')
        js("document.getElementById('backupNow').click()")
        check(wait(lambda: js("document.getElementById('backupList').options.length > 0")), 'local backup button creates a selectable backup')
        js("document.getElementById('restoreBackup').click()")
        check(js("!document.getElementById('restoreConfirmation').hidden"), 'restore requires its own confirmation')
        js("document.getElementById('cancelRestore').click()")
        check(js("document.getElementById('restoreConfirmation').hidden"), 'restore can be cancelled without replacing data')
        app.store.add('my disposable restore marker is test only',kind='note',merge=False)
        js("document.getElementById('restoreBackup').click();document.getElementById('confirmRestore').click()")
        check(wait(lambda: js("document.getElementById('backupFeedback').textContent.startsWith('Restored.')")), 'confirmed backup restore completes through the actual page')
        check(not app.store.notes('disposable restore marker') and len(ui.Api(app).backups())>=2, 'restore replaces only test data and saves the pre-restore state')
        js("document.getElementById('performanceCheck').click()")
        check(wait(lambda: js("document.getElementById('performanceResult').textContent.includes('Requests measured')")), 'performance panel displays real timing samples')
        js("document.querySelector('[data-page=knowledge]').click()")
        time.sleep(.4)
        js("document.getElementById('heardName').value='prome';document.getElementById('actualName').value='chrome';document.getElementById('teachName').requestSubmit()")
        check(wait(lambda: app.engine.memory.alias_active('prome') is not None), 'pronunciation dictionary can be taught from the UI')
        js("document.getElementById('routineName').value='ui focus';document.getElementById('routineSteps').value='open notepad';document.getElementById('newRoutine').requestSubmit()")
        check(wait(lambda: app.engine.memory.routine_get('ui focus') is not None), 'routine can be created from the Knowledge form')
        js("document.getElementById('factSearch').value='course';document.getElementById('factSearch').dispatchEvent(new Event('input'))")
        check(wait(lambda: js("document.querySelectorAll('#k_notes .factRow').length === 1 && document.getElementById('k_notes').textContent.includes('CS')")), 'Knowledge search narrows saved facts')
        grab_window('knowledge-expanded')
        js("document.querySelector('[data-page=settings]').click()")
        time.sleep(.3)
        grab_window('settings-expanded')
        js("document.getElementById('showDiagnostics').click()")
        check(wait(lambda: js("!document.getElementById('diagnostics').hidden && document.getElementById('diagnostics').textContent.includes('Heard:') && document.getElementById('diagnostics').textContent.includes('Outcome:')")), 'last-request panel shows actual command outcome')
        # a timer coming due is spoken-and-shown on the pill, and the window is left alone
        row = app.store.add("3-second", datetime.now() - timedelta(seconds=1), "timer")[0]
        app._fire()
        check(len(app.alerts) == 1 and app.alerts[0]["kind"] == "timer", "a due timer raises an alert for the pill")
        app.alert_action("stop")
        recurring=app.store.add('recurring UI test',datetime.now()-timedelta(seconds=1),'reminder',merge=False)[0]
        app.store.repeat(recurring['id'],1)
        app._fire()
        next_due=app.store.get(recurring['id'])['due']
        app.alert_action('snooze')
        check(app.store.get(recurring['id'])['due']==next_due and app.store.get(recurring['id'])['status']=='open', 'snoozing an occurrence preserves the next daily reminder')
        snoozes=app.store.db.execute("SELECT id FROM items WHERE text='recurring UI test' AND id!=?",(recurring['id'],)).fetchall()
        check(len(snoozes)==1 and not app.store.db.execute('SELECT * FROM repeats WHERE item_id=?',(snoozes[0]['id'],)).fetchone(), 'snooze creates a single occurrence without duplicating the recurring schedule')
        r = say("shut down")
        check(wait(lambda: quit_called, 4), "'shut down' asks Jarvis to quit completely")
    except Exception as ex:
        import traceback
        traceback.print_exc()
        fails.append(repr(ex))
    finally:
        print("ALL OK" if not fails else f"FAILED: {fails}")
        os._exit(1 if fails else 0)


threading.Thread(target=run, daemon=True).start()
ui.launch(app)  # Same URL construction/events/startup as the desktop app.
