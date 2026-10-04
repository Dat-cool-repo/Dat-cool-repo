"""Comic-page SVG primitives that mirror dat-dev.com's CSS (src/app/globals.css).

GitHub renders README images through <img>, so every SVG is self-contained:
fonts are subset and inlined as woff2, photos as data URIs, no scripts.
"""
import base64
import io
import math
import os
import random
from xml.sax.saxutils import escape

from fontTools import subset as ftsubset
from fontTools.ttLib import TTFont
from PIL import ImageFont

FONT_DIR = os.environ.get("COMIC_FONT_DIR", os.path.join(os.path.dirname(__file__), "fonts"))

# Site tokens (globals.css :root).
BG = "#0b0614"
FG = "#fdf8ec"
MUTED = "#bdb3d1"
PAPER = "#fff6e0"
INK = "#140c1f"
PAPER_MUTED = "#4a4258"
A1 = "#ff2e88"  # magenta
A2 = "#22e4ff"  # cyan
A3 = "#ffe14d"  # yellow
A4 = "#ff7a1a"  # orange
SHEET = "#fffdf6"
SHEET_UNDER = "#e8dfc6"

# family key -> (css family, file)
FONTS = {
    "display": ("dDisplay", "Bangers-400.ttf", 400),
    "body": ("dBody", "SpaceGrotesk-400.ttf", 400),
    "bodybold": ("dBodyB", "SpaceGrotesk-700.ttf", 700),
    "mono": ("dMono", "SpaceMono-700.ttf", 700),
    "monoreg": ("dMonoR", "SpaceMono-400.ttf", 400),
}
_pil = {}


def pil_font(key, size):
    k = (key, round(size * 4))
    if k not in _pil:
        _pil[k] = ImageFont.truetype(os.path.join(FONT_DIR, FONTS[key][1]), size)
    return _pil[k]


def text_width(s, key, size, ls=0.0):
    return pil_font(key, size).getlength(s) + ls * max(len(s) - 1, 0)


def wrap(s, key, size, max_w, ls=0.0):
    words, lines, cur = s.split(" "), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if cur and text_width(trial, key, size, ls) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def _subset_b64(key, chars):
    path = os.path.join(FONT_DIR, FONTS[key][1])
    font = TTFont(path)
    cmap = font.getBestCmap()
    missing = sorted(c for c in chars if ord(c) not in cmap and not c.isspace())
    if missing:
        raise ValueError(f"{FONTS[key][1]} lacks glyphs: {missing}")
    opts = ftsubset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga"]
    opts.name_IDs = []
    opts.notdef_outline = True
    sub = ftsubset.Subsetter(opts)
    sub.populate(text="".join(sorted(chars)) + " ")
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


