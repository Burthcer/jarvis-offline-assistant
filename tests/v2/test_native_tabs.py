"""Actual accessibility tab controls in an owned disposable WinForms window."""
import os, sys, subprocess
from pathlib import Path
os.environ['JARVIS_SILENT']='1'
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
if '--child' in sys.argv:
    import clr
    clr.AddReference('System.Windows.Forms')
    from System.Windows.Forms import Form,TabControl,TabPage,DockStyle,Application,Keys
    form=Form(); form.Text='Jarvis owned tab fixture'; form.Width=700; form.Height=400
    tabs=TabControl(); tabs.Dock=DockStyle.Fill
    for i in range(6): tabs.TabPages.Add(TabPage('Duplicate title'))
    form.Controls.Add(tabs); form.KeyPreview=True
    def key(sender,event):
        if event.Control and event.KeyCode==Keys.W:
            tabs.TabPages.Remove(tabs.SelectedTab); event.Handled=True
    form.KeyDown+=key
    form.Shown+=lambda *a:print(int(form.Handle.ToInt64()),flush=True)
    Application.Run(form)
else:
    from jarvis.actions import Real
    from jarvis2.browser_tabs import WindowsTabs,operate
    child=subprocess.Popen([sys.executable,'-u',__file__,'--child'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,cwd=ROOT)
    try:
        hwnd=int(child.stdout.readline().strip())
        backend=Real(); backend._browsers=lambda:[hwnd]
        adapter=WindowsTabs(backend)
        keys=[]
        backend._chord=lambda *a:(keys.append(a),True)[1]
        result=operate(adapter,'close','second and fifth')
        # Classic WinForms exposes identical runtime IDs for these tabs.
        # Refusal must occur before selecting or closing anything.
        assert not result['ok'] and 'unique' in result['message'] and not keys,result
        print('NATIVE AMBIGUOUS TAB IDENTITIES SAFELY REFUSED',flush=True)
    finally:
        child.terminate(); child.wait(timeout=5)
