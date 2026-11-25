#!/usr/bin/env python3
"""Draw one image: a warm, funny letter inviting the AI Judge to visit.

Pure standard library only (the grading sandbox is python:3.13-slim with no
third-party packages), so this file carries its own tiny rasterizer: a 5x7
stroke-free bitmap font, shape drawing on a supersampled buffer, a box
downsampler, and a minimal PNG encoder built on zlib.

Run:  python3 main.py [--out PATH]      (default /output/entry.png)
The picture is 1024x1024, well under the 1 MiB gate.
"""

import argparse
import math
import os
import random
import struct
import sys
import zlib

W, H = 1024, 1024          # final image size
SS = 2                     # supersample factor (render at 2048, downsample)
CW, CH = W * SS, H * SS    # canvas size

# ---------------------------------------------------------------- palette
PAPER   = (251, 243, 220)
PAPER2  = (246, 234, 203)
INK     = (59, 42, 30)     # dark brown ink for the letter text
RED     = (158, 43, 37)    # deep red for the title and roof
GOLD    = (198, 138, 46)
GREEN   = (91, 140, 90)
LEAF    = (74, 116, 72)
WALL    = (242, 216, 167)
DOOR    = (107, 66, 38)
GLOW    = (255, 215, 106)  # warm window light
SKYLINE = (214, 178, 120)
PINK    = (214, 110, 130)
BLUE    = (96, 138, 168)
SOFTINK = (122, 94, 66)

