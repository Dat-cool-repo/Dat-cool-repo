"""Builds the profile README's comic pages from the portfolio's own data.

    node tools/export-site-data.cjs ../portfolio > tools/site-data.json
    python tools/build_readme.py ../portfolio

Each section of dat-dev.com becomes an SVG page drawn with the site's tokens,
fonts and panel rules (see comic_svg.py), so the profile reads like the site.
"""
import base64
import io
import json
import math
import os
import random
import sys

from PIL import Image, ImageEnhance

from comic_svg import (A1, A2, A3, A4, BG, FG, INK, MUTED, PAPER, PAPER_MUTED, SHEET, SHEET_UNDER, Svg,
                       ragged_blob, text_width, wobbly_rect, wrap)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ASSETS = os.path.join(REPO, "assets")
PORTFOLIO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "..", "portfolio")
DATA = json.load(open(os.path.join(HERE, "site-data.json"), encoding="utf-8"))

W = 880
M = 34            # scene margin around the comic sheet
PAD = 22          # sheet padding
GUT = 22          # gutter between panels
SITE = "https://dat-dev.com"

# About.tsx content (kept in sync by hand; it lives in a component, not src/data).
ORIGIN = [
    "I'm Dat — a University of Florida student who likes taking ML from a whiteboard idea all the way to production. "
    "I've interned at Viettel AI and FPT Software in Hanoi and at VSP Vision, and now split my time between research and shipping.",
    "I'm most drawn to deep learning systems, hardware-aware optimization, and ML that lands somewhere it matters — like healthcare. "
    "Right now I'm tracing fine-tuned behaviors back to individual training tokens.",
]
SKILL_GROUPS = [
    ("Languages", A3, ["Python", "C/C++", "Rust", "SQL", "R", "Java", "Bash"]),
    ("Machine learning", A2, ["PyTorch", "PyTorch Geometric", "TensorFlow", "Transformers", "scikit-learn", "XGBoost", "Mech interp", "RL"]),
    ("ML infra & data", A1, ["CUDA", "Distributed training", "Snowflake", "Docker", "AWS", "Terraform", "Redis", "PostgreSQL", "MCP"]),
]
AWARDS = [
    ("2026", "ShellHacks", "2nd Place Best Use of AWS + Best Use of Tiger Data (transPEAKtation)"),
    ("2025", "Published at ASABE", "AI-driven plant tracking & canopy segmentation, 0.924 IoU"),
    ("2023", "ACSL — Top 1%", "American Computer Science League, ~8,000 competitors"),
    ("2022", "1 Idea 1 World — Gold", "International Invention & Innovation Competition"),
]
SIDE_QUESTS = [
    ("Quantitative Developer", "AlgoGators Investment Fund", "2026–Now"),
    ("Project Captain, Launchpad", "Dream Team Engineering", "2024–Now"),
    ("IoT & AI Research Assistant", "Hanoi Univ. of Science & Technology", "2023"),
]
# Public repos / pages a project card can link to.
PROJECT_LINKS = {
    "transPEAKtation": "https://yowaymo.us/about",
    "Train of Four": "https://github.com/Dat-cool-repo/Train-of-four",
    "Horus": "https://github.com/Dat-cool-repo/Horus",
}
RESEARCH_LINKS = {
    "AI-driven plant tracking for canopy estimation": "https://doi.org/10.13031/aim.202500347",
}


def save(svg, name):
    LABELS[name] = svg.label
    out = svg.render()
    with open(os.path.join(ASSETS, name), "w", encoding="utf-8") as f:
        f.write(out)
    print(f"{name:34s} {len(out) / 1024:7.1f} KB  {svg.w}x{svg.h:.0f}")


def moved_to_back(svg, start):
    """Move everything drawn since `start` underneath what came before."""
    new = svg.body[start:]
    del svg.body[start:]
    svg.body[0:0] = new


def triangle(svg, x, y, size, fill):
    svg.add(f'<path d="M{x:.1f} {y - size / 2:.1f}L{x + size * 0.8:.1f} {y:.1f}L{x:.1f} {y + size / 2:.1f}Z" fill="{fill}"/>')


def arrow_up_right(svg, x, y, size=28, color="#0b0b0b"):
    k = size / 24
    svg.add(f'<g transform="translate({x:.1f} {y:.1f}) scale({k:.3f})" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M7 7h10v10"/><path d="M7 17 17 7"/></g>')


def wobble_css(svg):
    svg.css.append(
        "@keyframes wob{0%,100%{transform:rotate(-6deg) scale(1)}50%{transform:rotate(-2deg) scale(1.06)}}"
        ".wob{transform-box:fill-box;transform-origin:center;animation:wob 3s ease-in-out infinite}"
        "@media (prefers-reduced-motion:reduce){.wob{animation:none}}"
    )


# ---------------------------------------------------------------- comic page

def sheet_strip(svg, x, y, w, page):
    """Page header strip: Dat. Comics · Vol. 01 · Issue #26 · Page NN."""
    size, ls = 10.5, 2.1
    base = y + 12
    svg.text(x, base, "Dat. Comics", "mono", size, INK, ls=ls, upper=True)
    svg.text(x + w / 2, base, "Vol. 01 · Issue #26", "mono", size, INK, "middle", ls, upper=True)
    svg.text(x + w, base, f"Page {page:02d}", "mono", size, INK, "end", ls, upper=True)
    svg.rect(x, y + 22, w, 3, "#000")
    return 25 + GUT


def sheet_bg(svg, x, y, w, h, tilt=0.0, border=True, shadow=True):
    if tilt:
        cx, cy = x + w / 2, y + h / 2
        rot = 1.4 * min(1.0, 900 / h)
        svg.add(f'<g transform="rotate({-rot if tilt > 0 else rot:.3f} {cx:.1f} {cy:.1f})">')
        svg.rect(x + 10, y + 14, w, h, SHEET_UNDER, "#000", 4)
        svg.add("</g>")
    if shadow:
        svg.rect(x + 12, y + 12, w, h, "#000")
    svg.rect(x, y, w, h, SHEET, "#000" if border else None, 4)
    svg.fill_dots(x + 2, y + 2, w - 4, h - 4, "rgba(0,0,0,0.07)", 6, 1.0)


