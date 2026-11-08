"""Real typing into ONE chat-like window this test creates (WinForms in a child PowerShell): contact list + message box.
Pressing Enter in the box records 'SENT: <text>' to a temp file. Every step first checks that this window is in front;
if Windows keeps another window in front, the test stops BEFORE any key is sent (keys would land in the wrong window)."""
import ctypes, os, subprocess, sys, tempfile, time
from pathlib import Path
from types import SimpleNamespace
os.environ['JARVIS_SILENT'] = '1'
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from jarvis3.engine.osapi import Real
from jarvis3.engine.registry import Ask
from jarvis3.engine.abilities import drafts
from jarvis3.screen_index import ScreenIndex, UiaSource

out = Path(tempfile.mkdtemp(prefix='v4-draft-')) / 'sent.txt'
script = r'''
Add-Type -AssemblyName System.Windows.Forms
$f = New-Object Windows.Forms.Form; $f.Text = 'V4 chat fixture'; $f.Width = 640; $f.Height = 420; $f.StartPosition = 'Manual'; $f.Left = 60; $f.Top = 60; $f.TopMost = $true
$l = New-Object Windows.Forms.ListBox; $l.Left = 10; $l.Top = 10; $l.Width = 200; $l.Height = 300; [void]$l.Items.AddRange(@('Rahul Sharma','Mum','College group')); $f.Controls.Add($l)
$t = New-Object Windows.Forms.TextBox; $t.Left = 220; $t.Top = 330; $t.Width = 390; $t.Name = 'message'; $t.AccessibleName = 'Type a message'; $f.Controls.Add($t)
$t.Add_KeyDown({ param($s, $e) if ($e.KeyCode -eq 'Return') { [IO.File]::AppendAllText($env:V4_OUT, 'SENT: ' + $s.Text + "`n"); $e.SuppressKeyPress = $true } })
$f.Add_Shown({ $f.Activate(); [Console]::Out.WriteLine('HWND ' + $f.Handle); [Console]::Out.Flush() })
$k = New-Object Windows.Forms.Timer; $k.Interval = 40000; $k.Add_Tick({ $f.Close() }); $k.Start()
[Windows.Forms.Application]::Run($f)
'''
p = subprocess.Popen(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], stdout=subprocess.PIPE, text=True, env={**os.environ, 'V4_OUT': str(out)})
u = ctypes.windll.user32; u.GetForegroundWindow.restype = ctypes.c_void_p
status = 'FAIL'
try:
    hwnd = int(p.stdout.readline().split()[1]); time.sleep(.6)
    front = lambda: u.GetForegroundWindow() == hwnd
    if not front():
        u.SetForegroundWindow(hwnd); time.sleep(.4)
    if not front():
        status = 'SKIPPED (Windows kept another window in front; no keys were sent)'
        raise SystemExit
    pc = object.__new__(Real); pc.screen = ScreenIndex(UiaSource(window=hwnd))
    ctx = SimpleNamespace(os=pc, app=SimpleNamespace(draft=None, last_typed=0), ai=None, memory=None, catalog={}, kind=lambda a: 'app')
    import uiautomation as auto
    box = lambda: auto.ControlFromHandle(hwnd).EditControl(Name='Type a message').GetValuePattern().Value
    sent = lambda: out.read_text().splitlines() if out.exists() else []
    def step(fn, *a):
        if not front():
            raise RuntimeError('test window lost the front; stopped before sending keys')
        try:
            r = fn(*a); return r.plain
        except Ask as q:
            return q.question
    t0 = time.perf_counter(); said = step(drafts.message_draft, {'contact': 'Rahul', 'what': "I'm out and cannot reply"}, ctx); ms = (time.perf_counter() - t0) * 1000
    print('draft ->', said, f'({ms:.0f} ms incl. {drafts.SETTLE_S*1000:.0f} ms settle)', '| box:', repr(box()), '| sent:', sent())
    ok = box() == "I'm out and cannot reply." and sent() == [] and 'Shall I send' in said
    said = step(drafts.draft_answer, {'said': 'change it to back at 6'}, ctx)
    print('change ->', said, '| box:', repr(box()), '| sent:', sent()); ok &= box() == 'Back at 6.' and sent() == []
    said = step(drafts.draft_answer, {'said': 'cancel'}, ctx)
    print('cancel ->', said, '| box:', repr(box()), '| sent:', sent()); ok &= box() == '' and sent() == []
    step(drafts.message_draft, {'contact': 'mum', 'what': 'on my way'}, ctx)
    said = step(drafts.draft_answer, {'said': 'send it'}, ctx); time.sleep(.3)
    print('send ->', said, '| sent:', sent()); ok &= sent() == ['SENT: On my way.']
    status = 'PASS' if ok else 'FAIL'
except SystemExit:
    pass
finally:
    p.kill(); p.wait()
print('NATIVE DRAFTS', status)
sys.exit(0 if status != 'FAIL' else 1)
