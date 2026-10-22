"""Short demo: a slice of the green-screen hadith recording placed inside each virtual studio.

  python3 brand/make_studio_demo.py [set ...]  ->  videos/edited/studio_demo_<set>.mp4  (9:16 reel, 1080x1920)
The source was filmed upright on a phone, so the reel crops the studio's centre and the presenter fills the
frame width (the photo edges of his sleeves stay outside the picture).
Background plate → keyed presenter (scaled from the studio camera, eyes on the camera's eye line)
→ desk layer → name strip + Urdu captions. The original voice, cleaned; no music.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SRC = os.path.join(ROOT, "videos", "raw", "dars2.mp4")
PLATES = os.path.join(HERE, "studio", "plates")
FONTS = os.path.join(ROOT, ".claude", "skills", "dai-video-editor", "assets", "fonts")
OUT = os.path.join(ROOT, "videos", "edited")
WORK = os.path.join(ROOT, "videos", "work", "studio_demo")

T0, T1 = 0.40, 11.30                     # "حضرت سہل بن سعد ... ایک شخص کا گزر ہوا"
EYES = ((181, 272), (241, 261))          # pupils in the source frame (480x864), measured with OpenCV
SCREEN = "0x73D737"
GRADE = {   # colour match of the presenter to each room: (r, g, b) gains
    "library": (1.04, 0.99, 0.92), "broadcast": (0.97, 0.99, 1.03), "arches": (1.05, 1.0, 0.93),
    "brand": (1.0, 0.99, 0.97), "manuscript": (1.05, 0.99, 0.92),
}
CAPTIONS = [   # clip-relative times (s); text follows the user's own wording of the hadith narration
    (0.00, 2.62, "حضرت سہل بن سعد رضی اللہ تعالیٰ عنہ"),
    (2.62, 5.42, "آپ صلی اللہ علیہ وسلم کی مجلس کا ایک واقعہ نقل فرماتے ہیں"),
    (5.42, 7.78, "ایک دفعہ آپ صلی اللہ علیہ وسلم مجلس میں تشریف فرما تھے"),
    (7.78, 10.90, "تو مجلس کے پاس سے ایک شخص کا گزر ہوا"),
]


def ts(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def ass(path):
    # Noto Nastaliq's line box is ~3.3x its em: size 64 here ≈ a 34 px Latin caption on 1080p
    lines = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "WrapStyle: 0", "",
             "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
             "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
             "MarginL, MarginR, MarginV, Encoding",
             "Style: Cap,Noto Nastaliq Urdu,104,&H00EAF3F7,&H00EAF3F7,&H00281A0F,&H96000000,1,0,0,0,100,100,0,0,1,2,3,2,70,70,170,1",
             "Style: Name,Noto Nastaliq Urdu,112,&H00EAF3F7,&H00EAF3F7,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,2,7,0,0,0,1",
             "Style: Kick,Noto Nastaliq Urdu,70,&H0057A8D9,&H0057A8D9,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,1,7,0,0,0,1",
             "", "[Events]",
             "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    # name strip, top-left, with a thin gold rule (drawn) — appears for the first 6 s
    lines.append(f"Dialogue: 2,{ts(0.3)},{ts(6.3)},Kick,,0,0,0,,{{\\an5\\pos(540,150)\\fad(400,400)\\bord0\\shad2}}درسِ حدیث")
    lines.append(f"Dialogue: 2,{ts(0.5)},{ts(6.3)},Name,,0,0,0,,{{\\an5\\pos(540,270)\\fad(500,400)\\bord0\\shad3}}ذبیح اللہ لغاری")
    for a, b, t in CAPTIONS:
        lines.append(f"Dialogue: 3,{ts(a)},{ts(b)},Cap,,0,0,0,,{{\\fad(150,150)}}{t}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def key_frames():
    """key the clip frame by frame: alpha from how much green exceeds red/blue (white kurta, black cap and
    skin are untouched), green spill clamped, edges eroded 1 px and softened. Writes RGBA PNGs."""
    import numpy as np
    from PIL import Image, ImageFilter
    kdir = os.path.join(WORK, "keyed")
    if os.path.isdir(kdir) and len(os.listdir(kdir)) > 10:
        return kdir
    os.makedirs(kdir, exist_ok=True)
    w, h = 480, 864
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{T0}", "-t", f"{T1 - T0}", "-i", SRC, "-vf", "fps=30",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    i = 0
    while True:
        buf = p.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        f = np.frombuffer(buf, np.uint8).reshape(h, w, 3).astype(np.float32) / 255
        r, g, b = f[..., 0], f[..., 1], f[..., 2]
        d = g - np.maximum(r, b)                      # green dominance
        a = 1 - np.clip((d - 0.10) / 0.16, 0, 1)      # >0.26 → fully transparent, <0.10 → opaque
        am = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(
            ImageFilter.GaussianBlur(0.8))
        a = np.asarray(am).astype(np.float32) / 255
        g2 = np.minimum(g, np.maximum(r, b) + 0.02)   # spill suppression
        rgba = np.dstack([r, g2, b, a])
        Image.fromarray((np.clip(rgba, 0, 1) * 255).astype(np.uint8), "RGBA").save(
            os.path.join(kdir, f"f{i:05d}.png"), compress_level=1)
        i += 1
    p.wait()
    return kdir


def esc(p):
    return p.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def render(name):
    meta = json.load(open(os.path.join(PLATES, f"{name}_v_meta.json")))
    (x1, y1), (x2, y2) = EYES
    iod = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    s = max(meta["ppm"] * 0.063 / iod, 1104 / 480)     # studio scale, but never narrower than the reel
    sw, sh = int(480 * s) // 2 * 2, int(864 * s) // 2 * 2
    ex, ey = (x1 + x2) / 2 * s, (y1 + y2) / 2 * s
    ox, oy = int(540 - ex), int(meta["eye_y"] - ey)
    r, g, b = GRADE[name]
    dur = T1 - T0
    os.makedirs(WORK, exist_ok=True)
    kdir = key_frames()
    sub = os.path.join(WORK, "captions.ass")
    ass(sub)
    out = os.path.join(OUT, f"studio_demo_{name}.mp4")
    fc = (
        f"[0:v]scale=1080:1920,format=rgb24[bg];"
        f"[3:v]scale={sw}:{sh}:flags=lanczos,format=rgba,"
        f"colorchannelmixer=rr={r}:gg={g}:bb={b}[pk];"
        f"[bg][pk]overlay=x={ox}:y={oy}:shortest=0:eof_action=pass[b1];"
        # dark band at the bottom so the captions read over the hands
        f"color=c=0x08162A:s=1080x700:r=30:d={dur},format=rgba,geq=r='8':g='22':b='42':a='235*pow(Y/H,1.3)'[band];"
        f"[b1][band]overlay=0:1220[b2];"
        f"[b2]ass=filename='{esc(sub)}':fontsdir='{esc(FONTS)}':shaping=complex,"
        f"vignette=angle=PI/6:mode=forward,fade=t=in:d=0.4,fade=t=out:st={dur - 0.5}:d=0.5,format=yuv420p[v];"
        f"[2:a]atrim={T0}:{T1},asetpts=PTS-STARTPTS,highpass=f=80,"
        f"afftdn=nf=-25,loudnorm=I=-16:TP=-1.5,afade=t=in:d=0.2,afade=t=out:st={dur - 0.4}:d=0.4[a]"
    )
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-loop", "1", "-framerate", "30", "-t", f"{dur}", "-i", os.path.join(PLATES, f"{name}_v_bg.png"),
           "-f", "lavfi", "-t", "1", "-i", "nullsrc",
           "-i", SRC, "-framerate", "30", "-i", os.path.join(kdir, "f%05d.png"), "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", f"{dur}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    print(out)
    return out


if __name__ == "__main__":
    for n in sys.argv[1:] or ["library", "broadcast", "arches", "brand", "manuscript"]:
        render(n)