def title_panel(svg, x, y, w, chapter, title, theme):
    h = 132
    cid = svg.clip_rect(x, y, w, h)
    svg.add(f'<g clip-path="url(#{cid})">')
    if theme == "experience":
        svg.rect(x, y, w, h, "#ee4dff")
        cut = x + w * 0.68
        svg.add(f'<path d="M{cut + 30:.1f} {y}L{x + w} {y}L{x + w} {y + h}L{cut - 30:.1f} {y + h}Z" fill="#b4ff2e"/>')
        svg.add(f'<path d="M{cut + 30:.1f} {y}L{cut + 38:.1f} {y}L{cut - 22:.1f} {y + h}L{cut - 30:.1f} {y + h}Z" fill="#000"/>')
        svg.fill_dots(x, y, w, h, "#000", 10, 2.0)
    elif theme == "projects":
        svg.rect(x, y, w, h, "#101014")
        for fx, fy, r in ((0.88, 0.34, 34), (0.76, 0.76, 18), (0.96, 0.86, 9)):
            cx, cy = x + w * fx, y + h * fy
            svg.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r + 2}" fill="#000" stroke="#f4efe4" stroke-width="3"/>')
        svg.speed_lines(x + w * 0.72, y + h * 0.45, w, "#fff", 0.05)
    elif theme == "about":
        svg.rect(x, y, w, h, "#111")
        p = [(0.64, 0.66, "#e8112d"), (0.66, 0.80, "#1d3fbb"), (0.80, 1.2, "#ffe14d")]
        for a, b, c in p:
            sk = h * 0.18
            svg.add(f'<path d="M{x + w * a + sk:.1f} {y}L{x + w * b + sk:.1f} {y}L{x + w * b - sk:.1f} {y + h}L{x + w * a - sk:.1f} {y + h}Z" fill="{c}"/>')
        svg.fill_dots(x, y, w, h, "#e8112d", 10, 2.0)
    svg.add("</g>")
    svg.rect(x, y, w, h, "none", "#000", 3)
    svg.caption(x + 34, y + 30, chapter, rot=-2)
    if theme == "experience":
        svg.misprint(x + 34, y + 104, title.upper(), 54, "#fff", c1="#b4ff2e", c2="#000", ls=1.5)
    else:
        svg.misprint(x + 34, y + 104, title.upper(), 54, FG, ls=1.5)
    return h


def continued(svg, x_right, y, label):
    size = 11.5
    s = label.upper()
    tw = svg_text_w = text_width(s, "mono", size, size * 0.14) + 14
    w, h = tw + size * 1.9, size * 2.3
    x = x_right - w
    svg.add(f'<g transform="rotate(-1.5 {x + w / 2:.1f} {y + h / 2:.1f})">')
    svg.rect(x + 3, y + 3, w, h, "#000")
    svg.rect(x, y, w, h, A3, "#000", 2)
    svg.text(x + size * 0.95, y + h / 2 + size * 0.36, s, "mono", size, INK, ls=size * 0.14)
    triangle(svg, x + size * 0.95 + svg_text_w - 8, y + h / 2, 8, INK)
    svg.add("</g>")


# ---------------------------------------------------------------- front page

