"""Offscreen native pill frames and icon sizes. No microphone, sound or PC effects."""
import sys,time,statistics
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from PIL import Image,ImageChops,ImageDraw
from jarvis3.brand import glyph,SVG
from jarvis3.legacy.island import Island

root=Path(__file__).resolve().parents[2]
assert (root/'jarvis3/assets/mark.svg').read_text(encoding='utf-8')==SVG
icon=Image.open(root/'jarvis3/assets/jarvis-v3-reactor.ico')
assert {(16,16),(32,32),(48,48),(256,256)}<=icon.ico.sizes()
for size in (16,24,32,48,256):
    image=glyph(size,tile=True);assert image.size==(size,size) and image.getbbox()
pill=Island.__new__(Island)
pill.s=1.5;pill._fonts={};pill.paper=False;pill.ink=(243,240,232,255);pill.accent=(169,198,255);pill.grey=(179,186,196)
pill.expanded=False;pill.dim=False;pill.motion=True;pill.level=.7;pill.text='A short test.';pill._lines=['A short test.']
sheet=Image.new('RGBA',(600,250),'#17191d');draw=ImageDraw.Draw(sheet)
timings=[]
for i,mode in enumerate(('idle','listening','thinking','speaking')):
    pill.mode=mode
    def frame(now):
        image=Image.new('RGBA',(420,60));pill._content(ImageDraw.Draw(image),image,420,60,now);return image
    a=frame(10.2);b=frame(10.7)
    if mode=='listening':
        pill.level=0;pill._strength=0;quiet=frame(10.2);pill.level=1;[frame(10.2) for _ in range(8)];loud=frame(10.2)
        assert ImageChops.difference(loud.crop((0,0,80,60)).convert('RGB'),quiet.crop((0,0,80,60)).convert('RGB')).getbbox(),'a voice must visibly change the reactor'   # V4: brighter core + soft ring, fixed size
        assert not loud.crop((240,0,420,60)).getbbox(),'separate bars are still present'
        pill.level=.7
    else:
        assert ImageChops.difference(a.convert('RGB'),b.convert('RGB')).getbbox(),mode+' does not animate'
    pill.motion=False
    assert frame(10.2).tobytes()==frame(10.7).tobytes(),'reduced motion moved '+mode
    pill.motion=True
    for n in range(15):
        start=time.perf_counter();frame(11+n/15);timings.append((time.perf_counter()-start)*1000)
    sheet.alpha_composite(a,(130,i*60));draw.text((10,i*60+20),mode,fill='white')
out=root/'data/v3-dev-checks/pill-brand.png';out.parent.mkdir(parents=True,exist_ok=True);sheet.save(out)
print('BRAND: all icon sizes, shared vector, native state frames/reduced motion passed; draw median ms',round(statistics.median(timings),2))
