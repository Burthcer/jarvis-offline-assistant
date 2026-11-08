"""Actual voice control/config chain, with silent unloaded speaker and fake PC."""
import os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-voice-preferences-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.paths import enter
enter()
from jarvis3.engine import ui
from jarvis3.engine.osapi import Fake
from jarvis3.engine.speaker import Speaker
class NoAI:
    loaded=False
    def complete(self,*a,**k):return 'CHAT: I cannot increase my speaking speed, sir.'
    def unload(self):pass
with patch.object(ui,'Real',Fake),patch.object(ui,'AI',lambda *a,**k:NoAI()),patch.object(ui.UiApp,'_boot',lambda self:None),patch.object(ui.settings,'set_autostart',lambda on:None):
    app=ui.UiApp(gui=False,tray=False);sp=Speaker();sp.ready=True
    app.voice.speaker=app.engine.speech=sp
    sp.on_tune=app._voice_tuned if hasattr(app,'_voice_tuned') else lambda values:None
    said=[];app.say=lambda text,*a:said.append(text)
    cues=[];app.feedback.send=lambda kind,*a:(cues.append(kind),True)[1]
    app.submit('speak faster',spoken=True)
    assert not any('verify completion' in s for s in said),'Blanket completion warning on supported voice action'
    assert app.cfg['tts_speed']==sp.v.speed==ui.settings.load()['tts_speed'],'Spoken change was not saved'
    speed=sp.v.speed;app.submit('increase your speed',spoken=True)
    assert sp.v.speed>speed and 'cannot' not in said[-1].lower(),'Natural speed command fell into chat'
    app.submit('increase your speaking speed',spoken=True)
    assert cues and set(cues)=={'success'},cues
    before=sp.v.speed;app.submit('speak slower',spoken=True);app.submit('scratch that',spoken=True)
    assert sp.v.speed==app.cfg['tts_speed']==before,'Voice undo did not restore/save exact previous value'
    app.submit('speak slower',spoken=True);sp.v.set_speed(.7)
    app.submit('undo that',spoken=True);assert sp.v.speed==.7 and 'changed afterwards' in said[-1]
    app.submit('open bluetooth settings',spoken=True)
    assert 'verify completion' not in said[-1],'An unchecked dispatch generated a blanket warning'
    sp.shutdown();app.store.db.close();app.engine.memory.db.close()
print('VOICE PREFERENCES: real setters, saved/reloaded speed, natural wording and no blanket warnings passed')