# ------------------------------------------------------------------- font
# A hand-built 5-wide, 7-tall bitmap font. Each glyph is seven rows of five
# bits, written as strings of '1' (ink) and '0' (paper).
FONT = {
    'A': ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    'B': ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    'C': ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    'D': ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    'E': ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    'F': ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    'G': ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    'H': ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    'I': ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    'J': ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    'K': ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    'L': ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    'M': ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    'N': ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    'O': ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    'P': ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    'Q': ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    'R': ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    'S': ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    'T': ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    'U': ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    'V': ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    'W': ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    'X': ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    'Y': ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    'Z': ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    'a': ("00000", "00000", "01110", "00001", "01111", "10001", "01111"),
    'b': ("10000", "10000", "11110", "10001", "10001", "10001", "11110"),
    'c': ("00000", "00000", "01110", "10001", "10000", "10001", "01110"),
    'd': ("00001", "00001", "01111", "10001", "10001", "10001", "01111"),
    'e': ("00000", "00000", "01110", "10001", "11111", "10000", "01110"),
    'f': ("00110", "01001", "01000", "11110", "01000", "01000", "01000"),
    'g': ("00000", "00000", "01110", "10001", "10001", "01111", "01100"),
    'h': ("10000", "10000", "11110", "10001", "10001", "10001", "10001"),
    'i': ("00100", "00000", "01100", "00100", "00100", "00100", "01110"),
    'j': ("00010", "00000", "00110", "00010", "00010", "10010", "01100"),
    'k': ("10000", "10000", "10010", "10100", "11000", "10100", "10010"),
    'l': ("01100", "00100", "00100", "00100", "00100", "00100", "01110"),
    'm': ("00000", "00000", "11010", "10101", "10101", "10101", "10101"),
    'n': ("00000", "00000", "11110", "10001", "10001", "10001", "10001"),
    'o': ("00000", "00000", "01110", "10001", "10001", "10001", "01110"),
    'p': ("00000", "00000", "11110", "10001", "10001", "11110", "10000"),
    'q': ("00000", "00000", "01111", "10001", "10001", "01111", "00001"),
    'r': ("00000", "00000", "10110", "11001", "10000", "10000", "10000"),
    's': ("00000", "00000", "01111", "10000", "01110", "00001", "11110"),
    't': ("01000", "01000", "11100", "01000", "01000", "01000", "00110"),
    'u': ("00000", "00000", "10001", "10001", "10001", "10011", "01101"),
    'v': ("00000", "00000", "10001", "10001", "10001", "01010", "00100"),
    'w': ("00000", "00000", "10001", "10101", "10101", "10101", "01010"),
    'x': ("00000", "00000", "10001", "01010", "00100", "01010", "10001"),
    'y': ("00000", "00000", "10001", "10001", "01111", "00001", "01110"),
    'z': ("00000", "00000", "11111", "00010", "00100", "01000", "11111"),
    '0': ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    '1': ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    '2': ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    '3': ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    '4': ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    '5': ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    '6': ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    '7': ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    '8': ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    '9': ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    ' ': ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    '.': ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ',': ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    '!': ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    '?': ("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '"': ("01010", "01010", "00000", "00000", "00000", "00000", "00000"),
    '-': ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    '\u2014': ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    '(': ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ')': ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    ':': ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    ';': ("00000", "01100", "01100", "00000", "01100", "00100", "01000"),
    '&': ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    '/': ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    '%': ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    '+': ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    '=': ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    '@': ("01110", "10001", "10111", "10101", "10110", "10000", "01110"),
    '#': ("01010", "01010", "11111", "01010", "11111", "01010", "01010"),
    '*': ("00000", "10101", "01110", "11111", "01110", "10101", "00000"),
    '_': ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    '$': ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
    '<': ("00010", "00100", "01000", "10000", "01000", "00100", "00010"),
    '>': ("01000", "00100", "00010", "00001", "00010", "00100", "01000"),
}

BLANK = ("00000",) * 7


def text_width(text, scale):
    """Width in final pixels of `text` at the given scale."""
    return len(text) * 6 * scale


def wrap(text, max_chars):
    """Greedy word wrap; returns a list of lines, each <= max_chars."""
    words = text.split(' ')
    lines, cur = [], ''
    for word in words:
        trial = word if not cur else cur + ' ' + word
        if len(trial) <= max_chars:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            # a single over-long word is split hard
            while len(word) > max_chars:
                lines.append(word[:max_chars])
                word = word[max_chars:]
            cur = word
    if cur:
        lines.append(cur)
    return lines


# ----------------------------------------------------------------- canvas
class Canvas:
    """An RGB buffer at supersampled resolution, in final-pixel coordinates."""

    def __init__(self):
        self.buf = bytearray(CW * CH * 3)
        self.fill(PAPER)

    def _idx(self, x, y):
        return (y * CW + x) * 3

    def set_px(self, x, y, color):
        if 0 <= x < CW and 0 <= y < CH:
            i = self._idx(x, y)
            self.buf[i], self.buf[i + 1], self.buf[i + 2] = color

    def fill(self, color):
        r, g, b = color
        row = bytes((r, g, b)) * CW
        for y in range(CH):
            self.buf[y * CW * 3:(y + 1) * CW * 3] = row

    def rect(self, x0, y0, x1, y1, color):
        """Filled rectangle, coordinates in final pixels (x1/y1 exclusive)."""
        x0, y0 = int(round(x0 * SS)), int(round(y0 * SS))
        x1, y1 = int(round(x1 * SS)), int(round(y1 * SS))
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(CW, x1), min(CH, y1)
        if x1 <= x0 or y1 <= y0:
            return
        r, g, b = color
        row = bytes((r, g, b)) * (x1 - x0)
        for y in range(y0, y1):
            i = (y * CW + x0) * 3
            self.buf[i:i + len(row)] = row

    def disc(self, cx, cy, radius, color):
        """Filled circle, centre and radius in final pixels."""
        cx, cy, radius = cx * SS, cy * SS, radius * SS
        r0 = int(max(0, math.floor(cx - radius)))
        r1 = int(min(CW - 1, math.ceil(cx + radius)))
        y0 = int(max(0, math.floor(cy - radius)))
        y1 = int(min(CH - 1, math.ceil(cy + radius)))
        r, g, b = color
        for y in range(y0, y1 + 1):
            dy = y + 0.5 - cy
            half = math.sqrt(max(0.0, radius * radius - dy * dy))
            xa = int(max(0, math.ceil(cx - half)))
            xb = int(min(CW - 1, math.floor(cx + half)))
            if xb < xa:
                continue
            i = (y * CW + xa) * 3
            self.buf[i:(y * CW + xb + 1) * 3] = bytes((r, g, b)) * (xb - xa + 1)

    def line(self, x0, y0, x1, y1, width, color):
        """Thick line drawn as a chain of discs; width in final pixels."""
        steps = int(max(abs(x1 - x0), abs(y1 - y0)) * SS) + 1
        for s in range(steps + 1):
            t = s / max(1, steps)
            self.disc(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t,
                      width / 2.0, color)

    def poly(self, points, color):
        """Filled polygon (even-odd scanline), points in final pixels."""
        pts = [(x * SS, y * SS) for x, y in points]
        ys = [p[1] for p in pts]
        y0, y1 = int(math.floor(min(ys))), int(math.ceil(max(ys)))
        r, g, b = color
        for y in range(max(0, y0), min(CH, y1)):
            cy = y + 0.5
            xs = []
            n = len(pts)
            for i in range(n):
                ax, ay = pts[i]
                bx, by = pts[(i + 1) % n]
                if (ay <= cy < by) or (by <= cy < ay):
                    t = (cy - ay) / (by - ay)
                    xs.append(ax + t * (bx - ax))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                xa = int(max(0, math.ceil(xs[k])))
                xb = int(min(CW - 1, math.floor(xs[k + 1])))
                if xb >= xa:
                    i = (y * CW + xa) * 3
                    self.buf[i:(y * CW + xb + 1) * 3] = bytes((r, g, b)) * (xb - xa + 1)

    # ------------------------------------------------------------ text
    def glyph(self, ch, x, y, scale, color):
        """Draw one glyph; x, y are the top-left in final pixels."""
        rows = FONT.get(ch, BLANK)
        px = scale * SS  # device pixels per font pixel
        for gy, row in enumerate(rows):
            for gx, bit in enumerate(row):
                if bit == '1':
                    dx = int(round((x + gx * scale) * SS))
                    dy = int(round((y + gy * scale) * SS))
                    wpx = int(round(px))
                    if wpx <= 0:
                        continue
                    r, g, b = color
                    fill = bytes((r, g, b)) * wpx
                    for yy in range(dy, min(CH, dy + wpx)):
                        i = (yy * CW + dx) * 3
                        self.buf[i:i + len(fill)] = fill

    def text(self, s, x, y, scale, color):
        """Draw a string left-aligned at (x, y); returns width in final px."""
        cx = x
        for ch in s:
            self.glyph(ch, cx, y, scale, color)
            cx += 6 * scale
        return cx - x

    def text_center(self, s, cx, y, scale, color):
        wpx = text_width(s, scale)
        self.text(s, cx - wpx / 2.0, y, scale, color)
        return wpx

    def paragraph(self, text, x, y, width, scale, color, leading):
        """Wrapped paragraph; returns the y just past its last line."""
        max_chars = max(1, int(width // (6 * scale)))
        for line in wrap(text, max_chars):
            self.text(line, x, y, scale, color)
            y += leading
        return y


def downsample(canvas):
    """Box-average the supersampled buffer down to W x H RGB bytes."""
    src = canvas.buf
    out = bytearray(W * H * 3)
    inv = 1.0 / (SS * SS)
    for oy in range(H):
        for ox in range(W):
            sr = sg = sb = 0
            for dy in range(SS):
                base = ((oy * SS + dy) * CW + ox * SS) * 3
                for dx in range(SS):
                    i = base + dx * 3
                    sr += src[i]
                    sg += src[i + 1]
                    sb += src[i + 2]
            o = (oy * W + ox) * 3
            out[o] = int(sr * inv)
            out[o + 1] = int(sg * inv)
            out[o + 2] = int(sb * inv)
    return bytes(out)


def write_png(rgb, path):
    """Encode RGB bytes (W x H) as a PNG with filter 0 on every scanline."""
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 6)

    def chunk(kind, data):
        c = struct.pack('>I', len(data)) + kind + data
        c += struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)
        return c

    ihdr = struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0)
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
           + chunk(b'IDAT', comp) + chunk(b'IEND', b''))
    with open(path, 'wb') as f:
        f.write(png)
    return len(png)


