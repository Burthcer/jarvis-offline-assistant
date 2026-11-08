"""Shared instrument geometry for the V3 panel, desktop icon and pill."""
import math
from functools import lru_cache

from PIL import Image, ImageColor, ImageDraw

CYAN = '#81eaff'
AMBER = '#ffbd71'
PANEL = '#0a1725'
TRACK = '#29475c'
CORE = ((128, 91), (160, 110), (160, 146), (128, 165), (96, 146), (96, 110))
GLYPH = ((142, 113), (142, 137), (135, 145), (121, 145), (114, 137))
SEGMENTS = ((8, 62), (76, 130), (144, 198), (212, 266), (280, 334))


def point(radius, angle):
    radians = math.radians(angle)
    return 128 + radius * math.cos(radians), 128 + radius * math.sin(radians)


def arc(radius, start, end):
    x1, y1 = point(radius, start)
    x2, y2 = point(radius, end)
    return f'M{x1:.2f} {y1:.2f}A{radius} {radius} 0 {int(end-start>180)} 1 {x2:.2f} {y2:.2f}'


def svg_points(points):
    return ' '.join(f'{x},{y}' for x, y in points)


ticks = ''.join(
    f'<path d="M{x:.2f} {y:.2f}L{a:.2f} {b:.2f}"/>'
    for angle in range(0, 360, 10)
    for x, y in [point(104, angle)]
    for a, b in [point(112 if angle % 30 == 0 else 108, angle)]
)
segments = ''.join(f'<path d="{arc(83, a, b)}"/>' for a, b in SEGMENTS)
bars = ''.join(f'<rect x="{x}" y="116" width="5" height="24" rx="2" style="--bar:{i}"/>'
               for i, x in enumerate((112, 122, 132, 142)))

SVG = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="companionMark" aria-hidden="true">
  <defs><radialGradient id="reactorField"><stop stop-color="#19394e"/><stop offset="1" stop-color="{PANEL}"/></radialGradient></defs>
  <circle cx="128" cy="128" r="122" fill="url(#reactorField)" stroke="{TRACK}" stroke-width="2"/>
  <path d="M128 8v15m0 210v15M8 128h15m210 0h15" stroke="{CYAN}" stroke-width="2" opacity=".55"/>
  <g class="reactorDial" stroke="{CYAN}" stroke-width="2" opacity=".55">{ticks}</g>
  <circle cx="128" cy="128" r="97" fill="none" stroke="{TRACK}"/>
  <g class="reactorSweep" fill="none" stroke-width="4"><path d="{arc(97, 202, 260)}" stroke="{AMBER}"/><path d="{arc(97, 26, 84)}" stroke="{CYAN}"/></g>
  <g class="reactorSegments" fill="none" stroke="{CYAN}" stroke-width="8">{segments}</g>
  <circle cx="128" cy="128" r="65" fill="none" stroke="{TRACK}" stroke-width="2" stroke-dasharray="2 5"/>
  <g class="reactorScan" fill="none" stroke="{CYAN}" stroke-width="2"><path d="{arc(61, 200, 315)}"/><path d="{arc(54, 31, 155)}"/></g>
  <circle class="reactorPulse" cx="128" cy="128" r="50" fill="none" stroke="{CYAN}" stroke-width="2"/>
  <polygon class="reactorCore" points="{svg_points(CORE)}" fill="#102b3e" stroke="{CYAN}" stroke-width="3"/>
  <polyline class="reactorGlyph" points="{svg_points(GLYPH)}" fill="none" stroke="{CYAN}" stroke-width="6" stroke-linecap="square"/>
  <g class="reactorVoice" fill="{CYAN}" opacity="0">{bars}</g>
  <path class="reactorMute" d="M111 145l34-34" stroke="{AMBER}" stroke-width="5" opacity="0"/>
</svg>'''


@lru_cache(maxsize=1024)
def glyph(size=256, state='idle', frame=0, level=0, tile=False):
    """Raster version for the Windows icon and the pill. V4: `frame` is the turn in degrees (the pill turns it continuously, each ring
    at its own speed); `level` (0..1) is his voice when listening or Jarvis's voice when speaking. No bars: the core keeps its J."""
    n = max(256, size * 2)
    scale = n / 256
    image = Image.new('RGBA', (n, n))
    draw = ImageDraw.Draw(image)

    def box(*coords):
        return tuple(round(value * scale) for value in coords)

    def ring(radius, start, end, color, width):
        draw.arc(box(128-radius, 128-radius, 128+radius, 128+radius), start, end,
                 fill=color, width=max(1, round(width * scale)))

    if tile:
        draw.rounded_rectangle(box(5, 5, 251, 251), radius=round(56*scale), fill=PANEL,
                               outline=TRACK, width=round(4*scale))
    else:
        draw.ellipse(box(6, 6, 250, 250), fill=PANEL)
    accent = '#6e8ba1' if state == 'off' else AMBER if state in ('alert', 'timer') else CYAN
    sweep, segments = frame, -frame / 2                      # the outer sweep and the segment ring turn opposite ways
    ring(111, 0, 360, TRACK, 4)
    for start, end in SEGMENTS:
        ring(88, start+segments, end+segments, accent, 11)
    ring(106, 204+sweep, 258+sweep, AMBER if state != 'off' else TRACK, 6)
    if state != 'off':
        ring(106, 26+sweep, 84+sweep, accent, 6)
    if state in ('listening', 'speaking') and level:
        ring(100 + level * 10, 0, 360, accent, 2 + level * 4)   # a voice swells a soft ring, never bars
    core = '#102b3e' if not level else tuple(round(a + (b - a) * (.18 + .25 * level)) for a, b in zip((16, 43, 62), ImageColor.getrgb(accent)))
    draw.polygon([box(x, y) for x, y in CORE], fill=core, outline=accent, width=round((4 + 2 * level)*scale))
    draw.line([box(x, y) for x, y in GLYPH], fill=accent, width=round(8*scale), joint='curve')
    if state == 'off':
        draw.line([box(109, 148), box(147, 108)], fill=AMBER, width=round(6*scale))
    return image.resize((size, size), Image.Resampling.LANCZOS)
