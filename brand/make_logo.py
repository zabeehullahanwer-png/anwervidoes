"""Generates the Zabeehullah Leghari logo set as SVG, rendered to PNG with ffmpeg (librsvg).
Run: python3 brand/make_logo.py"""
import math, os, subprocess

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo")
NAVY, NAVY2 = "#071522", "#0E2E3A"
UR, EN = "ذبیح اللہ لغاری", "ZABEEHULLAH LEGHARI"

DEFS = """
<defs>
  <linearGradient id="gold" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#FBEBB5"/><stop offset="0.45" stop-color="#D9B465"/>
    <stop offset="0.75" stop-color="#B8893A"/><stop offset="1" stop-color="#E8C77A"/>
  </linearGradient>
  <linearGradient id="goldH" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#B8893A" stop-opacity="0"/><stop offset="0.5" stop-color="#E8C77A"/>
    <stop offset="1" stop-color="#B8893A" stop-opacity="0"/>
  </linearGradient>
  <radialGradient id="bg" cx="0.5" cy="0.45" r="0.75">
    <stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/>
  </radialGradient>
  <radialGradient id="disc" cx="0.5" cy="0.4" r="0.6">
    <stop offset="0" stop-color="#123A46"/><stop offset="1" stop-color="#06121C"/>
  </radialGradient>
</defs>""" % (NAVY2, NAVY)


def star(cx, cy, r, n=8, step=3, rot=-math.pi / 2):
    pts = [(cx + r * math.cos(rot + 2 * math.pi * i / n), cy + r * math.sin(rot + 2 * math.pi * i / n)) for i in range(n)]
    d = ""
    for i in range(n):
        a, b = pts[i], pts[(i + step) % n]
        d += f"M{a[0]:.1f},{a[1]:.1f} L{b[0]:.1f},{b[1]:.1f} "
    return d


def rub_el_hizb(cx, cy, r):
    """two overlapping squares (8-point star) as a single filled outline polygon"""
    pts = []
    for i in range(16):
        ang = -math.pi / 2 + i * math.pi / 8
        rr = r if i % 2 == 0 else r * math.cos(math.pi / 8) / math.cos(math.pi / 8 - math.pi / 8) * 0.765
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"


def emblem(cx, cy, R, monogram=True):
    s = []
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="url(#disc)"/>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="url(#gold)" stroke-width="{R*0.035:.1f}"/>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{R*0.93:.1f}" fill="none" stroke="url(#gold)" stroke-width="{R*0.01:.1f}" opacity="0.8"/>')
    # dotted ring
    for i in range(48):
        a = 2 * math.pi * i / 48
        s.append(f'<circle cx="{cx+R*0.965*math.cos(a):.1f}" cy="{cy+R*0.965*math.sin(a):.1f}" r="{R*0.008:.1f}" fill="#E8C77A"/>')
    # 16-fold rosette lines
    s.append(f'<path d="{star(cx, cy, R*0.88, 16, 5)}" stroke="url(#gold)" stroke-width="{R*0.006:.1f}" fill="none" opacity="0.45"/>')
    # 8-point star (Rub el Hizb)
    s.append(f'<path d="{rub_el_hizb(cx, cy, R*0.80)}" fill="#0A1E29" stroke="url(#gold)" stroke-width="{R*0.022:.1f}" stroke-linejoin="round"/>')
    s.append(f'<path d="{rub_el_hizb(cx, cy, R*0.72)}" fill="none" stroke="url(#gold)" stroke-width="{R*0.008:.1f}" opacity="0.7"/>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{R*0.52:.1f}" fill="none" stroke="url(#gold)" stroke-width="{R*0.008:.1f}" opacity="0.7"/>')
    if monogram:
        # name in Nastaliq inside the star
        s.append(f'<text x="{cx}" y="{cy - R*0.02:.1f}" font-family="Noto Nastaliq Urdu" font-size="{R*0.23:.1f}" fill="url(#gold)" '
                 f'text-anchor="middle" direction="rtl">ذبیح اللہ</text>')
        s.append(f'<text x="{cx}" y="{cy + R*0.32:.1f}" font-family="Noto Nastaliq Urdu" font-size="{R*0.19:.1f}" fill="#F3E6C4" '
                 f'text-anchor="middle" direction="rtl">لغاری</text>')
    return "\n".join(s)


def svg(w, h, body, bg=True):
    back = f'<rect width="{w}" height="{h}" fill="url(#bg)"/>' if bg else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{DEFS}{back}\n{body}\n</svg>')


def diamond_rule(cx, y, half, size):
    return (f'<rect x="{cx-half}" y="{y-1.5}" width="{2*half}" height="3" fill="url(#goldH)"/>'
            f'<path d="M{cx},{y-size} L{cx+size},{y} L{cx},{y+size} L{cx-size},{y} Z" fill="#E8C77A"/>')


def square(bg=True):
    W = H = 1080
    body = emblem(540, 470, 330)
    body += f'<text x="540" y="935" font-family="Poppins" font-weight="600" font-size="46" letter-spacing="9" fill="url(#gold)" text-anchor="middle">{EN}</text>'
    body += diamond_rule(540, 870, 230, 9)
    return svg(W, H, body, bg)


def horizontal(bg=True):
    W, H = 2400, 760
    body = emblem(390, 380, 300, monogram=False)
    # monogram letter in the star centre
    body += '<text x="390" y="430" font-family="Amiri" font-weight="bold" font-size="210" fill="url(#gold)" text-anchor="middle">ذ</text>'
    tx = 1560
    body += f'<text x="{tx}" y="390" font-family="Noto Nastaliq Urdu" font-weight="bold" font-size="150" fill="url(#gold)" text-anchor="middle" direction="rtl">{UR}</text>'
    body += diamond_rule(tx, 470, 520, 12)
    body += f'<text x="{tx}" y="590" font-family="Poppins" font-weight="600" font-size="78" letter-spacing="14" fill="#F3E6C4" text-anchor="middle">{EN}</text>'
    return svg(W, H, body, bg)


def render(name, content, width=None):
    p = os.path.join(OUT, name + ".svg")
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    png = os.path.join(OUT, name + ".png")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", p, "-frames:v", "1", "-pix_fmt", "rgba", png], check=True)
    return png


os.makedirs(OUT, exist_ok=True)
for n, c in [("logo_square", square(True)), ("logo_square_transparent", square(False)),
             ("logo_horizontal", horizontal(True)), ("logo_horizontal_transparent", horizontal(False)),
             ("logo_emblem_transparent", svg(760, 760, emblem(380, 380, 360), False))]:
    print(render(n, c))