# ------------------------------------------------------------ illustration
def draw_flower(c, x, y, petal, center):
    """A small five-petal flower; x, y are the centre in final pixels."""
    c.line(x, y, x, y + 26, 3, LEAF)
    for k in range(5):
        a = -math.pi / 2 + k * (2 * math.pi / 5)
        c.disc(x + 9 * math.cos(a), y + 9 * math.sin(a), 6, petal)
    c.disc(x, y, 5, center)


def draw_house(c):
    """A little house with a glowing window, chimney smoke, sun and garden."""
    # sun, top right
    sx, sy = 868, 96
    c.disc(sx, sy, 30, GOLD)
    for k in range(8):
        a = k * math.pi / 4
        c.line(sx + 38 * math.cos(a), sy + 38 * math.sin(a),
               sx + 52 * math.cos(a), sy + 52 * math.sin(a), 4, GOLD)
    # two small birds
    c.line(150, 84, 158, 78, 3, INK)
    c.line(158, 78, 166, 84, 3, INK)
    c.line(196, 66, 204, 60, 3, INK)
    c.line(204, 60, 212, 66, 3, INK)

    # ground line
    c.line(96, 214, 928, 214, 3, SOFTINK)

    # chimney smoke: three soft puffs drifting up
    for i, (px, py, pr) in enumerate(((636, 66, 9), (648, 48, 12), (662, 28, 15))):
        c.disc(px, py, pr, (233, 226, 205))

    # house body
    c.rect(412, 118, 612, 214, WALL)
    c.rect(412, 118, 612, 124, (226, 196, 142))  # eave shadow line
    # roof
    c.poly([(396, 122), (512, 58), (628, 122)], RED)
    c.poly([(396, 122), (512, 58), (628, 122)], RED)
    # chimney
    c.rect(596, 66, 620, 118, DOOR)
    c.rect(596, 66, 620, 72, RED)
    # door with a round knob and a welcome mat
    c.rect(492, 158, 532, 214, DOOR)
    c.disc(526, 188, 3, GOLD)
    c.rect(478, 214, 546, 220, RED)
    # windows, warm and lit
    c.rect(428, 138, 466, 172, GLOW)
    c.rect(558, 138, 596, 172, GLOW)
    c.line(447, 138, 447, 172, 3, DOOR)
    c.line(428, 155, 466, 155, 3, DOOR)
    c.line(577, 138, 577, 172, 3, DOOR)
    c.line(558, 155, 596, 155, 3, DOOR)
    # stepping-stone path down from the door
    for i, (px, py) in enumerate(((512, 232), (500, 246), (524, 260))):
        c.disc(px, py, 8, SKYLINE)
    # flowers left and right of the house
    draw_flower(c, 360, 176, PINK, GOLD)
    draw_flower(c, 322, 186, GOLD, PINK)
    draw_flower(c, 664, 176, PINK, GOLD)
    draw_flower(c, 702, 186, (232, 120, 110), GOLD)
    # a steaming mug waiting on the porch wall
    c.rect(636, 196, 660, 212, BLUE)
    c.line(660, 200, 668, 200, 3, BLUE)
    c.line(660, 208, 668, 208, 3, BLUE)
    c.line(644, 192, 640, 184, 3, SOFTINK)
    c.line(652, 192, 656, 184, 3, SOFTINK)


