"""Real UI Automation scan + invoke on ONE window this test creates itself (WinForms in a child PowerShell). Never reads or clicks any other window.
The window's buttons write their name to a temp file when pressed; the test checks that exactly the intended button was pressed."""
import os, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from jarvis3.screen_index import ScreenIndex, UiaSource

out = Path(tempfile.mkdtemp(prefix='v4-screen-')) / 'pressed.txt'
script = r'''
Add-Type -AssemblyName System.Windows.Forms
$f = New-Object Windows.Forms.Form; $f.Text = 'V4 owned screen fixture'; $f.Width = 640; $f.Height = 360; $f.StartPosition = 'Manual'; $f.Left = 40; $f.Top = 40; $f.TopMost = $true
$names = 'Download','Download options','Mix - Travis Scott','Mix - Chill Synthwave','Delete account'
$i = 0
foreach ($n in $names) { $b = New-Object Windows.Forms.Button; $b.Text = $n; $b.Width = 260; $b.Height = 40; $b.Left = 20 + 300 * ($i % 2); $b.Top = 20 + 60 * [math]::Floor($i / 2)
  $b.Add_Click({ param($s, $e) [IO.File]::AppendAllText($env:V4_OUT, $s.Text + "`n") }); $f.Controls.Add($b); $i++ }
$swap = New-Object Windows.Forms.Button; $swap.Text = 'Rearrange layout'; $swap.Width = 260; $swap.Height = 40; $swap.Left = 320; $swap.Top = 260
$swap.Add_Click({ $a = $f.Controls | Where-Object { $_.Text -eq 'Download' }; $b = $f.Controls | Where-Object { $_.Text -eq 'Download options' }
  $p = $a.Location; $a.Location = $b.Location; $b.Location = $p }); $f.Controls.Add($swap)
$hub = New-Object Windows.Forms.Button; $hub.Text = 'Gaming Hub'; $hub.Width = 260; $hub.Height = 40; $hub.Left = 20; $hub.Top = 260
$hub.Add_Click({ $g = New-Object Windows.Forms.Button; $g.Text = 'general (text channel)'; $g.Width = 260; $g.Height = 30; $g.Left = 20; $g.Top = 305
  $g.Add_Click({ [IO.File]::AppendAllText($env:V4_OUT, "general`n") }); $f.Controls.Add($g) }); $f.Controls.Add($hub)
$f.Add_Shown({ [Console]::Out.WriteLine('HWND ' + $f.Handle); [Console]::Out.Flush() })
$t = New-Object Windows.Forms.Timer; $t.Interval = 30000; $t.Add_Tick({ $f.Close() }); $t.Start()
[Windows.Forms.Application]::Run($f)
'''
p = subprocess.Popen(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], stdout=subprocess.PIPE, text=True, env={**os.environ, 'V4_OUT': str(out)})
ok = True
try:
    line = p.stdout.readline().strip()
    assert line.startswith('HWND '), line
    hwnd = int(line.split()[1])
    time.sleep(.5)
    s = ScreenIndex(UiaSource(window=hwnd))
    t = time.perf_counter(); els = s.scan(); scan_ms = (time.perf_counter() - t) * 1000
    names = [e.name for e in els]
    print('scanned', len(els), 'controls in', round(scan_ms), 'ms:', names)
    ok &= {'Download', 'Download options', 'Mix - Travis Scott', 'Mix - Chill Synthwave', 'Delete account'} <= set(names)
    t = time.perf_counter(); r = s.target('download button'); click_ms = (time.perf_counter() - t) * 1000
    time.sleep(.4)
    pressed = out.read_text().split() if out.exists() else []
    print('download ->', r, round(click_ms), 'ms, pressed:', pressed)
    ok &= r['status'] == 'clicked' and out.read_text().strip().splitlines() == ['Download']
    r = s.target('mix playlist'); print('mix ->', r['status'], r.get('count'))
    ok &= r['status'] == 'ambiguous' and r['count'] == 2
    t = time.perf_counter(); s.scan(); rescan_ms = (time.perf_counter() - t) * 1000
    t = time.perf_counter(); r = s.pick('the chill synthwave one'); pick_ms = (time.perf_counter() - t) * 1000; time.sleep(.4)
    lines = out.read_text().strip().splitlines(); print('chill ->', r, lines, f'rescan {rescan_ms:.0f} ms, pick (rescan+press) {pick_ms:.0f} ms')
    ok &= r['status'] == 'clicked' and lines == ['Download', 'Mix - Chill Synthwave']
    r = s.target('delete account'); time.sleep(.3)
    ok &= r['status'] == 'risky' and len(out.read_text().strip().splitlines()) == 2
    print('delete ->', r['status'], '(not pressed)')

    # Site memory on the real window: learn, reuse, then the layout changes and the memory heals itself.
    from jarvis3.site_memory import SiteMemory
    mem = SiteMemory(out.parent / 'site_memory.json')
    pressed = lambda: out.read_text().strip().splitlines()
    s = ScreenIndex(UiaSource(window=hwnd), memory=mem)
    r = s.target('download'); time.sleep(.3)
    print('learn ->', r, 'site', s.site); ok &= r.get('learned') is True and pressed()[-1] == 'Download'
    s = ScreenIndex(UiaSource(window=hwnd), memory=SiteMemory(mem.path))
    t = time.perf_counter(); r = s.target('download'); ms = (time.perf_counter() - t) * 1000; time.sleep(.3)
    print('reuse ->', r, f'{ms:.0f} ms'); ok &= r.get('from') == 'memory' and pressed()[-1] == 'Download'
    ScreenIndex(UiaSource(window=hwnd)).target('rearrange layout'); time.sleep(.5)
    n = len(pressed())
    s = ScreenIndex(UiaSource(window=hwnd), memory=SiteMemory(mem.path))
    t = time.perf_counter(); r = s.target('download'); ms = (time.perf_counter() - t) * 1000; time.sleep(.3)
    print('after layout change ->', r, f'{ms:.0f} ms', pressed()[n:])
    ok &= r.get('healed') is True and r.get('from') != 'memory' and pressed()[n:] == ['Download']
    s = ScreenIndex(UiaSource(window=hwnd), memory=SiteMemory(mem.path))
    r = s.target('download'); time.sleep(.3)
    print('healed reuse ->', r); ok &= r.get('from') == 'memory' and pressed()[-1] == 'Download'

    # A multi-step task on the real window: the second button only appears after the first click; then a click that changes nothing stops it.
    from types import SimpleNamespace
    from jarvis3.engine.osapi import Real
    from jarvis3.engine.abilities import tasks
    pc = object.__new__(Real); pc.screen = ScreenIndex(UiaSource(window=hwnd))
    ctx = SimpleNamespace(os=pc, app=SimpleNamespace(task=None, names=None), ai=None)
    t = time.perf_counter(); r = tasks.task_run({'goal': 'click gaming hub, then click the general channel'}, ctx); ms = (time.perf_counter() - t) * 1000
    print('task ->', r.plain, f'{ms:.0f} ms', pressed()[-1:]); ok &= r.ok and pressed()[-1] == 'general'
    n = len(pressed()); r = tasks.task_run({'goal': 'click download, then click the general channel'}, ctx)
    print('task with a dead click ->', r.plain); ok &= not r.ok and 'nothing changed' in r.plain and pressed()[n:] == ['Download']
finally:
    p.kill(); p.wait()
print('NATIVE SCREEN INDEX', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
