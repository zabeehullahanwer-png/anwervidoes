"""Builds one .ass subtitle file that carries every text/graphic overlay:
captions (with word highlight), lower-thirds, hadith/ayah cards, keyword pops,
headline, intro/outro cards and the progress bar.

libass (inside ffmpeg) does proper Arabic / Urdu Nastaliq shaping and bidi,
which plain drawtext cannot, so all text goes through here.
"""

import math
import re
import unicodedata

FONT = {
    "arabic": "Amiri",
    "urdu": "Noto Nastaliq Urdu",
    "devanagari": "Hind",
    "latin": "Poppins",
}
# libass sizes a font by its (winAscent + winDescent) box, not its em. These
# ratios (box / em, read from the bundled fonts) let every size below be given
# as an *em* fraction of the short canvas side, so all scripts look consistent.
SIZE_FACTOR = {"arabic": 2.76, "urdu": 3.29, "devanagari": 1.60, "latin": 1.76}
# average advance per character in em (layout estimates only)
WIDTH_EM = {"arabic": 0.50, "urdu": 0.50, "devanagari": 0.55, "latin": 0.60}
# line height as a fraction of the libass font size
LINE_FACTOR = {"arabic": 0.80, "urdu": 0.62, "devanagari": 1.0, "latin": 1.0}

URDU_ONLY = set("ٹڈڑںےھہیکگپچژۓۀ")


def script_of(text, prefer="urdu"):
    """Detect which font family a text needs.
    prefer: what to use for Arabic-script text without Urdu-only letters
    ('arabic' for Quran/hadith text, 'urdu' for normal speech)."""
    has_ar = any("\u0600" <= ch <= "\u06FF" or "\u0750" <= ch <= "\u077F"
                 or "\uFB50" <= ch <= "\uFDFF" or "\uFE70" <= ch <= "\uFEFF" for ch in text)
    if has_ar:
        if prefer == "arabic" or (text.strip() and all(ch in "\uFDFA\uFDFB\uFDF2 " for ch in text)):
            return "arabic"
        return "urdu"
    if any("\u0900" <= ch <= "\u097F" for ch in text):
        return "devanagari"
    return "latin"


def is_rtl(text):
    return script_of(text) in ("urdu", "arabic")


def color(hx, alpha=0):
    hx = hx.lstrip("#")
    r, g, b = hx[0:2], hx[2:4], hx[4:6]
    return f"&H{alpha:02X}{b}{g}{r}&".upper()


def alpha_tag(a):
    return f"&H{a:02X}&"


def ts(t):
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def esc(text):
    text = text.replace("\\", "\u29F5").replace("{", "(").replace("}", ")")
    return text.replace("\r", "").replace("\n", "\\N")


def rrect_path(w, h, r):
    r = min(r, w / 2, h / 2)
    k = r * 0.45
    return (f"m {r:.0f} 0 l {w - r:.0f} 0 b {w - k:.0f} 0 {w:.0f} {k:.0f} {w:.0f} {r:.0f} "
            f"l {w:.0f} {h - r:.0f} b {w:.0f} {h - k:.0f} {w - k:.0f} {h:.0f} {w - r:.0f} {h:.0f} "
            f"l {r:.0f} {h:.0f} b {k:.0f} {h:.0f} 0 {h - k:.0f} 0 {h - r:.0f} "
            f"l 0 {r:.0f} b 0 {k:.0f} {k:.0f} 0 {r:.0f} 0")


def rect_path(w, h):
    return f"m 0 0 l {w:.0f} 0 {w:.0f} {h:.0f} 0 {h:.0f}"


def est_width(text, size, scr):
    n = sum(1 for ch in text if not unicodedata.combining(ch))
    return n * (size / SIZE_FACTOR[scr]) * WIDTH_EM[scr]


def est_lines(text, size, scr, max_w):
    lines = 0
    for part in text.split("\n"):
        lines += max(1, math.ceil(est_width(part, size, scr) / max_w))
    return lines


_RUN_RE = re.compile(r"([\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]+(?:[\s\u060C\u061F\u06D4:\d.()-]+[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]+)*)")