class Svg:
    def __init__(self, w, h, label):
        self.w, self.h, self.label = w, h, label
        self.defs, self.body = [], []
        self.chars = {k: set() for k in FONTS}
        self.css = []
        self._ids = 0

    def uid(self, p="i"):
        self._ids += 1
        return f"{p}{self._ids}"

    def add(self, s):
        self.body.append(s)

    def defn(self, s):
        self.defs.append(s)

    # ---- text ----
    def text(self, x, y, s, key="body", size=16, fill=INK, anchor="start", ls=0.0, upper=False, extra=""):
        if upper:
            s = s.upper()
        self.chars[key].update(s)
        fam = FONTS[key][0]
        a = f' text-anchor="{anchor}"' if anchor != "start" else ""
        l = f' letter-spacing="{ls:.2f}"' if ls else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam}" font-size="{size}"{a}{l} fill="{fill}"{extra}>{escape(s)}</text>')

    def misprint(self, x, y, s, size, fill=FG, c1=A2, c2=A1, shadow="#000", ls=0.0, anchor="start", extra=""):
        """.misprint: cyan plate left, magenta plate right, black drop below."""
        o = size * 0.06
        self.text(x, y + size * 0.08, s, "display", size, shadow, anchor, ls, extra=extra)
        self.text(x + o, y, s, "display", size, c2, anchor, ls, extra=extra)
        self.text(x - o, y, s, "display", size, c1, anchor, ls, extra=extra)
        self.text(x, y, s, "display", size, fill, anchor, ls, extra=extra)

    # ---- shapes ----
    def rect(self, x, y, w, h, fill, stroke=None, sw=3, extra=""):
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}"{st}{extra}/>')

    def box(self, x, y, w, h, fill, shadow="#000", off=8, sw=3, extra=""):
        """Ink panel: fill, black border, hard offset shadow."""
        if shadow:
            self.rect(x + off, y + off, w, h, shadow, extra=extra)
        self.rect(x, y, w, h, fill, "#000", sw, extra=extra)

    def fill_dots(self, x, y, w, h, color, step, r, opacity=1.0, extra=""):
        pid = self.uid("dots")
        self.defn(f'<pattern id="{pid}" width="{step}" height="{step}" patternUnits="userSpaceOnUse"><circle cx="{step / 2:.1f}" cy="{step / 2:.1f}" r="{r}" fill="{color}"/></pattern>')
        op = f' opacity="{opacity}"' if opacity != 1 else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="url(#{pid})"{op}{extra}/>')

    def caption(self, x, y, s, rot=-2.0, size=11.5, fill=A3, color=INK, shadow=True):
        """Yellow narration caption box (.caption)."""
        s = s.upper()
        ls = size * 0.14
        tw = text_width(s, "mono", size, ls)
        w, h = tw + size * 1.9, size * 2.3
        cx, cy = x + w / 2, y + h / 2
        self.add(f'<g transform="rotate({rot} {cx:.1f} {cy:.1f})">')
        if shadow:
            self.rect(x + 3, y + 3, w, h, "#000")
        self.rect(x, y, w, h, fill, "#000", 2)
        self.text(x + (w - tw) / 2, y + h / 2 + size * 0.36, s, "mono", size, color, ls=ls)
        self.add("</g>")
        return w, h

    def tag(self, x, y, s, size=11, fill="#fff", sw=2, shadow=None, rot=0.0):
        s = s.upper()
        ls = size * 0.04
        tw = text_width(s, "mono", size, ls)
        w, h = tw + 16, size + 11
        if rot:
            self.add(f'<g transform="rotate({rot} {x + w / 2:.1f} {y + h / 2:.1f})">')
        if shadow:
            self.rect(x + 3, y + 3, w, h, shadow)
        self.rect(x, y, w, h, fill, "#000", sw)
        self.text(x + 8, y + h / 2 + size * 0.36, s, "mono", size, INK, ls=ls)
        if rot:
            self.add("</g>")
        return w, h

    def tags(self, x, y, items, max_w, size=11, gap=8, **kw):
        cx, cy, row_h = x, y, 0
        for t in items:
            w = text_width(t.upper(), "mono", size, size * 0.04) + 16
            if cx > x and cx + w > x + max_w:
                cx, cy = x, cy + row_h + gap
            tw, th = self.tag(cx, cy, t, size, **kw)
            row_h = max(row_h, th)
            cx += tw + gap
        return cy + row_h - y

    def paragraph(self, x, y, s, max_w, key="body", size=15, lh=1.6, fill=INK, ls=0.0):
        lines = wrap(s, key, size, max_w, ls)
        for i, ln in enumerate(lines):
            self.text(x, y + size + i * size * lh, ln, key, size, fill, ls=ls)
        return len(lines) * size * lh

    def speed_lines(self, cx, cy, radius, color="#fff", opacity=0.05, step=7.0, width=1.5, clip=None):
        parts = []
        a = 0.0
        while a < 360:
            a1, a2 = math.radians(a), math.radians(a + width)
            parts.append(f"M{cx:.0f} {cy:.0f}L{cx + radius * math.cos(a1):.0f} {cy + radius * math.sin(a1):.0f}L{cx + radius * math.cos(a2):.0f} {cy + radius * math.sin(a2):.0f}Z")
            a += step
        cp = f' clip-path="url(#{clip})"' if clip else ""
        self.add(f'<path d="{"".join(parts)}" fill="{color}" opacity="{opacity}"{cp}/>')

    def clip_rect(self, x, y, w, h):
        cid = self.uid("clip")
        self.defn(f'<clipPath id="{cid}"><rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"/></clipPath>')
        return cid

    def burst(self, cx, cy, r1, r2, n=14, fill=A3, rot=0.0, cls=""):
        pts = []
        for i in range(n * 2):
            a = math.pi * i / n
            r = r1 if i % 2 == 0 else r2
            pts.append(f"{cx + r * math.cos(a):.1f},{cy + r * math.sin(a):.1f}")
        c = f' class="{cls}"' if cls else ""
        self.add(f'<g transform="rotate({rot} {cx:.1f} {cy:.1f})"{c}><polygon points="{" ".join(pts)}" fill="#000" transform="translate(5 5)"/><polygon points="{" ".join(pts)}" fill="{fill}" stroke="#000" stroke-width="3"/></g>')

    def render(self):
        faces = []
        for key, chars in self.chars.items():
            if not chars:
                continue
            fam, _, weight = FONTS[key]
            faces.append(f'@font-face{{font-family:{fam};font-weight:{weight};src:url(data:font/woff2;base64,{_subset_b64(key, chars)}) format("woff2")}}')
        style = "<style>" + "".join(faces) + "".join(self.css) + "</style>"
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h:.0f}" width="{self.w}" height="{self.h:.0f}" role="img" aria-label="{escape(self.label)}">'
            f"{style}<defs>{''.join(self.defs)}</defs>{''.join(self.body)}</svg>"
        )


def ragged_blob(cx, cy, rx, ry, seed, jag=0.12, n=72):
    """A rough ink blot (the Spot's portal hole): lumpy outline, torn edge."""
    rnd = random.Random(seed)
    waves = [(k, rnd.uniform(0, 2 * math.pi), rnd.uniform(0.02, 0.06)) for k in (2, 3, 5)]
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        k = 1 + sum(amp * math.sin(f * a + ph) for f, ph, amp in waves) + (rnd.random() - 0.5) * jag * 0.5
        pts.append((cx + rx * k * math.cos(a), cy + ry * k * math.sin(a)))
    return "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z"


def wobbly_rect(x, y, w, h, seed, amp=2.2, seg=40):
    """Hand-inked rectangle outline (SketchFrame)."""
    rnd = random.Random(seed)
    def edge(x0, y0, x1, y1):
        n = max(2, int(math.hypot(x1 - x0, y1 - y0) / seg))
        out = []
        for i in range(1, n + 1):
            t = i / n
            out.append(f"L{x0 + (x1 - x0) * t + (rnd.random() - 0.5) * amp:.1f} {y0 + (y1 - y0) * t + (rnd.random() - 0.5) * amp:.1f}")
        return "".join(out)
    return f"M{x:.1f} {y:.1f}" + edge(x, y, x + w, y) + edge(x + w, y, x + w, y + h) + edge(x + w, y + h, x, y + h) + edge(x, y + h, x, y)