def portrait_data_uri():
    im = Image.open(os.path.join(PORTFOLIO, "public", "portrait-headshot.jpg")).convert("RGB")
    im = ImageEnhance.Color(im).enhance(1.08)
    im = ImageEnhance.Contrast(im).enhance(1.04)
    im = im.resize((472, 590), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def front_page():
    H = 680
    s = Svg(W, H, "Dat Le — I build systems & chase ideas worth testing. UF Computer Science '27, open to ML & AI roles.")
    wobble_css(s)
    # Scene: Earth-26 front page — red photocopy with black halftone.
    s.rect(0, 0, W, H, "#d7132e")
    s.fill_dots(0, 0, W, H, "rgba(0,0,0,0.45)", 10, 1.8)
    s.speed_lines(W * 0.72, H * 0.45, 1200, "#fff", 0.06)
    # Torn newsprint strips + blue zine strip, as in SceneBackground's ZineStrips.
    def strip(x, y, w, h, rot, blue=False):
        s.add(f'<g transform="rotate({rot} {x + w / 2:.0f} {y + h / 2:.0f})">')
        rnd = random.Random(int(x * 7 + y))
        top = [(x + w * t / 10, y + rnd.uniform(0, 7)) for t in range(11)]
        bot = [(x + w * (10 - t) / 10, y + h - rnd.uniform(0, 7)) for t in range(11)]
        pts = " ".join(f"{a:.0f},{b:.0f}" for a, b in top + bot)
        if blue:
            s.add(f'<polygon points="{pts}" fill="#1d3fbb"/>')
            cid = s.uid("bl")
            s.defn(f'<clipPath id="{cid}"><polygon points="{pts}"/></clipPath>')
            s.add(f'<g clip-path="url(#{cid})">')
            s.fill_dots(x, y, w, h, "#06134a", 9, 2.6)
            s.add("</g>")
        else:
            s.add(f'<polygon points="{pts}" fill="#f6f1e4"/>')
            for ly in range(int(y + 18), int(y + h - 12), 11):
                s.rect(x + 18, ly, w - 36, 3, "rgba(0,0,0,0.55)")
        s.add("</g>")
    strip(-30, 92, 420, 80, -6)
    strip(600, 300, 330, 70, 4, blue=True)
    strip(-20, 520, 300, 74, 3)
    # Ransom-letter particles.
    for x, y, ch, bg, rot in ((506, 74, "R", "#1d3fbb", -8), (520, 420, "★", A3, 6), (420, 616, "K", "#fff", -4), (800, 612, "X", A3, 10)):
        s.add(f'<g transform="rotate({rot} {x + 18} {y + 18})">')
        s.rect(x + 4, y + 4, 36, 36, "#000")
        s.rect(x, y, 36, 36, bg, "#000", 3)
        if ch == "★":
            pts = []
            for i in range(10):
                a = -math.pi / 2 + math.pi * i / 5
                r = 12 if i % 2 == 0 else 5
                pts.append(f"{x + 18 + r * math.cos(a):.1f},{y + 19 + r * math.sin(a):.1f}")
            s.add(f'<polygon points="{" ".join(pts)}" fill="#000"/>')
        else:
            s.text(x + 18, y + 29, ch, "display", 26, "#fff" if bg == "#1d3fbb" else "#d7132e", "middle")
        s.add("</g>")

    # Nav bar.
    s.rect(0, 0, W, 58, "rgba(11,6,20,0.95)")
    s.rect(0, 58, W, 3, "#000")
    s.misprint(30, 40, "DAT", 32, FG, ls=1.5)
    s.text(30 + text_width("DAT", "display", 32, 1.5) + 2, 40, ".", "display", 32, A3)
    nx = 210
    for item in ("Experience", "Projects", "Research", "About", "Contact"):
        s.text(nx, 36, item.upper(), "display", 17, FG, ls=2.2)
        nx += text_width(item.upper(), "display", 17, 2.2) + 26
    bx, by, bw, bh = W - 168, 13, 138, 34
    s.add(f'<g transform="rotate(1 {bx + bw / 2} {by + bh / 2})">')
    s.box(bx, by, bw, bh, A3, off=5)
    s.text(bx + bw / 2, by + 24, "GET IN TOUCH", "display", 17, INK, "middle", 1.0)
    s.add("</g>")

    # Left column: caption, headline, intro panel, buttons.
    s.caption(40, 92, "UF Computer Science '27 · Open to ML & AI roles", rot=-1, size=11)
    for i, (line, col) in enumerate((("I BUILD SYSTEMS", FG), ("& CHASE IDEAS", A3), ("WORTH TESTING.", FG))):
        s.misprint(40, 206 + i * 74, line, 78, col, ls=1.5)
    px, py, pw = 44, 392, 450
    intro = ("I'm Dat Le, an ML engineer in training at the University of Florida. I've shipped models over 50M-row "
             "production pipelines, published computer-vision research, and I'm now tracing fine-tuned behavior back to "
             "individual training tokens on Gemma-3 12B.")
    lines = wrap(intro, "body", 15, pw - 44)
    ph = 40 + len(lines) * 15 * 1.62
    s.box(px, py, pw, ph, PAPER, A1, 8)
    for i, ln in enumerate(lines):
        if i == 0 and ln.startswith("I'm Dat Le"):
            s.text(px + 22, py + 35, "I'm ", "body", 15, INK)
            dx = text_width("I'm ", "body", 15)
            s.text(px + 22 + dx, py + 35, "Dat Le", "bodybold", 15, INK)
            dx += text_width("Dat Le", "bodybold", 15)
            s.text(px + 22 + dx, py + 35, ln[len("I'm Dat Le"):], "body", 15, INK)
        else:
            s.text(px + 22, py + 35 + i * 15 * 1.62, ln, "body", 15, INK)
    by = py + ph + 34
    for label, col, bx in (("SEE MY WORK", A3, 44), ("RESEARCH", A1, 222)):
        bw = text_width(label, "display", 20, 1.2) + 44
        s.box(bx, by, bw, 50, col, off=5)
        s.text(bx + bw / 2, by + 33, label, "display", 20, INK, "middle", 1.2)

    # Right column: the portrait panel (ComicPortrait.tsx).
    fx, fy, fw = 566, 150, 260
    photo_w, photo_h = fw - 16, (fw - 16) * 5 / 4
    fh = photo_h + 16 + 22
    s.add(f'<g transform="rotate(2 {fx + fw / 2} {fy + fh / 2})">')
    s.box(fx, fy, fw, fh, PAPER, A2, 8)
    cid = s.clip_rect(fx + 8, fy + 8, photo_w, photo_h)
    s.add(f'<image x="{fx + 8}" y="{fy + 8}" width="{photo_w}" height="{photo_h}" href="{portrait_data_uri()}" preserveAspectRatio="xMidYMid slice" clip-path="url(#{cid})"/>')
    s.fill_dots(fx + 8, fy + 8, photo_w, photo_h, "rgba(0,0,0,0.12)", 5, 1.2)
    s.rect(fx + 8, fy + 8, photo_w, photo_h, "none", "#000", 3)
    s.text(fx + fw - 10, fy + fh - 9, "OUR HERO · EARTH-2026", "mono", 9.5, INK, "end", 2.0)
    s.add("</g>")
    # Speech bubble.
    bx, by, bw, bh = fx - 70, fy - 52, 190, 56
    s.add(f'<g transform="rotate(-3 {bx + bw / 2} {by + bh / 2})">')
    s.add(f'<rect x="{bx + 6}" y="{by + 6}" width="{bw}" height="{bh}" rx="28" fill="{A2}"/>')
    s.add(f'<path d="M{bx + bw - 64} {by + bh - 3}L{bx + bw - 44} {by + bh + 24}L{bx + bw - 30} {by + bh - 3}Z" fill="{PAPER}" stroke="#000" stroke-width="3" stroke-linejoin="round"/>')
    s.add(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="28" fill="{PAPER}" stroke="#000" stroke-width="3"/>')
    s.rect(bx + bw - 62, by + bh - 4, 30, 6, PAPER)
    s.text(bx + bw / 2, by + 37, "HEY! I'M DAT.", "display", 26, INK, "middle", 1.0)
    s.add("</g>")
    # Issue box.
    ix, iy = fx + fw - 74, fy - 50
    s.add(f'<g transform="rotate(6 {ix + 44} {iy + 46})">')
    s.box(ix, iy, 88, 94, PAPER, A1, 5)
    s.text(ix + 44, iy + 22, "CLASS OF", "mono", 10, INK, "middle", 2.0)
    s.text(ix + 44, iy + 62, "'27", "display", 40, INK, "middle")
    s.text(ix + 44, iy + 82, "UF CS", "mono", 9, INK, "middle", 1.8)
    s.add("</g>")
    # Starburst sticker.
    cx, cy = fx - 6, fy + fh + 6
    s.add('<g class="wob">')
    s.burst(cx, cy, 62, 42, 14, A3)
    s.text(cx, cy - 4, "OPEN TO", "display", 22, INK, "middle")
    s.text(cx, cy + 20, "WORK!", "display", 22, INK, "middle")
    s.add("</g>")
    save(s, "front-page.svg")


# ---------------------------------------------------------------- experience

def exp_box(s, x, y, w, job, i):
    """Experience.tsx exp-box: ink title strip, role, stats, highlights, tags."""
    start = len(s.body)
    pad = 26
    cy = y
    # Title strip.
    strip_h = 54
    s.rect(x, cy, w, strip_h, INK)
    s.text(x + pad, cy + 37, job["company"].upper(), "display", 27, A3, ls=2.0)
    cw_, ch_ = 0, 0
    date = job["dates"].upper()
    dw = text_width(date, "mono", 10.5, 10.5 * 0.14) + 10.5 * 1.9
    s.caption(x + w - pad - dw, cy + 14, job["dates"], rot=1, size=10.5)
    s.rect(x, cy + strip_h, w, 3, "#000")
    cy += strip_h + 3 + pad
    inner = w - 2 * pad
    # Role + location.
    for ln in wrap(job["role"].upper(), "display", 34, inner, 1.0):
        s.text(x + pad, cy + 30, ln, "display", 34, INK, ls=1.0)
        cy += 36
    s.text(x + pad, cy + 14, job["location"].upper(), "mono", 11, PAPER_MUTED, ls=1.2)
    cy += 30
    # Stat boxes.
    if job["stats"]:
        gap = 14
        sw = (inner - 2 * gap) / 3
        sh = 0
        layouts = []
        for st in job["stats"]:
            lab = wrap(st["label"].upper(), "mono", 10, sw - 26, 0.5)
            layouts.append(lab)
            sh = max(sh, 50 + len(lab) * 13)
        for k, (st, lab) in enumerate(zip(job["stats"], layouts)):
            bx = x + pad + k * (sw + gap)
            s.box(bx, cy, sw, sh, (A3, A2, A4)[k % 3], off=4)
            s.text(bx + 13, cy + 40, st["value"], "display", 36, INK)
            for li, ln in enumerate(lab):
                s.text(bx + 13, cy + 58 + li * 13, ln, "mono", 10, INK, ls=0.5)
        cy += sh + 24
    # Highlights.
    for h in job["highlights"]:
        lines = wrap(h, "body", 14.5, inner - 24)
        s.add(f'<circle cx="{x + pad + 6}" cy="{cy + 10}" r="3.2" fill="{A1}"/>')
        for li, ln in enumerate(lines):
            s.text(x + pad + 22, cy + 15 + li * 23.5, ln, "body", 14.5, INK)
        cy += len(lines) * 23.5 + 10
    # Publication.
    pub = job.get("publication")
    if pub:
        cy += 12
        bx, bw = x + pad, inner - 10
        tl = wrap(pub["title"].upper(), "display", 25, bw - 90, 0.8)
        sl = wrap(pub["summary"], "body", 14, bw - 44)
        bh = 24 + 16 + 12 + len(tl) * 28 + 26 + len(sl) * 22 + 24
        s.box(bx, cy, bw, bh, A3, off=5)
        s.text(bx + 22, cy + 30, pub["venue"].upper(), "mono", 11, INK, ls=2.2)
        ty = cy + 52
        for ln in tl:
            s.text(bx + 22, ty + 22, ln, "display", 25, INK, ls=0.8)
            ty += 28
        s.text(bx + 22, ty + 20, pub["authors"], "mono", 11.5, INK)
        ty += 34
        for ln in sl:
            s.text(bx + 22, ty + 14, ln, "body", 14, INK)
            ty += 22
        s.burst(bx + bw - 14, cy - 8, 42, 30, 12, A1, rot=12)
        s.text(bx + bw - 14, cy - 10, "PUB-", "display", 15, INK, "middle")
        s.text(bx + bw - 14, cy + 6, "LISHED!", "display", 15, INK, "middle")
        cy += bh + 16
    # Tags.
    cy += 10
    cy += s.tags(x + pad, cy, job["tags"], inner, size=10.5) + pad
    h = cy - y
    # Panel body + shadow go underneath.
    mark = len(s.body)
    shadow = A2 if i % 2 else A1
    s.rect(x + 8, y + 8, w, h, shadow)
    s.rect(x, y, w, h, PAPER)
    # .halftone-fade: pink dots fading from the top-left corner.
    mid = s.uid("fade")
    gid = s.uid("g")
    s.defn(f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff"/><stop offset="0.65" stop-color="#fff" stop-opacity="0"/></linearGradient>'
           f'<mask id="{mid}"><rect x="{x}" y="{y + strip_h}" width="{w}" height="{h - strip_h}" fill="url(#{gid})"/></mask>')
    s.add(f'<g mask="url(#{mid})">')
    s.fill_dots(x, y + strip_h, w, h - strip_h, "rgba(255,46,136,0.5)", 9, 1.5)
    s.add("</g>")
    new = s.body[mark:]
    del s.body[mark:]
    s.body[start:start] = new
    s.rect(x, y, w, h, "none", "#000", 3)
    return h


def experience_page():
    s = Svg(W, 100, "")
    sx, sw = M, W - 2 * M
    top = 44
    x0, cw = sx + PAD, sw - 2 * PAD
    y = top + PAD
    body_start = len(s.body)
    y += sheet_strip(s, x0, y, cw, 2)
    y += title_panel(s, x0, y, cw, "Chapter 01 · Experience", "Where I've shipped", "experience") + GUT
    for i, job in enumerate(DATA["EXPERIENCE"]):
        y += exp_box(s, x0, y, cw - 8, job, i) + GUT + 8
    sheet_h = y - top + PAD - GUT
    H = top + sheet_h + 64
    s.h = H
    content = s.body[body_start:]
    del s.body[body_start:]
    # Scene: the Impact Zone — magenta, lime wedge, black halftone, speed lines.
    s.rect(0, 0, W, H, "#ee4dff")
    # Lime wedge on the right (the site's 118deg cut), seen in the right margin.
    s.add(f'<path d="M{W * 0.70:.0f} 0L{W} 0L{W} {H}L{W * 0.56:.0f} {H}Z" fill="#b4ff2e"/>')
    s.add(f'<path d="M{W * 0.66:.0f} 0L{W * 0.69:.0f} 0L{W * 0.55:.0f} {H}L{W * 0.52:.0f} {H}Z" fill="#b4ff2e"/>')
    s.fill_dots(0, 0, W, H, "#000", 13, 2.6)
    s.speed_lines(W * 0.5, 160, 1400, "#000", 0.28, step=11, width=1.3, clip=s.clip_rect(0, 0, W, 1300))
    sheet_bg(s, sx, top, sw, sheet_h, tilt=-0.4)
    s.body.extend(content)
    continued(s, sx + sw - 24, top + sheet_h - 14, "Continued on page 03")
    roles = "; ".join(f'{j["role"]} at {j["company"]} ({j["dates"]})' for j in DATA["EXPERIENCE"])
    s.label = f"Page 02, Chapter 01: Where I've shipped. {roles}."
    save(s, "page-02-experience.svg")


# ---------------------------------------------------------------- projects

def void_scene(s, H, seed):
    """The Ink Void: near-black stage, faint chalk dots and hatching, portal holes."""
    gid = s.uid("void")
    s.defn(f'<radialGradient id="{gid}" cx="0.5" cy="0.5" r="0.75"><stop offset="0" stop-color="#17171c"/><stop offset="0.75" stop-color="#050506"/></radialGradient>')
    s.rect(0, 0, W, H, f"url(#{gid})")
    s.fill_dots(0, 0, W, H, "rgba(244,239,228,0.08)", 9, 1.2)
    rnd = random.Random(seed)
    for _ in range(3):
        side = rnd.choice((rnd.uniform(-10, M - 8), rnd.uniform(W - M + 8, W + 10)))
        y = rnd.uniform(10, H - 10)
        r = rnd.uniform(10, 26)
        s.add(f'<path d="{ragged_blob(side, y, r, r * 0.86, rnd.randint(0, 999), 0.14)}" fill="#0b0b0b" stroke="#f4efe4" stroke-width="2.5"/>')


def sheet_slice(s, H, top_border=False, bottom_border=False):
    sx, sw = M, W - 2 * M
    y0 = 24 if top_border else -6
    y1 = H - 40 if bottom_border else H + 6
    if bottom_border:
        s.rect(sx + 12, y0 + 12, sw, y1 - y0, "#000")
    s.rect(sx, y0, sw, y1 - y0, SHEET, "#000", 4)
    s.fill_dots(sx + 2, y0 + 2, sw - 4, y1 - y0 - 4, "rgba(0,0,0,0.07)", 6, 1.0)
    return sx, y0, sw, y1


def projects_header(page_title, chapter, name, label, page=None, caption_only=False):
    s = Svg(W, 100, label)
    sx, sw = M, W - 2 * M
    x0, cw = sx + PAD, sw - 2 * PAD
    content_start = len(s.body)
    y = (24 if page else 0) + PAD
    if page:
        y += sheet_strip(s, x0, y, cw, page)
    y += title_panel(s, x0, y, cw, chapter, page_title, "projects") + 8
    H = y
    s.h = H
    content = s.body[content_start:]
    del s.body[content_start:]
    void_scene(s, H, len(name))
    sheet_slice(s, H, top_border=bool(page))
    s.body.extend(content)
    save(s, name)


def portal(s, x, y, w, h, glyph, caption, seed):
    """SpotPortal: an ink hole torn in the sketchbook, with the issue number."""
    cid = s.clip_rect(x, y, w, h)
    s.add(f'<g clip-path="url(#{cid})">')
    cx, cy = x + w / 2, y + h / 2
    r = min(w, h) * 0.44
    # Pink accent swoops (ink-bleed) and black construction arcs.
    s.add(f'<path d="M{x - 10:.0f} {y + h * 0.22:.0f}Q{cx:.0f} {y - h * 0.05:.0f} {x + w + 10:.0f} {y + h * 0.2:.0f}" fill="none" stroke="{A1}" stroke-width="16" stroke-linecap="round" opacity="0.35"/>')
    s.add(f'<path d="M{x - 10:.0f} {y + h * 0.22:.0f}Q{cx:.0f} {y - h * 0.05:.0f} {x + w + 10:.0f} {y + h * 0.2:.0f}" fill="none" stroke="{A1}" stroke-width="9" stroke-linecap="round"/>')
    s.add(f'<path d="M{x - 10:.0f} {y + h * 0.86:.0f}Q{cx:.0f} {y + h * 1.04:.0f} {x + w + 10:.0f} {y + h * 0.84:.0f}" fill="none" stroke="{A1}" stroke-width="9" stroke-linecap="round"/>')
    for k, rr in enumerate((1.18, 1.32)):
        s.add(f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{r * rr * 1.25:.1f}" ry="{r * rr * 0.92:.1f}" fill="none" stroke="#000" stroke-width="{3.2 - k}" transform="rotate({-8 + 14 * k} {cx:.1f} {cy:.1f})"/>')
    s.add(f'<line x1="{x + w * 0.42:.0f}" y1="{y}" x2="{x + w * 0.42:.0f}" y2="{y + h}" stroke="#5fa8ff" stroke-width="1.3" opacity="0.7"/>')
    s.add(f'<line x1="{x}" y1="{y + h * 0.13:.0f}" x2="{x + w}" y2="{y + h * 0.13:.0f}" stroke="#5fa8ff" stroke-width="1.3" opacity="0.7"/>')
    s.add(f'<path d="{ragged_blob(cx, cy, r * 1.05, r * 0.98, seed, 0.1)}" fill="#000"/>')
    s.add("</g>")
    gx, gy = cx, cy + 30
    s.add(f'<g transform="rotate(-6 {gx:.1f} {gy:.1f})">')
    s.text(gx + 4, gy + 4, glyph, "display", 92, A1, "middle")
    s.text(gx, gy, glyph, "display", 92, "#f4efe4", "middle")
    s.add("</g>")
    s.caption(x + 14, y + 14, caption, rot=-2, size=11, fill=INK if False else A3)


def project_card(name, title, blurb, tags, year, idx, caption, glyph, href=None, venue=None, last=False, label=""):
    s = Svg(W, 100, label)
    sx, sw = M, W - 2 * M
    x0, cw = sx + PAD + 18, sw - 2 * PAD - 36
    content_start = len(s.body)
    y = 30
    flip = idx % 2 == 1
    pw = cw * 2 / 5
    tw = cw - pw
    tx = x0 if flip else x0 + pw
    px = x0 + tw if flip else x0
    pad = 28
    inner = tw - 2 * pad
    # Story cell content.
    cy = y + pad
    if year:
        yw = text_width(year.upper(), "mono", 10, 2.0) + 16
        s.rect(tx + pad, cy, yw, 22, INK, "#000", 2)
        s.text(tx + pad + 8, cy + 15, year.upper(), "mono", 10, PAPER, ls=2.0)
    if href:
        arrow_up_right(s, tx + tw - pad - 28, cy - 2)
    cy += 36
    for ln in wrap(title.upper(), "display", 44, inner, 1.0):
        s.text(tx + pad, cy + 38, ln, "display", 44, INK, ls=1.0)
        cy += 44
    if venue:
        cy += 8
        vw = text_width(venue.upper(), "mono", 11.5, 0.6) + 12
        lines = wrap(venue.upper(), "mono", 11.5, inner - 12, 0.6)
        for ln in lines:
            lw = text_width(ln, "mono", 11.5, 0.6) + 12
            s.rect(tx + pad, cy, lw, 20, INK)
            s.text(tx + pad + 6, cy + 14.5, ln, "mono", 11.5, A1, ls=0.6)
            cy += 22
    cy += 14
    for ln in wrap(blurb, "body", 14.5, inner):
        s.text(tx + pad, cy + 15, ln, "body", 14.5, INK)
        cy += 23.5
    if tags:
        cy += 18
        cy += s.tags(tx + pad, cy, tags, inner, size=10.5)
    cy += pad
    ch = max(cy - y, 300)
    story = s.body[content_start:]
    del s.body[content_start:]
    H = y + ch + 30 + (70 if last else 0)
    s.h = H
    void_scene(s, H, idx * 31 + 7)
    sheet_slice(s, H, bottom_border=last)
    # SketchFrame: blue pencil construction lines, then the card, then ink outline.
    for (ax, ay, bx, by) in ((x0 - 22, y + 6, x0 + cw + 24, y - 2), (x0 - 18, y + ch + 3, x0 + cw + 22, y + ch - 4),
                             (x0 + 4, y - 18, x0 - 3, y + ch + 22), (x0 + cw - 2, y - 20, x0 + cw + 5, y + ch + 18)):
        s.add(f'<line x1="{ax:.0f}" y1="{ay:.0f}" x2="{bx:.0f}" y2="{by:.0f}" stroke="#5fa8ff" stroke-width="1.2" opacity="0.8"/>')
    s.rect(x0 + 9, y + 9, cw, ch, "#050506")
    gid = s.uid("grid")
    s.defn(f'<pattern id="{gid}" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="rgba(95,168,255,0.13)" stroke-width="1"/></pattern>')
    s.rect(x0, y, cw, ch, "#fbf8f0")
    s.rect(x0, y, cw, ch, f"url(#{gid})")
    portal(s, px, y, pw, ch, glyph, caption, idx * 13 + 5)
    # Black spots on the story cell's edges (clipped by the card).
    cid = s.clip_rect(tx, y, tw, ch)
    s.add(f'<g clip-path="url(#{cid})">')
    spots = [(1.0, 1.0, 120), (0.0 if not flip else 1.0, 0.64, 38), (0.58, 0.0, 30), (0.84, 0.0, 16)] if idx % 2 == 0 else \
            [(0.0, 1.0, 110), (1.0, 0.4, 44), (0.4, 0.0, 26), (0.7, 1.0, 18)]
    for fx, fy, sz in spots:
        bx, by = tx + tw * fx, y + ch * fy
        s.add(f'<path d="{ragged_blob(bx, by, sz / 2, sz * 0.43, int(fx * 100 + fy * 10 + sz), 0.1)}" fill="#050506"/>')
    s.add("</g>")
    s.body.extend(story)
    s.add(f'<path d="{wobbly_rect(x0, y, cw, ch, idx + 3, 2.4)}" fill="none" stroke="#000" stroke-width="3.2" stroke-linejoin="round"/>')
    s.add(f'<path d="{wobbly_rect(x0 + 1.5, y - 1, cw - 2, ch + 1, idx + 11, 3.2)}" fill="none" stroke="#000" stroke-width="1.4" opacity="0.8"/>')
    if last:
        continued(s, M + (W - 2 * M) - 24, H - 40 - 14, "Continued on page 04")
    save(s, name)


# ---------------------------------------------------------------- about

def punk_panel(s, x, y, w, h, fill, shadow):
    """punk-box: tape strips on top, hand-drawn red/cyan double frame."""
    s.box(x, y, w, h, fill, shadow, 8)
    for k, (ox, rot) in enumerate(((18, -4), (w - 110, 3))):
        tx, ty = x + ox, y - 14
        pts = "0,3 7,0 18,3 31,0 46,2 61,0 76,3 92,1 89,25 74,28 57,25 40,28 24,26 9,28 2,24"
        s.add(f'<g transform="translate({tx:.0f} {ty:.0f}) rotate({rot} 46 14)"><polygon points="{pts}" fill="rgba(255,225,77,0.88)" stroke="#000" stroke-width="2"/></g>')
    s.add(f'<path d="{wobbly_rect(x - 7, y - 6, w + 13, h + 12, int(x + y), 3.5, 60)}" fill="none" stroke="#e8112d" stroke-width="2.2"/>')
    s.add(f'<path d="{wobbly_rect(x - 3, y - 9, w + 8, h + 15, int(x * 3 + y), 3.5, 60)}" fill="none" stroke="{A2}" stroke-width="1.8" opacity="0.9"/>')


def about_page():
    s = Svg(W, 100, "")
    sx, sw = M, W - 2 * M
    top = 44
    x0, cw = sx + PAD, sw - 2 * PAD
    content_start = len(s.body)
    y = top + PAD
    y += sheet_strip(s, x0, y, cw, 4)
    y += title_panel(s, x0, y, cw, "Chapter 03 · About", "A little about me", "about") + GUT + 18
    c1w = (cw - GUT - 8) * 1.4 / 2.4
    c2w = cw - GUT - 8 - c1w
    c2x = x0 + c1w + GUT
    # --- measure row 1
    o_lines = [wrap(p, "body", 15, c1w - 44 - 52) for p in ORIGIN]
    bubble_h = 30 + sum(len(l) for l in o_lines) * 24.5 + 14 * (len(o_lines) - 1) + 20
    origin_h = 28 + 30 + 20 + bubble_h + 52
    chip_rows = []
    py = 28 + 34 + 16
    for label, col, skills in SKILL_GROUPS:
        py += 18
        cx, rows = 0, 1
        for sk in skills:
            wv = text_width(sk.upper(), "mono", 10.5, 0.4) + 16
            if cx and cx + wv > c2w - 48:
                cx, rows = 0, rows + 1
            cx += wv + 9
        py += rows * 32 + 16
    power_h = py + 14
    r1 = max(origin_h, power_h)
    # Origin story.
    punk_panel(s, x0, y, c1w, r1, PAPER, A2)
    cid = s.clip_rect(x0, y, c1w, r1)
    s.add(f'<g clip-path="url(#{cid})">')
    s.fill_dots(x0, y, c1w, r1, "rgba(34,228,255,0.35)", 10, 1.3)
    s.add("</g>")
    s.rect(x0, y, c1w, r1, "none", "#000", 3)
    s.caption(x0 + 26, y + 28, "Origin story", rot=-1, size=11)
    bx, by, bw = x0 + 26, y + 28 + 30 + 20, c1w - 52
    s.add(f'<rect x="{bx + 6}" y="{by + 6}" width="{bw}" height="{bubble_h}" rx="28" fill="{A2}"/>')
    s.add(f'<path d="M{bx + 44} {by + bubble_h - 3}L{bx + 50} {by + bubble_h + 26}L{bx + 80} {by + bubble_h - 3}Z" fill="{PAPER}" stroke="#000" stroke-width="3" stroke-linejoin="round"/>')
    s.add(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bubble_h}" rx="28" fill="{PAPER}" stroke="#000" stroke-width="3"/>')
    s.rect(bx + 47, by + bubble_h - 4, 30, 6, PAPER)
    ty = by + 30
    for lines in o_lines:
        for ln in lines:
            s.text(bx + 22, ty + 12, ln, "body", 15, INK)
            ty += 24.5
        ty += 14
    # Power-ups.
    punk_panel(s, c2x, y, c2w, r1, A3, A1)
    s.text(c2x + 24, y + 28 + 26, "POWER-UPS", "display", 30, INK, ls=1.2)
    py = y + 28 + 34 + 16
    tilts = (-2, 1, -1, 2)
    for label, col, skills in SKILL_GROUPS:
        s.text(c2x + 24, py + 10, label.upper(), "mono", 10.5, INK, ls=2.1)
        py += 18
        cx = 0
        for i, sk in enumerate(skills):
            wv = text_width(sk.upper(), "mono", 10.5, 0.4) + 16
            if cx and cx + wv > c2w - 48:
                cx, py = 0, py + 32
            s.tag(c2x + 24 + cx, py, sk, size=10.5, fill=PAPER if i % 3 == 0 else col, shadow="#000", rot=tilts[i % 4])
            cx += wv + 9
        py += 32 + 16
    y += r1 + GUT + 26
    # --- row 2: achievements | side quests
    a_items = []
    ah = 28 + 34 + 18
    for yr, t, d in AWARDS:
        dl = wrap(d, "body", 13, c1w - 48 - 80)
        a_items.append((yr, t, dl))
        ah += 26 + len(dl) * 19 + 16
    ah += 12
    sh = 28 + 34 + 18 + len(SIDE_QUESTS) * 62 + 12
    r2 = max(ah, sh)
    punk_panel(s, x0, y, c1w, r2, INK, A3)
    cid = s.clip_rect(x0, y, c1w, r2)
    s.add(f'<g clip-path="url(#{cid})">')
    s.speed_lines(x0 + c1w * 0.72, y + r2 * 0.45, c1w * 1.2, "#fff", 0.05)
    s.add("</g>")
    s.misprint(x0 + 24, y + 28 + 26, "ACHIEVEMENTS UNLOCKED", 30, FG, ls=1.2)
    ay = y + 28 + 34 + 18
    for yr, t, dl in a_items:
        s.caption(x0 + 24, ay, yr, rot=0, size=10.5)
        s.text(x0 + 24 + 80, ay + 18, t.upper(), "display", 21, A3, ls=1.0)
        for li, ln in enumerate(dl):
            s.text(x0 + 24 + 80, ay + 40 + li * 19, ln, "body", 13, MUTED)
        ay += 26 + len(dl) * 19 + 16
    punk_panel(s, c2x, y, c2w, r2, PAPER, A2)
    mid, gid = s.uid("fade"), s.uid("g")
    s.defn(f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff"/><stop offset="0.65" stop-color="#fff" stop-opacity="0"/></linearGradient>'
           f'<mask id="{mid}"><rect x="{c2x}" y="{y}" width="{c2w}" height="{r2}" fill="url(#{gid})"/></mask>')
    s.add(f'<g mask="url(#{mid})">')
    s.fill_dots(c2x, y, c2w, r2, "rgba(255,46,136,0.5)", 9, 1.5)
    s.add("</g>")
    s.rect(c2x, y, c2w, r2, "none", "#000", 3)
    s.text(c2x + 24, y + 28 + 26, "SIDE QUESTS", "display", 30, INK, ls=1.2)
    qy = y + 28 + 34 + 18
    for role, org, when in SIDE_QUESTS:
        s.rect(c2x + 24, qy, 5, 46, A1)
        s.text(c2x + 40, qy + 19, role.upper(), "display", 20, INK, ls=0.8)
        for li, ln in enumerate(wrap(f"{org} · {when}".upper(), "mono", 9.5, c2w - 70, 0.8)[:2]):
            s.text(c2x + 40, qy + 36 + li * 13, ln, "mono", 9.5, PAPER_MUTED, ls=0.8)
        qy += 62
    y += r2 + GUT + 20
    sheet_h = y - top
    H = top + sheet_h + 64
    s.h = H
    content = s.body[content_start:]
    del s.body[content_start:]
    # Scene: Earth-138 Spider-Punk photocopy.
    gid = s.uid("punk")
    s.defn(f'<linearGradient id="{gid}" x1="0" y1="0" x2="0.35" y2="1"><stop offset="0" stop-color="#ece6d6"/><stop offset="1" stop-color="#c9c2b2"/></linearGradient>')
    s.rect(0, 0, W, H, f"url(#{gid})")
    s.add(f'<path d="M{W * 0.62 + 300:.0f} 0L{W * 0.70 + 300:.0f} 0L{W * 0.70 - 300:.0f} {H}L{W * 0.62 - 300:.0f} {H}Z" fill="rgba(232,17,45,0.85)"/>')
    for ly in range(0, int(H), 7):
        s.rect(0, ly, W, 2, "rgba(0,0,0,0.07)")
    s.fill_dots(0, 0, W, H, "rgba(0,0,0,0.38)", 9, 1.7)
    sheet_bg(s, sx, top, sw, sheet_h, tilt=0.4)
    s.body.extend(content)
    continued(s, sx + sw - 24, top + sheet_h - 14, "Finale on the last page")
    s.label = ("Page 04, Chapter 03: A little about me. " + " ".join(ORIGIN) + " Power-ups: " +
               "; ".join(f"{g}: {', '.join(k)}" for g, _, k in SKILL_GROUPS) + ". Achievements: " +
               "; ".join(f"{y} {t} — {d}" for y, t, d in AWARDS) + ". Side quests: " +
               "; ".join(f"{r}, {o} ({w})" for r, o, w in SIDE_QUESTS) + ".")
    save(s, "page-04-about.svg")


# ---------------------------------------------------------------- contact

H_TOP, H_BOT = 380, 250


def contact_gradient(s, offset):
    gid = s.uid("sun")
    total = H_TOP + H_BOT + 70
    s.defn(f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="0" y1="{-offset}" x2="0" y2="{total - offset}">'
           '<stop offset="0" stop-color="#120a24"/><stop offset="0.3" stop-color="#3a0f2e"/><stop offset="0.62" stop-color="#a32d10"/><stop offset="1" stop-color="#ff7a1a"/></linearGradient>')
    return f"url(#{gid})"


def contact_top():
    s = Svg(W, H_TOP, "Chapter 04: Contact. Let's talk! Open to ML and AI engineering roles — deep learning systems, hardware-aware optimization, and ML for healthcare. Reach out, I reply fast.")
    s.rect(0, 0, W, H_TOP, contact_gradient(s, 0))
    s.rect(0, 0, W, 3, "#000")
    s.speed_lines(W * 0.72, H_TOP * 0.45, 1100, "#fff", 0.05)
    for x, y, c, r in ((380, 50, A3, 18), (560, 120, A2, 12), (610, 190, A2, 18), (760, 300, A3, 14), (820, 80, MUTED, 14), (300, 330, A2, 12)):
        s.add(f'<rect x="{x}" y="{y}" width="{r}" height="{r}" fill="{c}" opacity="0.45" transform="rotate(45 {x + r / 2} {y + r / 2})"/>')
    s.caption(54, 60, "Chapter 04 · Contact", rot=-2)
    s.misprint(54, 196, "LET'S", 96, FG, ls=1.5)
    s.misprint(54 + text_width("LET'S ", "display", 96, 1.5), 196, "TALK!", 96, A3, ls=1.5)
    para = "Open to ML and AI engineering roles — deep learning systems, hardware-aware optimization, and ML for healthcare. Reach out, I reply fast."
    for i, ln in enumerate(wrap(para, "body", 17.5, 470)):
        s.text(54, 252 + i * 29, ln, "body", 17.5, MUTED)
    save(s, "contact.svg")


def contact_bottom():
    s = Svg(W, H_BOT, "To be continued… Built with Next.js and Tailwind.")
    s.rect(0, 0, W, H_BOT, contact_gradient(s, H_TOP + 70))
    gid = s.uid("glow")
    s.defn(f'<radialGradient id="{gid}" cx="0.5" cy="1" r="0.8"><stop offset="0" stop-color="rgba(255,214,102,0.55)"/><stop offset="0.7" stop-color="rgba(255,214,102,0)"/></radialGradient>')
    s.rect(0, 0, W, H_BOT, f"url(#{gid})")
    # Retro grid floor.
    hz = 120
    lines = []
    for k in range(-14, 15):
        lines.append(f"M{W / 2 + k * 40:.0f} {hz}L{W / 2 + k * 180:.0f} {H_BOT}")
    yy, step = hz, 6
    while yy < H_BOT:
        lines.append(f"M0 {yy:.0f}H{W}")
        step *= 1.32
        yy += step
    s.add(f'<path d="{"".join(lines)}" stroke="#22e4ff" stroke-width="1.2" opacity="0.45" fill="none"/>')
    bx, by, bw, bh = 54, 40, W - 108, 58
    s.box(bx, by, bw, bh, INK, "#000", 5)
    s.text(bx + 22, by + 34, "© 2026 — Built with Next.js & Tailwind.", "monoreg", 12, MUTED)
    s.text(bx + bw - 22, by + 37, "TO BE CONTINUED…", "display", 21, A3, "end", 1.5)
    save(s, "contact-footer.svg")


def button(name, label, fill, icon):
    tw = text_width(label, "display", 21, 1.2)
    bw, bh = tw + 76, 54
    s = Svg(int(bw + 12), bh + 12, label.title())
    s.box(3, 3, bw, bh, fill, "#000", 5)
    s.add(f'<g transform="translate(25 {3 + bh / 2 - 10}) scale(0.83)" fill="none" stroke="{INK}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">{icon}</g>')
    s.text(54, 3 + bh / 2 + 8, label, "display", 21, INK, ls=1.2)
    save(s, name)


MAIL = '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>'
LINKEDIN = '<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect width="4" height="12" x="2" y="9"/><circle cx="4" cy="4" r="2"/>'
GLOBE = '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>'


LABELS = {}


def img(name, href, width="100%", stack=False):
    alt = LABELS[name].replace('"', "&quot;")
    w = f' width="{width}"' if width else ""
    # align="top" drops the inline baseline gap, so stacked slices butt together.
    a = ' align="top"' if stack else ""
    return f'<a href="{href}"><img src="assets/{name}"{w}{a} alt="{alt}"></a>'


def write_readme(project_files, research_files):
    stack = "<br>\n".join(
        [img("page-03-projects.svg", f"{SITE}/#projects", stack=True)]
        + [img(f, h, stack=True) for f, h in project_files]
        + [img("research-files.svg", f"{SITE}/#research", stack=True)]
        + [img(f, h, stack=True) for f, h in research_files]
    )
    md = f"""<!-- Generated by tools/build_readme.py from dat-dev.com's own data. Edit the site, then rebuild. -->

{img("front-page.svg", SITE)}

{img("page-02-experience.svg", f"{SITE}/#experience")}

<p>
{stack}
</p>

{img("page-04-about.svg", f"{SITE}/#about")}

{img("contact.svg", "mailto:harydat12@gmail.com")}

<p align="center">
{img("btn-email.svg", "mailto:harydat12@gmail.com", None)}&nbsp;&nbsp;{img("btn-linkedin.svg", "https://www.linkedin.com/in/dat-le-96aa27262", None)}&nbsp;&nbsp;{img("btn-site.svg", SITE, None)}
</p>

{img("contact-footer.svg", SITE)}
"""
    with open(os.path.join(REPO, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(md)


def main():
    os.makedirs(ASSETS, exist_ok=True)
    project_files, research_files = [], []
    front_page()
    experience_page()
    projects_header("Things I've built", "Chapter 02 · Projects & research", "page-03-projects.svg",
                    "Page 03, Chapter 02: Things I've built — projects and research.", page=3)
    projects = DATA["PROJECTS"]
    for i, p in enumerate(projects):
        slug = "".join(c if c.isalnum() else "-" for c in p["title"].lower()).strip("-")
        name = f"project-{i + 1:02d}-{slug}.svg"
        project_files.append((name, PROJECT_LINKS.get(p["title"], f"{SITE}/#projects")))
        project_card(name, p["title"], p["blurb"], p["tags"], p["year"], i,
                     f"Issue #{i + 1:02d}", f"#{i + 1:02d}", href=PROJECT_LINKS.get(p["title"]),
                     label=f'Issue #{i + 1:02d}: {p["title"]}{" (" + p["year"] + ")" if p["year"] else ""}. {p["blurb"]}')
    projects_header("Questions I've chased", "Research files", "research-files.svg",
                    "Research files: questions I've chased.")
    research = DATA["RESEARCH"]
    for k, r in enumerate(research):
        idx = len(projects) + k
        research_files.append((f"research-{k + 1:02d}.svg", r.get("href") or f"{SITE}/#research"))
        project_card(f"research-{k + 1:02d}.svg", r["title"], r["summary"], [], r["year"], idx,
                     f"Research file #{k + 1:02d}", "?!", href=r.get("href"), venue=r["venue"],
                     last=k == len(research) - 1,
                     label=f'Research file #{k + 1:02d}: {r["title"]} — {r["venue"]} ({r["year"]}). {r["summary"]}')
    about_page()
    contact_top()
    contact_bottom()
    button("btn-email.svg", "EMAIL ME", A3, MAIL)
    button("btn-linkedin.svg", "LINKEDIN", A1, LINKEDIN)
    button("btn-site.svg", "DAT-DEV.COM", A2, GLOBE)
    write_readme(project_files, research_files)


if __name__ == "__main__":
    main()
