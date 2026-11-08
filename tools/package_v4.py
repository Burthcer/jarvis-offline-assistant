"""Build the separate V4 runtime and optionally install its desktop shortcut.
The V2 (Jarvis.lnk) and V3 (Jarvis V3.lnk) shortcuts must stay byte-for-byte unchanged."""
import os,sys,shutil,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from jarvis3.brand import glyph,SVG
OUT=(ROOT/'data/runtime-v4').resolve()
assert OUT.is_relative_to((ROOT/'data').resolve()) and OUT.name=='runtime-v4'
OUT.mkdir(parents=True,exist_ok=True)
assets=ROOT/'jarvis3/assets';assets.mkdir(exist_ok=True)
image=glyph(512,tile=True)
(assets/'mark.svg').write_text(SVG,encoding='utf-8')
page=ROOT/'jarvis3/engine/web/app.html'
html=page.read_text(encoding='utf-8')
if '<!-- V3 SPARK -->' in html:
    start,rest=html.split('<!-- V3 SPARK -->',1)
    _,end=rest.split('<!-- /V3 SPARK -->',1)
    html=start+'<!-- V3 SPARK -->'+SVG+'<!-- /V3 SPARK -->'+end
else:
    html=html.replace('<img src="../../assets/mark.svg" alt="" class="companionMark">','<!-- V3 SPARK -->'+SVG+'<!-- /V3 SPARK -->')
page.write_text(html,encoding='utf-8')
icon=assets/'jarvis-v4-reactor.ico';image.save(icon,sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
base=Path(sys.base_prefix)
for name,target in [('pythonw.exe','JarvisV4.exe'),('python3.dll','python3.dll'),(f'python{sys.version_info.major}{sys.version_info.minor}.dll',f'python{sys.version_info.major}{sys.version_info.minor}.dll'),('vcruntime140.dll','vcruntime140.dll'),('vcruntime140_1.dll','vcruntime140_1.dll')]:
    source=base/name;dest=OUT/target
    if not dest.exists() or hashlib.sha256(source.read_bytes()).digest()!=hashlib.sha256(dest.read_bytes()).digest():shutil.copy2(source,dest)
(OUT/'pyvenv.cfg').write_text(f'home = {base}\ninclude-system-site-packages = true\nversion = {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}\n',encoding='utf-8')
if '--install-shortcut' in sys.argv:
    # Values are passed through environment variables, never interpolated as PS code.
    script='''$desktop=[Environment]::GetFolderPath('Desktop')
$keep=@('Jarvis.lnk','Jarvis V3.lnk') | ForEach-Object { $p=Join-Path $desktop $_; if(Test-Path -LiteralPath $p){(Get-FileHash -LiteralPath $p).Hash}else{''} }
$path=Join-Path $desktop 'Jarvis V4.lnk'
$shell=New-Object -ComObject WScript.Shell
$link=$shell.CreateShortcut($path)
if((Test-Path -LiteralPath $path) -and $link.TargetPath -ne $env:JARVIS_V4_EXE){throw 'An unrelated shortcut already has the V4 name.'}
$link.TargetPath=$env:JARVIS_V4_EXE
$link.Arguments='"'+$env:JARVIS_V4_ENTRY+'"'
$link.WorkingDirectory=$env:JARVIS_V4_ROOT
$link.IconLocation=$env:JARVIS_V4_ICON+',0'
$link.Description='Jarvis V4'
$link.Save()
$after=@('Jarvis.lnk','Jarvis V3.lnk') | ForEach-Object { $p=Join-Path $desktop $_; if(Test-Path -LiteralPath $p){(Get-FileHash -LiteralPath $p).Hash}else{''} }
if(($keep -join ',') -ne ($after -join ',')){throw 'Existing V2/V3 shortcut changed unexpectedly.'}
Write-Output 'Jarvis V4 shortcut saved; V2 and V3 shortcuts unchanged.'
'''
    subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',script],check=True,creationflags=subprocess.CREATE_NO_WINDOW,
                   env={**os.environ,'JARVIS_V4_EXE':str(OUT/'JarvisV4.exe'),'JARVIS_V4_ENTRY':str(ROOT/'Jarvis4.pyw'),'JARVIS_V4_ROOT':str(ROOT),'JARVIS_V4_ICON':str(icon)})
print('V4 runtime:',OUT/'JarvisV4.exe')
