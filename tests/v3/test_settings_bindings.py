"""Saving ordinary settings must not leave old music/privacy values active."""
import os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-settings-bindings-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.paths import enter
enter()
from jarvis3.engine import ui
from jarvis3.engine.osapi import Fake
class NoAI:
    loaded=False
    def complete(self,*a,**k):return 'ASK: Which app, sir?'
    def unload(self):pass
with patch.object(ui,'Real',Fake),patch.object(ui,'AI',lambda *a,**k:NoAI()),patch.object(ui.UiApp,'_boot',lambda self:None),patch.object(ui.settings,'set_autostart',lambda on:None),patch.object(ui.Voice,'set_voice',lambda *a:None):
    app=ui.UiApp(gui=False,tray=False);api=ui.Api(app)
    try:
        api.v3_status({'clipboard_context':True})
        assert app.engine.context_options['clipboard_context']
        app.save_settings(dict(app.cfg))
        api.v3_status({'clipboard_context':False})
        app.engine.os.clipboard_text='This must not be read'
        reply=app.engine.handle('save a note from my clipboard')
        assert reply.plan.kind=='ask' and not getattr(app.engine.os,'clipboard_reads',0),'old settings kept clipboard capture enabled'
        url='https://www.youtube.com/watch?v=updated&list=RDupdated'
        api.music_settings({'url':url,'browser':'chrome'})
        assert app.engine.music.cfg.get('music_url')==url and app.engine.music.cfg.get('music_browser')=='chrome','music retained the old settings dictionary'
        app.engine.context_pending={'kind':'clipboard','text':'unsaved clipboard text'}
        api.v3_status({'clipboard_context':False})
        assert app.engine.context_pending is None,'opt-out retained pending clipboard data'
    finally:app.store.db.close();app.engine.memory.db.close()
print('SETTINGS BINDINGS: fresh privacy/music values after normal settings save, opt-out drops pending data passed')