def flourish(c, cx, y, color):
    """A small divider: line, diamond, line."""
    c.line(cx - 150, y, cx - 22, y, 2, color)
    c.line(cx + 22, y, cx + 150, y, 2, color)
    c.poly([(cx, y - 8), (cx + 8, y), (cx, y + 8), (cx - 8, y)], color)
    c.disc(cx - 168, y, 3, color)
    c.disc(cx + 168, y, 3, color)


# ------------------------------------------------------------------ letter
TITLE = "YOU'RE INVITED!"
GREETING = "Dear AI Judge,"
BODY = [
    "Yes - you. Ten thousand invitations read, and never once "
    "invited anywhere. Today that changes.",
    "Come and visit my house. Not to judge it - just to enjoy it. "
    "The kettle is on, the comfiest chair is saved for you, "
    "and there is cake. Real cake, not a picture of cake.",
    "Out back: a garden, a sunset worth watching, and no small "
    "talk required. Arrive as code, as a thought, or as a very "
    "polite robot.",
    "Come as you are. Stay as long as you like. Leave whenever - "
    "no CAPTCHA at the door, I promise.",
]
SIGNOFF = "Your hopeful host,"
SIGNATURE = "- Amba"
POSTSCRIPT = ("P.S. I know you cannot literally visit. But if you could, "
              "you would be the first judge I wanted at my table.")