def split_runs(text):
    """Split mixed text into (segment, is_arabic_script) runs."""
    out, pos = [], 0
    for m in _RUN_RE.finditer(text):
        if m.start() > pos:
            out.append((text[pos:m.start()], False))
        out.append((m.group(0), True))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], False))
    if not out:
        return [(text, False)]
    # digits / punctuation / spaces stay with the surrounding Arabic-script text;
    # only real Latin / Devanagari words become separate runs
    if any(ar for _, ar in out):
        out = [(seg, ar or not re.search(r"[A-Za-z\u0900-\u097F]", seg)) for seg, ar in out]
    merged = []
    for seg, ar in out:
        if merged and merged[-1][1] == ar:
            merged[-1] = (merged[-1][0] + seg, ar)
        else:
            merged.append((seg, ar))
    return merged


def rtl_dominant(text):
    ar = sum(1 for ch in text if "\u0600" <= ch <= "\u06FF")
    lat = sum(1 for ch in text if ch.isalpha() and ch.isascii())
    return ar > lat


class AssDoc:
    def __init__(self, W, H, style, lang="ur"):
        self.W, self.H = W, H
        self.base = min(W, H)
        self.style = style
        self.lang = lang
        self.events = []
        self.prefer = "arabic" if lang == "ar" else "urdu"

    # -- helpers ----------------------------------------------------------
    def font_for(self, text, prefer=None):
        scr = script_of(text, prefer or self.prefer)
        return scr, FONT[scr]

    def size(self, frac, scr):
        return int(round(self.base * frac * SIZE_FACTOR[scr]))

    def add(self, t0, t1, text, layer=1, style="Default"):
        if t1 - t0 < 0.05:
            return
        self.events.append((layer, t0, t1, style, text))

    def text_tag(self, text, frac, prefer=None, bold=False, col=None, outline=0, outline_col="#000000",
                 shadow=0):
        """Style tag for the dominant script of `text` (use with self.mk for the body)."""
        scr, fn = self.font_for(text, prefer)
        sz = self.size(frac, scr)
        b = 1 if bold and scr in ("latin", "devanagari") else 0
        c = col or self.style["text"]
        if outline:
            outline = max(1, int(round(sz * 0.045 * (0.6 if scr in ("urdu", "arabic") else 1))))
        tag = (f"\\fn{fn}\\fs{sz}\\b{b}\\1c{color(c)}\\bord{outline}\\3c{color(outline_col)}"
               f"\\shad{shadow}\\4c{color('#000000')}\\4a&H80&")
        return tag, scr, sz

    def width(self, text, frac, prefer=None):
        prefer = prefer or self.prefer
        w = 0.0
        for seg, ar in split_runs(text):
            scr = (prefer if prefer in ("arabic", "urdu") else "urdu") if ar else script_of(seg)
            w += est_width(seg, self.size(frac, scr), scr)
        return w

    def mk(self, text, frac, prefer=None, bold=False, force=False):
        """Escaped body text; runs of a different script get their own font + size."""
        prefer = prefer or self.prefer
        runs = split_runs(text)
        if len(runs) == 1 and not force:
            return esc(text)
        out = []
        if len(runs) > 1 and rtl_dominant(text):
            runs = [(seg.strip() + " " if i else seg.strip(), ar) for i, (seg, ar) in enumerate(reversed(runs))]
        for seg, ar in runs:
            scr = (prefer if prefer in ("arabic", "urdu") else "urdu") if ar else script_of(seg)
            if not seg.strip():
                out.append(esc(seg))
                continue
            b = 1 if bold and scr in ("latin", "devanagari") else 0
            out.append("{\\fn%s\\fs%d\\b%d}" % (FONT[scr], self.size(frac, scr), b) + esc(seg))
        return "".join(out)

    # -- components -------------------------------------------------------
    def captions(self, chunks, y_bottom, max_w_frac=0.86, over_video=True):
        cap = self.style["captions"]
        acc = self.style["accent"]
        txt = self.style["text"]
        for ch in chunks:
            text = ch["text"].strip()
            if not text:
                continue
            scr, fn = self.font_for(text)
            sz = self.size(cap["size"], scr)
            if cap.get("box"):
                em = self.base * cap["size"]
                cy = int(y_bottom - em * 0.9)
                pre = (f"\\an5\\pos({self.W // 2},{cy})\\fn{fn}\\fs{sz}\\1c{color(txt)}"
                       f"\\bord0\\shad0")
                cstyle = "Default"
                bw = int(min(self.W * 0.94, self.width(text, cap["size"]) + em * 1.4))
                bh = int(em * 1.9)
                by = cy - int(em * (0.12 if scr in ("urdu", "arabic") else 0))
                self.add(ch["start"], ch["end"],
                         "{\\an5\\pos(%d,%d)\\bord0\\shad0\\1c%s\\1a&H38&\\fad(90,90)\\p1}%s{\\p0}"
                         % (self.W // 2, by, color(self.style.get("panel", "#000000")), rrect_path(bw, bh, em * 0.45)),
                         layer=4)
            else:
                pre = (f"\\an2\\pos({self.W // 2},{y_bottom})\\fn{fn}\\fs{sz}\\b{1 if scr == 'latin' else 0}"
                       f"\\1c{color(txt)}\\3c{color('#000000')}\\bord{max(2, int(sz * 0.08))}"
                       f"\\shad{max(1, int(sz * 0.05))}\\4a&H70&")
                cstyle = "Default"
            words = ch.get("words") or []
            t0, t1 = ch["start"], ch["end"]
            highlight = cap.get("highlight") and len(words) >= 2
            entry = "\\fad(90,0)"
            if cap.get("pop"):
                entry = "\\fad(60,0)\\fscx86\\fscy86\\t(0,110,\\fscx100\\fscy100)"
            exit_ = "\\fad(0,90)"
            if not highlight:
                tags = pre + entry.replace("\\fad(90,0)", "\\fad(90,90)")
                self.add(t0, t1, "{" + tags + "}" + self.mk(text, cap["size"], bold=True), layer=5, style=cstyle)
                continue
            # word-by-word highlight: one event per active word
            wl = [w["w"].strip() for w in words]
            rtl = rtl_dominant(text)
            hl = lambda w_: "{\\1c" + color(acc) + "}" + esc(w_) + "{\\1c" + color(txt) + "}"
            for i, w in enumerate(words):
                s = t0 if i == 0 else w["s"]
                e = words[i + 1]["s"] if i + 1 < len(words) else t1
                if e - s < 0.04:
                    continue
                before, after = " ".join(wl[:i]), " ".join(wl[i + 1:])
                if rtl:
                    # libass lays colour runs out left-to-right, so emit them in visual order
                    body = (esc(after) + " " if after else "") + hl(wl[i]) + (" " + esc(before) if before else "")
                    q = "\\q2"
                else:
                    body = (esc(before) + " " if before else "") + hl(wl[i]) + (" " + esc(after) if after else "")
                    q = ""
                fx = entry if i == 0 else ""
                if i == len(words) - 1:
                    fx += exit_
                self.add(s, e, "{" + pre + q + fx + "}" + body, layer=5, style=cstyle)

    def lower_third(self, t0, t1, name, title, x, y, max_w):
        """x,y = top-left anchor of the block (top-right when RTL)."""
        acc, panel = self.style["accent"], self.style.get("panel", "#000000")
        ntag, nscr, nsz = self.text_tag(name, 0.040, bold=True)
        ttag, tscr, tsz = self.text_tag(title or " ", 0.027, col=self.style.get("muted"))
        pad = int(self.base * 0.022)
        nh = nsz * LINE_FACTOR[nscr] * 0.8
        th = tsz * LINE_FACTOR[tscr] * 0.8 if title else 0
        h = int(pad * 1.6 + nh + th)
        w = int(min(max_w, max(self.width(name, 0.040), self.width(title or "", 0.027)) + pad * 3))
        bar = max(6, int(self.base * 0.008))
        rtl = is_rtl(name)
        dur_in = 450
        if rtl:
            x0 = x - w
            clip_from = f"\\clip({x},{y},{x},{y + h})"
            clip_to = f"\\clip({x0},{y},{x},{y + h})"
            bar_x = x - bar
            txt_x, an = x - bar - pad, 9
            sl = int(self.base * 0.03)
        else:
            x0 = x
            clip_from = f"\\clip({x},{y},{x},{y + h})"
            clip_to = f"\\clip({x},{y},{x + w},{y + h})"
            bar_x = x
            txt_x, an = x + bar + pad, 7
            sl = -int(self.base * 0.03)
        # panel (wipe in)
        self.add(t0, t1, "{\\an7\\pos(%d,%d)\\bord0\\shad0\\1c%s\\1a&H28&%s\\t(0,%d,%s)\\fad(0,300)\\p1}%s{\\p0}"
                 % (x0, y, color(panel), clip_from, dur_in, clip_to, rect_path(w, h)), layer=6)
        # accent bar
        self.add(t0, t1, "{\\an7\\pos(%d,%d)\\bord0\\shad0\\1c%s\\fad(150,300)\\p1}%s{\\p0}"
                 % (bar_x, y, color(acc), rect_path(bar, h)), layer=7)
        ny = y + int(pad * 0.6)
        self.add(t0 + 0.15, t1, "{\\an%d\\move(%d,%d,%d,%d,0,350)%s\\fad(250,300)}%s"
                 % (an, txt_x + sl, ny, txt_x, ny, ntag, self.mk(name, 0.040, bold=True)), layer=8)
        if title:
            ty = int(ny + nh)
            self.add(t0 + 0.3, t1, "{\\an%d\\move(%d,%d,%d,%d,0,350)%s\\fad(250,300)}%s"
                     % (an, txt_x + sl, ty, txt_x, ty, ttag, self.mk(title, 0.027)), layer=8)

    def divider(self, t0, t1, cx, y, w, delay_ms=0, layer=7):
        acc = self.style["accent"]
        lh = max(2, int(self.base * 0.0028))
        d = int(self.base * 0.014)
        # line that grows from the centre
        self.add(t0, t1, "{\\an5\\pos(%d,%d)\\bord0\\shad0\\1c%s\\fscx0\\t(%d,%d,\\fscx100)\\fad(0,300)\\p1}%s{\\p0}"
                 % (cx, y, color(acc), delay_ms, delay_ms + 600, rect_path(w, lh)), layer=layer)
        diamond = f"m {d} 0 l {2 * d} {d} {d} {2 * d} 0 {d}"
        self.add(t0, t1, "{\\an5\\pos(%d,%d)\\bord0\\shad0\\1c%s\\fad(%d,300)\\p1}%s{\\p0}"
                 % (cx, y, color(acc), 300 + delay_ms, diamond), layer=layer + 1)

    def scrim(self, t0, t1, alpha=0x50, col="#000000", fade=(350, 350), layer=4):
        self.add(t0, t1, "{\\an7\\pos(0,0)\\bord0\\shad0\\1c%s\\1a%s\\fad(%d,%d)\\p1}%s{\\p0}"
                 % (color(col), alpha_tag(alpha), fade[0], fade[1], rect_path(self.W, self.H)), layer=layer)

    def quote_card(self, t0, t1, arabic="", translation="", reference="", label="", mode="overlay",
                   on_background=False):
        W, H = self.W, self.H
        cx = W // 2
        area_w = W * (0.84 if H > W else 0.70)
        txt_col = self.style.get("on_background_text", self.style["text"]) if on_background else self.style["text"]
        if mode == "overlay":
            self.scrim(t0, t1, alpha=0x48)
            txt_col = self.style["text"]
        blocks = []  # (kind, text, frac, prefer, col)
        if label:
            blocks.append(("label", label, 0.032, None, self.style["accent"]))
        if arabic:
            blocks.append(("arabic", arabic, 0.070, "arabic", self.style["accent"] if not on_background
                           else self.style["accent"]))
        if arabic and (translation or reference):
            blocks.append(("divider", "", 0, None, None))
        if translation:
            blocks.append(("translation", translation, 0.046, None, txt_col))
        if reference:
            blocks.append(("reference", reference, 0.029, None, self.style.get("muted", txt_col)
                           if not on_background else self.style["accent"]))
        # measure
        heights = []
        for kind, text, frac, prefer, _ in blocks:
            if kind == "divider":
                heights.append(self.base * 0.05)
                continue
            scr, _fn = self.font_for(text, prefer)
            sz = self.size(frac, scr)
            heights.append(est_lines(text, sz, scr, area_w) * sz * LINE_FACTOR[scr] * 0.85 + self.base * 0.035)
        total = sum(heights)
        y = max(H * 0.08, H * 0.47 - total / 2)
        margin = int((W - area_w) / 2)
        delays = {"label": 0, "arabic": 150, "divider": 500, "translation": 750, "reference": 1100}
        for (kind, text, frac, prefer, col), hgt in zip(blocks, heights):
            dl = delays[kind]
            if kind == "divider":
                self.divider(t0, t1, cx, int(y + hgt / 2), int(area_w * 0.45), delay_ms=dl)
            else:
                tag, scr, sz = self.text_tag(text, frac, prefer=prefer, col=col, bold=(kind == "label"),
                                             outline=0 if on_background else 1,
                                             shadow=0 if on_background else 2)
                anim = ("\\alpha&HFF&\\t(%d,%d,\\alpha&H00&)\\blur4\\t(%d,%d,\\blur0)\\fad(0,350)"
                        % (dl, dl + 600, dl, dl + 700))
                if kind == "arabic":
                    anim += "\\fscx96\\fscy96\\t(%d,%d,\\fscx100\\fscy100)" % (dl, dl + 1400)
                self.add(t0, t1, "{\\an8\\pos(%d,%d)\\q0%s%s}%s"
                         % (cx, int(y), tag, anim, self.mk(text, frac, prefer, bold=(kind == "label"))), layer=9)
            y += hgt
        return margin

    def keyword(self, t0, t1, text, cx, cy, frac=0.090):
        tag, scr, sz = self.text_tag(text, frac, bold=True, col=self.style["accent"],
                                     outline=max(3, int(self.base * 0.006)), shadow=3)
        self.add(t0, t1, "{\\an5\\pos(%d,%d)%s\\fscx55\\fscy55\\t(0,140,\\fscx112\\fscy112)"
                         "\\t(140,260,\\fscx100\\fscy100)\\fad(0,220)}%s"
                 % (cx, cy, tag, self.mk(text, frac, bold=True)), layer=10)

    def headline(self, t0, t1, text, cx, cy, max_w, kicker="", frac=0.058):
        """Title block: optional kicker, 1-2 balanced lines (placed explicitly; Nastaliq's
        natural line box is far too tall), then an animated gold divider."""
        col = self.style.get("on_background_text", self.style["text"])
        em = self.base * frac
        lines = [text]
        if self.width(text, frac) > max_w and len(text.split()) > 1:
            words = text.split()
            best = None
            for k in range(1, len(words)):
                a_, b_ = " ".join(words[:k]), " ".join(words[k:])
                d = abs(self.width(a_, frac) - self.width(b_, frac))
                if best is None or d < best[0]:
                    best = (d, [a_, b_])
            lines = best[1]
            frac = min(frac, frac * max_w / max(self.width(l, frac) for l in lines))
            em = self.base * frac
        gap = em * 1.75
        y0 = cy - gap * (len(lines) - 1) / 2
        for i, line in enumerate(lines):
            tag, scr, sz = self.text_tag(line, frac, bold=True, outline=2, shadow=2, col=col)
            self.add(t0, t1, "{\\an5\\pos(%d,%d)%s\\fad(%d,300)\\blur3\\t(0,500,\\blur0)}%s"
                     % (cx, int(y0 + i * gap), tag, 500 + 150 * i, self.mk(line, frac, bold=True)), layer=6)
        bottom = y0 + gap * (len(lines) - 1) + em * 1.2
        self.divider(t0, t1, cx, int(bottom), int(self.base * 0.22), delay_ms=300)
        if kicker:
            ktag, kscr, ksz = self.text_tag(kicker, 0.030, col=self.style["accent"], bold=True)
            self.add(t0, t1, "{\\an5\\pos(%d,%d)%s\\fad(500,300)}%s"
                     % (cx, int(y0 - em * 1.3), ktag, self.mk(kicker, 0.030, bold=True)), layer=6)

    def intro(self, t0, t1, top_text, name, subtitle, on_background_col):
        W, H = self.W, self.H
        cx = W // 2
        if top_text:
            tag, scr, sz = self.text_tag(top_text, 0.074, prefer="arabic", col=self.style["accent"])
            self.add(t0, t1, "{\\an5\\pos(%d,%d)%s\\fad(700,400)\\blur6\\t(0,800,\\blur0)"
                             "\\fscx94\\fscy94\\t(0,%d,\\fscx102\\fscy102)}%s"
                     % (cx, int(H * 0.43), tag, int((t1 - t0) * 1000), self.mk(top_text, 0.074, "arabic")), layer=9)
        self.divider(t0 + 0.3, t1, cx, int(H * 0.515), int(self.base * 0.3))
        if name:
            tag, scr, sz = self.text_tag(name, 0.042, bold=True, col=on_background_col)
            self.add(t0 + 0.5, t1, "{\\an8\\pos(%d,%d)%s\\fad(500,400)}%s" % (cx, int(H * 0.54), tag, self.mk(name, 0.042, bold=True)), layer=9)
        if subtitle:
            tag, scr, sz = self.text_tag(subtitle, 0.027, col=self.style["accent"])
            self.add(t0 + 0.8, t1, "{\\an8\\pos(%d,%d)%s\\fad(500,400)}%s" % (cx, int(H * 0.54 + self.base * 0.11), tag,
                                                                          self.mk(subtitle, 0.027)), layer=9)

    def outro(self, t0, t1, name, cta, handle, on_background_col):
        W, H = self.W, self.H
        cx = W // 2
        if name:
            tag, scr, sz = self.text_tag(name, 0.048, bold=True, col=on_background_col)
            self.add(t0, t1, "{\\an2\\pos(%d,%d)%s\\fad(500,500)}%s" % (cx, int(H * 0.44), tag, self.mk(name, 0.048, bold=True)), layer=9)
        self.divider(t0 + 0.2, t1, cx, int(H * 0.475), int(self.base * 0.3))
        if cta:
            tag, scr, sz = self.text_tag(cta, 0.034, bold=True, col=self.style.get("panel", "#000000"))
            pw = int(min(W * 0.92, self.width(cta, 0.034) + self.base * 0.10))
            ph = int(sz * LINE_FACTOR[scr] * 0.9)
            py = int(H * 0.53)
            self.add(t0 + 0.4, t1, "{\\an8\\pos(%d,%d)\\bord0\\shad0\\1c%s\\fscx80\\fscy80\\t(0,250,\\fscx100\\fscy100)"
                                   "\\fad(250,500)\\p1}%s{\\p0}"
                     % (cx, py, color(self.style["accent"]), rrect_path(pw, ph, ph / 2)), layer=9)
            self.add(t0 + 0.55, t1, "{\\an5\\pos(%d,%d)%s\\fad(250,500)}%s"
                     % (cx, int(py + ph / 2), tag, self.mk(cta, 0.034, bold=True)), layer=10)
        if handle:
            tag, scr, sz = self.text_tag(handle, 0.028, col=on_background_col)
            self.add(t0 + 0.8, t1, "{\\an8\\pos(%d,%d)%s\\fad(400,500)}%s"
                     % (cx, int(H * 0.53 + self.base * 0.13), tag, self.mk(handle, 0.028)), layer=9)

    def watermark(self, t0, t1, text, top_right=True, bottom=False):
        tag, scr, sz = self.text_tag(text, 0.022, col="#FFFFFF", outline=1, shadow=1)
        m = int(self.base * 0.04)
        if bottom:
            pos = "\\an2\\pos(%d,%d)" % (self.W // 2, self.H - int(m * 0.55))
        elif top_right:
            pos = "\\an9\\pos(%d,%d)" % (self.W - m, m)
        else:
            pos = "\\an7\\pos(%d,%d)" % (m, m)
        self.add(t0, t1, "{%s%s\\alpha&H70&\\fad(600,300)}%s" % (pos, tag, self.mk(text, 0.022)), layer=3)

    def progress_bar(self, t0, t1, y=None):
        h = max(5, int(self.base * 0.007))
        y = self.H - h if y is None else y
        dur = int((t1 - t0) * 1000)
        self.add(t0, t1, "{\\an7\\pos(0,%d)\\bord0\\shad0\\1c%s\\1a&H90&\\p1}%s{\\p0}"
                 % (y, color("#FFFFFF"), rect_path(self.W, h)), layer=11)
        self.add(t0, t1, "{\\an7\\pos(0,%d)\\bord0\\shad0\\1c%s\\clip(0,%d,1,%d)\\t(0,%d,\\clip(0,%d,%d,%d))\\p1}%s{\\p0}"
                 % (y, color(self.style["accent"]), y, y + h, dur, y, self.W, y + h, rect_path(self.W, h)), layer=12)

    # -- output -----------------------------------------------------------
    def write(self, path):
        head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {self.W}
PlayResY: {self.H}
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Poppins,{int(self.base * 0.04)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,{int(self.W * 0.07)},{int(self.W * 0.07)},{int(self.H * 0.06)},1
Style: Box,Poppins,{int(self.base * 0.04)},&H00FFFFFF,&H00FFFFFF,&H40000000,&H40000000,0,0,0,0,100,100,0,0,3,10,0,2,{int(self.W * 0.07)},{int(self.W * 0.07)},{int(self.H * 0.06)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        lines = []
        for layer, t0, t1, style, text in sorted(self.events, key=lambda e: (e[1], e[0])):
            lines.append(f"Dialogue: {layer},{ts(t0)},{ts(t1)},{style},,0,0,0,,{text}")
        with open(path, "w", encoding="utf-8") as f:
            f.write(head + "\n".join(lines) + "\n")


