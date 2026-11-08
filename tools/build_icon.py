"""Build the code-native Jarvis mark at Windows icon sizes; no downloads."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def cubic(a, b, c, d):
    return [((1-t)**3*a[0]+3*(1-t)**2*t*b[0]+3*(1-t)*t*t*c[0]+t**3*d[0],
             (1-t)**3*a[1]+3*(1-t)**2*t*b[1]+3*(1-t)*t*t*c[1]+t**3*d[1]) for t in (i/40 for i in range(41))]


def draw(size=1024):
    scale = size / 512
    im = Image.new('RGBA', (size, size))
    d = ImageDraw.Draw(im)
    box = tuple(int(x*scale) for x in (24,24,488,488))
    d.rounded_rectangle(box, radius=int(116*scale), fill='#285296')
    p = [(176,160),(324,160),(324,314)]
    p += cubic((324,314),(324,383),(290,420),(230,420))
    p += cubic((230,420),(177,420),(145,389),(141,342))
    p += [(199,332)]
    p += cubic((199,332),(202,356),(211,368),(230,368))
    p += cubic((230,368),(253,368),(264,352),(264,315))
    p += [(264,216),(176,216)]
    d.polygon([(round(x*scale),round(y*scale)) for x,y in p], fill='#fcfaf5')
    star=[(390,97),(402,128),(433,140),(402,152),(390,183),(378,152),(347,140),(378,128)]
    d.polygon([(round(x*scale),round(y*scale)) for x,y in star], fill='#ddeb79')
    return im


if __name__ == '__main__':
    image = draw()
    sizes = [(s,s) for s in (16,20,24,32,40,48,64,96,128,256)]
    image.save(ROOT/'jarvis.ico', sizes=sizes)
    image.save(ROOT/'jarvis-paper.ico', sizes=sizes)
    image.resize((512,512), Image.Resampling.LANCZOS).save(ROOT/'jarvis2/web/mark.png')
    print('Built Jarvis icons at 16–256 px and preview.')