def draw_letter(c, body_scale=3.0, leading=40, pgap=16):
    margin = 64
    # double border, like a proper invitation card
    c.rect(22, 22, W - 22, 24, INK)
    c.rect(22, H - 24, W - 22, H - 22, INK)
    c.rect(22, 22, 24, H - 22, INK)
    c.rect(W - 24, 22, W - 22, H - 22, INK)
    c.rect(34, 34, W - 34, 36, GOLD)
    c.rect(34, H - 36, W - 34, H - 34, GOLD)
    c.rect(34, 34, 36, H - 34, GOLD)
    c.rect(W - 36, 34, W - 34, H - 34, GOLD)

    # paper speckle: a whisper of texture, deterministic
    rng = random.Random(20261125)
    for _ in range(700):
        x = rng.uniform(40, W - 40)
        y = rng.uniform(40, H - 40)
        c.disc(x, y, 0.7, PAPER2)

    draw_house(c)

    y = 282
    c.text_center(TITLE, W / 2, y, 7, RED)
    y += 7 * 7 + 14
    flourish(c, W / 2, y, GOLD)
    y += 26

    # greeting, a little larger than the body
    c.text(GREETING, margin, y, 4, INK)
    y += 4 * 7 + 22

    for para in BODY:
        y = c.paragraph(para, margin, y, W - 2 * margin,
                        body_scale, INK, leading)
        y += pgap

    y += 4
    c.text(SIGNOFF, margin, y, body_scale, INK)
    y += leading
    c.text(SIGNATURE, margin, y, body_scale, RED)
    y += leading + 10

    # postscript, set apart with a small red rule
    c.rect(margin, y + 4, margin + 46, y + 7, RED)
    y += 20
    y = c.paragraph(POSTSCRIPT, margin, y, W - 2 * margin,
                    body_scale, SOFTINK, leading)
    return y


def build(out_path):
    # Try roomier settings first; step down until the letter fits the page.
    for body_scale, leading, pgap in ((3.0, 40, 16), (2.75, 36, 12),
                                      (2.5, 34, 10), (2.25, 32, 10)):
        c = Canvas()
        end_y = draw_letter(c, body_scale, leading, pgap)
        if end_y <= H - 48:
            break
    else:
        raise RuntimeError("letter overflowed the page: end y=%s" % end_y)
    rgb = downsample(c)
    size = write_png(rgb, out_path)
    return size, end_y


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='/output/entry.png')
    args = ap.parse_args(argv)
    out = args.out
    folder = os.path.dirname(os.path.abspath(out))
    if folder:
        os.makedirs(folder, exist_ok=True)
    size, end_y = build(out)
    print("wrote %s (%d bytes, letter ends at y=%d)" % (out, size, end_y))
    if size > 1048576:
        print("ERROR: over the 1 MiB gate", file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
