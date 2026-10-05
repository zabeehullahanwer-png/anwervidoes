#!/usr/bin/env python3
"""Dai Studio — professional video editor for Islamic content.

Turns a raw talking-head recording into a finished, studio-looking video:
silence/mistake cuts, punch-in zooms, cleaned + loudness-normalised audio,
colour grade, animated Islamic-geometric background, speaker card, captions
(Urdu Nastaliq / Arabic / Hindi / English) with word highlight, hadith / ayah
cards, lower-thirds, keyword pops, intro + outro, watermark and progress bar.

Only needs ffmpeg (with libass) and Python 3.8+. Transcription optionally uses
faster-whisper.

Commands
  doctor                      check ffmpeg / fonts / whisper
  analyze   RAW               probe, silence map, loudness, contact sheets
  transcribe RAW              word-level transcript (faster-whisper)
  autoplan  RAW               draft edit_plan.json (cuts, zooms, captions, titles)
  preview   PLAN [--at ...]   fast still preview of titles/captions/layout (seconds, not minutes)
  render    PLAN [--draft]    render the final video from an edit plan
  frames    VIDEO --at ...    export still frames for visual QA
  background --style S        render a 10 s preview of a style's background
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import graphics  # noqa: E402
from ass_builder import AssDoc  # noqa: E402

FONTS_DIR = os.path.join(SKILL, "assets", "fonts")
STYLES = os.path.join(SKILL, "presets", "styles.json")
FPS = 30
FORMATS = {"reel": (1080, 1920), "youtube": (1920, 1080), "square": (1080, 1080)}

GRADES = {
    "none": "",
    "neutral": "eq=contrast=1.04:saturation=1.04,unsharp=5:5:0.30",
    "warm": "eq=contrast=1.06:brightness=0.008:saturation=1.08,"
            "colorbalance=rs=0.025:bs=-0.03:rm=0.02:bm=-0.02:rh=0.01:bh=-0.015,unsharp=5:5:0.35",
    "cinematic": "eq=contrast=1.09:saturation=1.06:gamma=0.98,"
                 "colorbalance=rs=-0.02:bs=0.035:rh=0.03:bh=-0.03,unsharp=5:5:0.40",
}

DENOISE = {
    "off": "",
    "light": "afftdn=nr=8:nf=-45",
    "medium": "afftdn=nr=12:nf=-40",
    "strong": "afftdn=nr=20:nf=-35,afftdn=nr=8:nf=-40",
}


# ---------------------------------------------------------------------------
# utilities
# ---------------------------------------------------------------------------

def log(*a):
    print("[dai]", *a, file=sys.stderr, flush=True)


def run(cmd, quiet=True):
    if not quiet:
        log(" ".join(cmd))
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        sys.stderr.write(p.stderr[-4000:])
        raise SystemExit(f"command failed: {cmd[0]} (exit {p.returncode})")
    return p


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def workdir_for(video, root=None):
    stem = os.path.splitext(os.path.basename(video))[0]
    root = root or os.path.join(os.getcwd(), "videos", "work")
    d = os.path.join(root, stem)
    os.makedirs(d, exist_ok=True)
    return d


def find_brand(explicit=None):
    cands = [explicit] if explicit else []
    cands += [os.path.join(os.getcwd(), "dai-brand.json")]  # never fall back to the example (placeholder names)
    for c in cands:
        if c and os.path.exists(c):
            return load_json(c), c
    return {}, None


def probe(path):
    p = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path])
    info = json.loads(p.stdout)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    if not v:
        raise SystemExit("no video stream in " + path)
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    if "rotate" in (v.get("tags") or {}):
        rot = int(v["tags"]["rotate"])
    if abs(rot) % 180 == 90:
        w, h = h, w
    num, den = (v.get("avg_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    return {
        "width": w, "height": h, "fps": round(fps, 3), "rotation": rot,
        "duration": float(info["format"].get("duration", 0)),
        "has_audio": a is not None,
        "audio_rate": int(a["sample_rate"]) if a else None,
        "audio_channels": int(a["channels"]) if a else None,
        "vcodec": v.get("codec_name"),
    }


def silences(path, noise_db=-35, min_d=0.45):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn",
                        "-af", f"highpass=f=100,silencedetect=noise={noise_db}dB:d={min_d}",
                        "-f", "null", "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, cur = [], None
    for line in p.stderr.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", line)
        if m:
            cur = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and cur is not None:
            out.append([round(cur, 3), round(float(m.group(1)), 3)])
            cur = None
    if cur is not None:
        out.append([round(cur, 3), None])
    return out


def loudness(path):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn",
                        "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, re.S)
    if not m:
        return {}
    j = json.loads(m.group(0))
    return {"integrated_lufs": float(j["input_i"]), "true_peak": float(j["input_tp"]),
            "lra": float(j["input_lra"]), "noise_floor_hint": float(j["input_thresh"])}


def q(t, fps=FPS):
    """quantise a time to the output frame grid (keeps A/V in sync over many cuts)"""
    return round(round(t * fps) / fps, 4)


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------

def cmd_doctor(_a):
    ok = True
    for tool in ("ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        print(f"{tool:12s} {'OK  ' + path if path else 'MISSING'}")
        ok &= bool(path)
    if shutil.which("ffmpeg"):
        bc = run(["ffmpeg", "-hide_banner", "-buildconf"]).stdout
        for lib in ("libass", "libfreetype", "libfribidi", "libharfbuzz", "libx264"):
            has = ("--enable-" + lib) in bc
            print(f"{lib:12s} {'OK' if has else 'MISSING (needed)' if lib in ('libass', 'libx264') else 'missing'}")
            if lib in ("libass", "libx264"):
                ok &= has
    fonts = sorted(f for f in os.listdir(FONTS_DIR) if f.endswith(".ttf"))
    print("fonts       ", ", ".join(fonts))
    try:
        import faster_whisper  # noqa: F401
        print("whisper      OK (faster-whisper)")
    except Exception:
        print("whisper      not installed -> `pip install faster-whisper` for automatic captions")
    brand, bp = find_brand()
    print("brand       ", bp or "none (copy brand.example.json to ./dai-brand.json)")
    print("READY" if ok else "NOT READY")


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------

def cmd_analyze(a):
    work = a.work or workdir_for(a.video)
    info = probe(a.video)
    log("probe:", info)
    sil = silences(a.video, a.noise, a.min_silence) if info["has_audio"] else []
    loud = loudness(a.video) if info["has_audio"] else {}
    dur = info["duration"]
    # contact sheets: 1 frame every N seconds, 4x4 tiles, so Claude can *see* the footage
    every = max(1.0, dur / 48.0)
    sheet = os.path.join(work, "contact_%02d.jpg")
    run(["ffmpeg", "-y", "-v", "error", "-i", a.video, "-vf",
         f"fps=1/{every:.3f},scale=320:-2,drawtext=fontfile={os.path.join(FONTS_DIR, 'Poppins-SemiBold.ttf')}:"
         f"text='%{{pts\\:hms}}':x=6:y=6:fontsize=18:fontcolor=white:box=1:boxcolor=black@0.6,tile=4x4",
         "-vsync", "vfr", "-q:v", "4", sheet])
    sheets = sorted(os.path.join(work, f) for f in os.listdir(work) if f.startswith("contact_"))
    speech = dur - sum(((e if e is not None else dur) - s) for s, e in sil)
    res = {"source": os.path.abspath(a.video), "info": info, "loudness": loud, "silences": sil,
           "speech_seconds": round(speech, 2), "contact_sheets": sheets, "contact_every_s": round(every, 2)}
    out = os.path.join(work, "analysis.json")
    save_json(out, res)
    print(json.dumps({"analysis": out, "duration": dur, "speech_seconds": round(speech, 1),
                      "silences": len(sil), "loudness": loud, "contact_sheets": sheets,
                      "resolution": f"{info['width']}x{info['height']}", "fps": info["fps"]},
                     ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# transcribe
# ---------------------------------------------------------------------------

def cmd_transcribe(a):
    work = a.work or workdir_for(a.video)
    try:
        from faster_whisper import WhisperModel
    except Exception:
        raise SystemExit("faster-whisper is not installed. Run:  pip install faster-whisper\n"
                         "(first run downloads the model from huggingface.co). Or provide a transcript.json.")
    wav = os.path.join(work, "speech16k.wav")
    run(["ffmpeg", "-y", "-v", "error", "-i", a.video, "-vn", "-ac", "1", "-ar", "16000",
         "-af", "highpass=f=80,afftdn=nr=10", wav])
    log(f"loading whisper model '{a.model}' ...")
    model = WhisperModel(a.model, device=a.device, compute_type="int8" if a.device == "cpu" else "float16")
    prompt = a.prompt or ("بسم اللہ الرحمن الرحیم۔ حدیث، قرآن، رسول اللہ صلی اللہ علیہ وسلم، صحابہ کرام، "
                          "اللہ تعالیٰ، نماز، روزہ، زکوٰۃ۔")
    segs, info = model.transcribe(wav, language=None if a.lang == "auto" else a.lang, word_timestamps=True,
                                  vad_filter=True, beam_size=5, initial_prompt=prompt)
    out = {"language": info.language, "segments": []}
    for s in segs:
        out["segments"].append({
            "start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip(),
            "words": [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3),
                       "p": round(w.probability, 3)} for w in (s.words or [])],
        })
        log(f"{s.start:7.2f}-{s.end:7.2f} {s.text.strip()}")
    path = os.path.join(work, "transcript.json")
    save_json(path, out)
    # human/Claude readable version
    with open(os.path.join(work, "transcript.txt"), "w", encoding="utf-8") as f:
        for i, s in enumerate(out["segments"]):
            f.write(f"[{i:03d}] {s['start']:8.2f} → {s['end']:8.2f} | {s['text']}\n")
    print(path)


# ---------------------------------------------------------------------------
# autoplan
# ---------------------------------------------------------------------------

def speech_segments(dur, sil, pad_in=0.10, pad_out=0.20, merge_gap=0.30, min_len=0.35):
    keep, t = [], 0.0
    for s, e in sil:
        e = dur if e is None else e
        if s > t:
            keep.append([t, s])
        t = e
    if t < dur:
        keep.append([t, dur])
    padded = [[max(0, s - pad_in), min(dur, e + pad_out)] for s, e in keep]
    merged = []
    for s, e in padded:
        if merged and s - merged[-1][1] < merge_gap:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [[round(s, 3), round(e, 3)] for s, e in merged if e - s >= min_len]


def chunk_words(words, max_words, max_s):
    chunks, cur = [], []
    for w in words:
        if not w["w"].strip():
            continue
        if cur and (len(cur) >= max_words or w["e"] - cur[0]["s"] > max_s or w["s"] - cur[-1]["e"] > 0.6):
            chunks.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.!?؟۔،,]$", w["w"].strip()) and len(cur) >= 2:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return [{"start": c[0]["s"], "end": c[-1]["e"], "text": " ".join(x["w"].strip() for x in c),
             "words": [{"w": x["w"].strip(), "s": x["s"], "e": x["e"]} for x in c]} for c in chunks]


def cmd_autoplan(a):
    work = a.work or workdir_for(a.video)
    styles = load_json(STYLES)
    brand, _ = find_brand(a.brand)
    a.style = a.style or brand.get("style") or "jtr-cinematic"
    a.lang = a.lang or brand.get("language") or "ur"
    if a.style not in styles:
        raise SystemExit(f"unknown style '{a.style}'. choose: {', '.join(styles)}")
    style = styles[a.style]
    an_path = os.path.join(work, "analysis.json")
    if not os.path.exists(an_path):
        cmd_analyze(argparse.Namespace(video=a.video, work=work, noise=a.noise, min_silence=a.min_silence))
    an = load_json(an_path)
    info = an["info"]
    dur = info["duration"]
    segs = speech_segments(dur, an["silences"]) if info["has_audio"] else [[0, dur]]
    if not segs:
        segs = [[0, dur]]
    cycle = style["zoom_cycle"]
    seg_objs = []
    for i, (s, e) in enumerate(segs):
        seg_objs.append({"start": s, "end": e, "zoom": cycle[i % len(cycle)], "focus": [0.5, 0.40]})
    landscape = info["width"] > info["height"]
    fmt = a.format
    layout = a.layout or ("frame" if fmt == "reel" and landscape else "fill")
    plan = {
        "source": os.path.abspath(a.video),
        "output": os.path.abspath(a.output or os.path.join(os.getcwd(), "videos", "edited",
                                                           os.path.splitext(os.path.basename(a.video))[0]
                                                           + f"_{fmt}.mp4")),
        "format": fmt,
        "layout": layout,
        "card_aspect": "1:1" if landscape else "4:5",
        "style": a.style,
        "language": a.lang,
        "grade": style["grade"],
        "segments": seg_objs,
        "headline": {"text": "", "kicker": brand.get("series", "")} if layout == "frame" else None,
        "captions": {"enabled": True, "items": []},
        "overlays": [],
        "intro": {"enabled": True, "duration": 2.8,
                  "top_text": brand.get("intro_arabic", "بِسْمِ اللّٰهِ الرَّحْمٰنِ الرَّحِيْمِ"),
                  "name": brand.get("name", ""), "subtitle": brand.get("title", "")},
        "outro": {"enabled": True, "duration": 4.0, "name": brand.get("name", ""),
                  "cta": brand.get("cta", "Subscribe • Share — صدقہ جاریہ"),
                  "handle": brand.get("handle", "")},
        "watermark": {"enabled": bool(brand.get("handle") or brand.get("logo")),
                      "text": brand.get("handle", ""), "logo": brand.get("logo", "")},
        "progress_bar": style.get("progress_bar", False),
        "audio": {"denoise": "medium", "loudness": -14, "music": brand.get("music", ""),
                  "music_volume": 0.07, "whoosh": False},
    }
    if brand.get("name"):
        plan["overlays"].append({"type": "lower_third", "at": round(segs[0][0] + 1.5, 2), "duration": 5.0,
                                 "name": brand["name"], "title": brand.get("title", "")})
    tpath = a.transcript or os.path.join(work, "transcript.json")
    if os.path.exists(tpath):
        tr = load_json(tpath)
        words = [w for s in tr["segments"] for w in s.get("words", [])]
        if words:
            cap = style["captions"]
            plan["captions"]["items"] = chunk_words(words, cap["max_words"], cap["max_seconds"])
        else:
            plan["captions"]["items"] = [{"start": s["start"], "end": s["end"], "text": s["text"]}
                                         for s in tr["segments"]]
    else:
        plan["captions"]["enabled"] = False
        log("no transcript.json -> captions disabled in draft plan (run `transcribe` or add items by hand)")
    out = a.plan or os.path.join(work, "edit_plan.json")
    save_json(out, plan)
    kept = sum(e - s for s, e in segs)
    print(json.dumps({"plan": out, "segments": len(segs), "kept_seconds": round(kept, 1),
                      "removed_seconds": round(dur - kept, 1), "layout": layout, "format": fmt,
                      "captions": len(plan["captions"]["items"])}, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

class Timeline:
    """Maps source-video time -> output time through the kept segments."""

    def __init__(self, segs, offset):
        self.segs = segs
        self.offset = offset
        self.starts = []
        acc = 0.0
        for s in segs:
            self.starts.append(acc)
            acc += s["end"] - s["start"]
        self.content = acc

    def map(self, t, side="start"):
        for s, o in zip(self.segs, self.starts):
            if s["start"] <= t <= s["end"]:
                return self.offset + o + (t - s["start"])
            if t < s["start"]:
                # t is inside a removed gap
                if side == "start":
                    return self.offset + o
                return self.offset + o  # end snaps to the cut point
        return self.offset + self.content

    def span(self, a, b):
        return self.map(a, "start"), self.map(b, "end")


def even(x):
    x = int(round(x))
    return x - (x % 2)


def parse_aspect(s):
    a, b = s.split(":")
    return float(a) / float(b)


def layer_geometry(plan, W, H, src_w, src_h):
    """Where the speaker goes on the canvas."""
    if plan["layout"] == "fill":
        return {"x": 0, "y": 0, "w": W, "h": H, "card": False}
    asp = parse_aspect(plan.get("card_aspect") or f"{src_w}:{src_h}")
    if H > W:  # vertical reel
        cw = even(W * 0.89)
        ch = even(cw / asp)
        max_h = H * 0.56
        if ch > max_h:
            ch = even(max_h)
            cw = even(ch * asp)
        y = even(H * 0.235)
    else:
        ch = even(H * 0.78)
        cw = even(ch * asp)
        if cw > W * 0.86:
            cw = even(W * 0.86)
            ch = even(cw / asp)
        y = even((H - ch) / 2 - H * 0.03)
    return {"x": even((W - cw) / 2), "y": y, "w": cw, "h": ch, "card": True}


def segment_filters(seg, src_w, src_h, lw, lh, grade, nframes):
    target = lw / lh
    if src_w / src_h > target:
        ch_ = src_h
        cw_ = src_h * target
    else:
        cw_ = src_w
        ch_ = src_w / target
    z = max(1.0, float(seg.get("zoom", 1.0)))
    cw_, ch_ = cw_ / z, ch_ / z
    fx, fy = seg.get("focus", [0.5, 0.42])
    x = min(max(0, fx * src_w - cw_ / 2), src_w - cw_)
    y = min(max(0, fy * src_h - ch_ / 2), src_h - ch_)
    f = [f"crop={even(cw_)}:{even(ch_)}:{even(x)}:{even(y)}"]
    if seg.get("motion") == "push":
        amt = float(seg.get("push", 0.06))
        f.append(f"scale={lw * 2}:{lh * 2}:flags=lanczos")
        f.append(f"zoompan=z='1+{amt}*on/{max(1, nframes)}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                 f":d=1:s={lw}x{lh}:fps={FPS}")
    else:
        f.append(f"scale={lw}:{lh}:flags=lanczos")
    f += ["setsar=1", f"fps={FPS}"]
    if GRADES.get(grade):
        f.append(GRADES[grade])
    f.append("format=yuv420p")
    return ",".join(f)


def cut_segments(plan, info, geo, work, draft):
    """Render each kept segment (zoom + grade) then concat -> speaker.mkv"""
    segdir = os.path.join(work, "segments")
    if os.path.isdir(segdir):
        shutil.rmtree(segdir)
    os.makedirs(segdir)
    lst = []
    src = plan["source"]
    for i, seg in enumerate(plan["segments"]):
        s, e = q(seg["start"]), q(seg["end"])
        seg["start"], seg["end"] = s, e
        d = round(e - s, 4)
        if d <= 0:
            continue
        nfr = int(round(d * FPS))
        vf = segment_filters(seg, info["width"], info["height"], geo["w"], geo["h"], plan.get("grade", "warm"), nfr)
        out = os.path.join(segdir, f"seg_{i:04d}.mkv")
        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{s:.4f}", "-i", src]
        if info["has_audio"]:
            fade = min(0.02, d / 4)
            af = f"aresample=48000,afade=t=in:d={fade:.3f},afade=t=out:st={d - fade:.4f}:d={fade:.3f}"
            cmd += ["-t", f"{d:.4f}", "-vf", vf, "-af", af, "-map", "0:v:0", "-map", "0:a:0"]
        else:  # silent source: add a silent track so the rest of the pipeline is uniform
            cmd += ["-f", "lavfi", "-t", f"{d:.4f}", "-i", "anullsrc=r=48000:cl=mono",
                    "-t", f"{d:.4f}", "-vf", vf, "-map", "0:v:0", "-map", "1:a:0"]
        cmd += ["-ac", "1", "-c:a", "pcm_s16le",
                "-c:v", "libx264", "-preset", "ultrafast" if draft else "veryfast", "-crf", "20" if draft else "12",
                out]
        run(cmd)
        lst.append(out)
        log(f"segment {i + 1}/{len(plan['segments'])}  {s:.2f}-{e:.2f}  zoom {seg.get('zoom', 1)}")
    listfile = os.path.join(segdir, "list.txt")
    with open(listfile, "w") as f:
        for p in lst:
            f.write(f"file '{p}'\n")
    speaker = os.path.join(work, "speaker.mkv")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", speaker])
    return speaker


def build_ass(plan, style, W, H, geo, tl, intro_d, outro_d, total, ass_path, brand):
    doc = AssDoc(W, H, style, plan.get("language", "ur"))
    cx = W // 2
    content0, content1 = tl.offset, tl.offset + tl.content
    on_bg = style.get("on_background_text", style["text"])
    # caption baseline
    if geo["card"] and H > W:
        cap_y = int(geo["y"] + geo["h"] + H * 0.115)
        if cap_y > H * 0.93:
            cap_y = int(H * 0.93)
    elif geo["card"]:
        cap_y = int(H * 0.965)
    else:
        cap_y = int(H * (0.80 if H > W else 0.92))
    # intro / outro
    if intro_d > 0:
        it = plan["intro"]
        doc.intro(0.15, intro_d + 0.25, it.get("top_text", ""), it.get("name", ""), it.get("subtitle", ""), on_bg)
    if outro_d > 0:
        ot = plan["outro"]
        doc.outro(content1 + 0.2, total, ot.get("name", ""), ot.get("cta", ""), ot.get("handle", ""), on_bg)
    # headline above the card
    hl = plan.get("headline") or {}
    if geo["card"] and hl.get("text") and H > W:
        doc.headline(content0 + 0.2, content1, hl["text"], cx, int(geo["y"] * 0.55), W * 0.86, hl.get("kicker", ""))
    # captions
    cap = plan.get("captions") or {}
    if cap.get("enabled", True):
        # suppress captions while a quote card covers the screen
        blocks = [tl.span(o["start"], o["end"]) for o in plan.get("overlays", [])
                  if o.get("type") == "quote_card" and o.get("hide_captions", True)]
        chunks = []
        for c in cap.get("items", []):
            t0, t1 = tl.span(c["start"], c["end"])
            if t1 - t0 < 0.15 or any(b0 - 0.05 <= t0 < b1 for b0, b1 in blocks):
                continue
            nc = {"start": t0, "end": t1, "text": c["text"]}
            if c.get("words"):
                nc["words"] = [{"w": w["w"], "s": tl.map(w["s"]), "e": tl.map(w["e"], "end")} for w in c["words"]]
            chunks.append(nc)
        # avoid overlaps between consecutive chunks
        for i in range(len(chunks) - 1):
            if chunks[i]["end"] > chunks[i + 1]["start"]:
                chunks[i]["end"] = chunks[i + 1]["start"]
        doc.captions(chunks, cap_y)
    # overlays
    cards = [tl.span(o["start"], o["end"]) for o in plan.get("overlays", []) if o.get("type") == "quote_card"]
    for o in plan.get("overlays", []):
        typ = o.get("type")
        if typ == "lower_third":
            t0 = tl.map(o["at"])
            t1 = min(content1, t0 + float(o.get("duration", 5)))
            for b0, b1 in cards:
                if t0 < b0 < t1:
                    t1 = b0
                elif b0 <= t0 < b1:
                    t0 = t1  # starts under a card -> drop
            rtl = any("؀" <= ch <= "ۿ" for ch in o.get("name", ""))
            if geo["card"]:
                y = int(geo["y"] + geo["h"] * 0.70)
                x = geo["x"] + geo["w"] - int(W * 0.03) if rtl else geo["x"] + int(W * 0.03)
                mw = geo["w"] * 0.9
            else:
                y = int(H * (0.62 if H > W else 0.72))
                x = W - int(W * 0.06) if rtl else int(W * 0.06)
                mw = W * 0.8
            doc.lower_third(t0, t1, o.get("name", ""), o.get("title", ""), x, y, mw)
        elif typ == "quote_card":
            t0, t1 = tl.span(o["start"], o["end"])
            mode = o.get("mode", "fullscreen")
            doc.quote_card(t0, t1, o.get("arabic", ""), o.get("translation", ""), o.get("reference", ""),
                           o.get("label", ""), mode=mode, on_background=(mode == "fullscreen"))
        elif typ == "keyword":
            t0, t1 = tl.span(o["start"], o["end"])
            if geo["card"]:
                ky = int(geo["y"] + geo["h"] * 0.18)
            else:
                ky = int(H * (0.30 if H > W else 0.22))
            doc.keyword(t0, t1, o["text"], cx, ky)
        elif typ == "text":
            t0, t1 = tl.span(o["start"], o["end"])
            doc.headline(t0, t1, o["text"], cx, int(H * float(o.get("y", 0.15))), W * 0.86, o.get("kicker", ""))
    # watermark / progress
    wm = plan.get("watermark") or {}
    if wm.get("enabled") and wm.get("text") and not wm.get("logo"):
        doc.watermark(content0 + 0.5, content1, wm["text"])
    if plan.get("progress_bar"):
        doc.progress_bar(content0, content1)
    doc.write(ass_path)


def clean_voice(speaker, work, au):
    """highpass -> denoise -> de-ess -> compress, then linear two-pass loudnorm. Returns a WAV path."""
    chain = ["highpass=f=75", "lowpass=f=15000"]
    dn = DENOISE.get(au.get("denoise", "medium"), "")
    if dn:
        chain.append(dn)
    chain += ["deesser=i=0.35", "acompressor=threshold=-20dB:ratio=3:attack=8:release=180:makeup=2"]
    pre = ",".join(chain)
    target = float(au.get("loudness", -14))
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", speaker, "-vn", "-af",
                        pre + f",loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, re.S)
    ln = f"loudnorm=I={target}:TP=-1.5:LRA=11"
    if m:
        j = json.loads(m.group(0))
        if j["input_i"] not in ("-inf", "inf"):
            ln += (f":measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
                   f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    out = os.path.join(work, "voice_clean.wav")
    run(["ffmpeg", "-y", "-v", "error", "-i", speaker, "-vn", "-af", pre + "," + ln + ",aresample=48000",
         "-ac", "1", "-c:a", "pcm_s16le", out])
    return out


def fullscreen_windows(plan, tl):
    wins = []
    for o in plan.get("overlays", []):
        if o.get("type") == "quote_card" and o.get("mode", "fullscreen") == "fullscreen":
            a, b = tl.span(o["start"], o["end"])
            if b - a > 0.4:
                wins.append((a, b))
    return wins


def cmd_render(a):
    plan = load_json(a.plan)
    styles = load_json(STYLES)
    style = styles[plan.get("style", "jtr-cinematic")]
    brand, _ = find_brand(a.brand)
    W, H = FORMATS[plan.get("format", "reel")]
    info = probe(plan["source"])
    work = a.work or workdir_for(plan["source"])
    geo = layer_geometry(plan, W, H, info["width"], info["height"])
    log("canvas", W, H, "speaker layer", geo)
    if not plan.get("segments"):
        plan["segments"] = [{"start": 0, "end": info["duration"]}]
    plan["segments"].sort(key=lambda s: s["start"])

    speaker = cut_segments(plan, info, geo, work, a.draft)
    intro_d = float(plan["intro"]["duration"]) if (plan.get("intro") or {}).get("enabled") else 0.0
    outro_d = float(plan["outro"]["duration"]) if (plan.get("outro") or {}).get("enabled") else 0.0
    tl = Timeline(plan["segments"], intro_d)
    C = tl.content
    T = intro_d + C + outro_d
    c0, c1 = intro_d, intro_d + C

    ass_path = os.path.join(work, "overlays.ass")
    build_ass(plan, style, W, H, geo, tl, intro_d, outro_d, T, ass_path, brand)

    # ---- graphics assets
    bg = style["background"]
    pat, tile, par = graphics.ensure_background_assets(work, W, H, style)
    inputs = ["-i", speaker,
              "-loop", "1", "-framerate", str(FPS), "-t", f"{T:.3f}", "-i", pat,
              "-loop", "1", "-framerate", str(FPS), "-t", f"{T:.3f}", "-i", par]
    idx = 3
    fc = []
    cols = bg["colors"]
    gtype = bg.get("type", "radial")
    fc.append(f"gradients=s={W}x{H}:r={FPS}:d={T:.3f}:n={len(cols)}:"
              + ":".join(f"c{i}={c.replace('#', '0x')}" for i, c in enumerate(cols))
              + f":speed={bg.get('speed', 0.005)}:type={gtype}:seed=11,format=yuv420p[g0]")
    dx, dy = bg.get("pattern_drift", [6, 3])
    po = bg.get("pattern_opacity", 0.1)
    fc.append(f"[1:v]format=gray,crop={W}:{H}:x='mod(t*{dx},{tile})':y='mod(t*{dy},{tile})',"
              f"lut=y='val*{po:.3f}'[pm]")
    fc.append(f"color=c={bg['pattern_color'].replace('#', '0x')}:s={W}x{H}:r={FPS}:d={T:.3f},format=yuva420p[pc]")
    fc.append("[pc][pm]alphamerge[pl]")
    fc.append("[g0][pl]overlay=format=auto:shortest=1[g1]")
    last = "g1"
    if bg.get("particles", 0) > 0 and bg.get("particle_opacity", 0) > 0:
        sp = bg.get("particle_speed", 14)
        fc.append(f"[2:v]format=gray,crop={W}:{H}:x=0:y='{H}-mod(t*{sp},{H})',"
                  f"lut=y='val*{bg['particle_opacity']:.3f}'[qm]")
        fc.append(f"color=c={bg['particle_color'].replace('#', '0x')}:s={W}x{H}:r={FPS}:d={T:.3f},format=yuva420p[qc]")
        fc.append("[qc][qm]alphamerge[ql]")
        fc.append(f"[{last}][ql]overlay=format=auto:shortest=1[g2]")
        last = "g2"
    if bg.get("vignette"):
        fc.append(f"[{last}]vignette=angle=PI/4.5[g3]")
        last = "g3"
    wins = fullscreen_windows(plan, tl)
    n_bg = 1 + len(wins)
    if n_bg > 1:
        fc.append(f"[{last}]split={n_bg}[bgm]" + "".join(f"[bgc{i}]" for i in range(len(wins))))
    else:
        fc.append(f"[{last}]null[bgm]")
    base = "bgm"

    # ---- speaker layer
    fade_d = 0.45
    sp = (f"[0:v]setpts=PTS-STARTPTS+{c0:.4f}/TB,format=yuva420p")
    if geo["card"]:
        r = int(style.get("card_radius", 28) * W / 1080)
        mpath = os.path.join(work, f"cardmask_{geo['w']}x{geo['h']}_{r}.pgm")
        if not os.path.exists(mpath):
            graphics.write_pgm(mpath, geo["w"], geo["h"], graphics.rounded_mask(geo["w"], geo["h"], r))
        pad = int(60 * W / 1080)
        bpx = int(style.get("card_border", 4) * W / 1080)
        ppath = os.path.join(work, f"plate_{geo['w']}x{geo['h']}_{r}_{bpx}_{style['accent'][1:]}.pam")
        if not os.path.exists(ppath):
            log("drawing card plate ...")
            pw, ph, pdata = graphics.card_plate(geo["w"], geo["h"], r, pad, bpx, style["accent"])
            graphics.write_pam_rgba(ppath, pw, ph, pdata)
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{T:.3f}", "-i", mpath,
                   "-loop", "1", "-framerate", str(FPS), "-t", f"{T:.3f}", "-i", ppath]
        mi, pi = idx, idx + 1
        idx += 2
        fc.append(f"[{mi}:v]format=gray,trim=0:{C:.4f},setpts=PTS-STARTPTS+{c0:.4f}/TB[cm]")
        fc.append(sp + "[spv]")
        fc.append("[spv][cm]alphamerge,"
                  f"fade=t=in:st={c0:.3f}:d={fade_d}:alpha=1,fade=t=out:st={c1 - fade_d:.3f}:d={fade_d}:alpha=1[spk]")
        fc.append(f"[{pi}:v]format=yuva420p,trim=0:{C:.4f},setpts=PTS-STARTPTS+{c0:.4f}/TB,"
                  f"fade=t=in:st={c0:.3f}:d={fade_d}:alpha=1,fade=t=out:st={c1 - fade_d:.3f}:d={fade_d}:alpha=1[plt]")
        fc.append(f"[{base}][plt]overlay=x={geo['x'] - pad}:y={geo['y'] - pad}:eof_action=pass:format=auto[b1]")
        fc.append(f"[b1][spk]overlay=x={geo['x']}:y={geo['y']}:eof_action=pass:format=auto[b2]")
    else:
        fc.append(sp + f",fade=t=in:st={c0:.3f}:d={fade_d}:alpha=1,"
                       f"fade=t=out:st={c1 - fade_d:.3f}:d={fade_d}:alpha=1[spk]")
        fc.append(f"[{base}][spk]overlay=0:0:eof_action=pass:format=auto[b2]")
    cur = "b2"

    # ---- full-screen background cut-aways for quote cards
    for i, (wa, wb) in enumerate(wins):
        fd = min(0.45, (wb - wa) / 3)
        fc.append(f"[bgc{i}]trim=start={wa:.3f}:end={wb:.3f},format=yuva420p,"
                  f"fade=t=in:st={wa:.3f}:d={fd:.3f}:alpha=1,fade=t=out:st={wb - fd:.3f}:d={fd:.3f}:alpha=1[cw{i}]")
        fc.append(f"[{cur}][cw{i}]overlay=eof_action=pass:format=auto[cv{i}]")
        cur = f"cv{i}"

    # ---- b-roll (user images / clips), full-screen
    for j, o in enumerate(o for o in plan.get("overlays", []) if o.get("type") == "broll"):
        ba, bb = tl.span(o["start"], o["end"])
        d = bb - ba
        if d < 0.3 or not os.path.exists(o["file"]):
            log("skip broll", o.get("file"))
            continue
        is_img = os.path.splitext(o["file"])[1].lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp")
        if is_img:
            inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{d:.3f}", "-i", o["file"]]
            kb = 1.12
            fc.append(f"[{idx}:v]scale={int(W * kb)}:{int(H * kb)}:force_original_aspect_ratio=increase,"
                      f"crop={W}:{H}:x='(iw-{W})*t/{d:.3f}':y='(ih-{H})/2',setsar=1,fps={FPS},format=yuva420p,"
                      f"setpts=PTS-STARTPTS+{ba:.4f}/TB,"
                      f"fade=t=in:st={ba:.3f}:d=0.35:alpha=1,fade=t=out:st={bb - 0.35:.3f}:d=0.35:alpha=1[br{j}]")
        else:
            inputs += ["-ss", str(o.get("from", 0)), "-t", f"{d:.3f}", "-i", o["file"]]
            fc.append(f"[{idx}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
                      f"fps={FPS},{GRADES.get(plan.get('grade', 'warm')) or 'null'},format=yuva420p,"
                      f"setpts=PTS-STARTPTS+{ba:.4f}/TB,"
                      f"fade=t=in:st={ba:.3f}:d=0.35:alpha=1,fade=t=out:st={bb - 0.35:.3f}:d=0.35:alpha=1[br{j}]")
        idx += 1
        fc.append(f"[{cur}][br{j}]overlay=eof_action=pass:format=auto[bv{j}]")
        cur = f"bv{j}"

    # ---- text & graphics (libass)
    ass_esc = ass_path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    fdir = FONTS_DIR.replace("\\", "/").replace(":", "\\:")
    fc.append(f"[{cur}]ass=filename='{ass_esc}':fontsdir='{fdir}':shaping=complex[tx]")
    cur = "tx"

    # ---- logo watermark
    wm = plan.get("watermark") or {}
    logo = wm.get("logo") or ""
    if wm.get("enabled") and logo and os.path.exists(logo):
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{T:.3f}", "-i", logo]
        lw = int(W * (0.16 if H > W else 0.09))
        m = int(min(W, H) * 0.04)
        fc.append(f"[{idx}:v]scale={lw}:-1,format=yuva420p,colorchannelmixer=aa=0.85,"
                  f"fade=t=in:st={c0 + 0.5:.3f}:d=0.6:alpha=1[lg]")
        fc.append(f"[{cur}][lg]overlay=x=W-w-{m}:y={m}:shortest=1:format=auto[lgo]")
        idx += 1
        cur = "lgo"
    if a.draft:
        fc.append(f"[{cur}]scale={W // 2}:{H // 2}[vout]")
    else:
        fc.append(f"[{cur}]null[vout]")

    # ---- audio (voice is cleaned in its own pass -> stable timestamps, true 2-pass loudnorm)
    au = plan.get("audio") or {}
    voice = clean_voice(speaker, work, au)
    inputs += ["-i", voice]
    vi = idx
    idx += 1
    fc.append(f"[{vi}:a]aresample=48000,aformat=channel_layouts=stereo,"
              f"adelay={int(round(c0 * 1000))}:all=1,apad=whole_dur={T:.3f}[amx]")
    acur = "amx"
    music = au.get("music") or ""
    whoosh = au.get("whoosh") and (wins or any(o.get("type") == "broll" for o in plan.get("overlays", [])))
    if music and os.path.exists(music):
        inputs += ["-stream_loop", "-1", "-i", music]
        fc.append("[amx]asplit=2[voice][sc]")
        mv = float(au.get("music_volume", 0.07))
        fc.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{T:.3f},volume={mv},"
                  f"afade=t=in:d=1.5,afade=t=out:st={max(0, T - 2.5):.3f}:d=2.5[mus]")
        fc.append("[mus][sc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[duck]")
        fc.append("[voice][duck]amix=inputs=2:duration=first:normalize=0[amm]")
        idx += 1
        acur = "amm"
    if whoosh:
        times = [w[0] for w in wins] + [tl.map(o["start"]) for o in plan.get("overlays", []) if o.get("type") == "broll"]
        for k, t0 in enumerate(times):
            fc.append(f"anoisesrc=color=pink:d=0.9:a=0.5:r=48000,highpass=f=400,lowpass=f=4500,"
                      f"afade=t=in:d=0.45:curve=exp,afade=t=out:st=0.45:d=0.45,volume=0.18,"
                      f"aformat=channel_layouts=stereo,adelay={max(0, int((t0 - 0.45) * 1000))}:all=1[wh{k}]")
        fc.append(f"[{acur}]" + "".join(f"[wh{k}]" for k in range(len(times)))
                  + f"amix=inputs={len(times) + 1}:duration=first:normalize=0[aout]")
    else:
        fc.append(f"[{acur}]anull[aout]")

    out = a.output or plan["output"]
    if a.draft:
        out = os.path.splitext(out)[0] + "_draft.mp4"
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    graph_path = os.path.join(work, "filter_graph.txt")
    with open(graph_path, "w", encoding="utf-8") as f:
        f.write(";\n".join(fc))
    cmd = (["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats"] + inputs
           + ["-filter_complex_script", graph_path, "-map", "[vout]", "-map", "[aout]",
              "-t", f"{T:.3f}", "-r", str(FPS),
              "-c:v", "libx264", "-preset", "ultrafast" if a.draft else a.preset,
              "-crf", "26" if a.draft else str(a.crf), "-pix_fmt", "yuv420p",
              "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
    log(f"rendering {T:.1f}s -> {out}")
    p = subprocess.run(cmd)
    if p.returncode != 0:
        raise SystemExit("final render failed; see filter graph in " + graph_path)
    save_json(os.path.join(work, "last_render.json"),
              {"output": out, "duration": T, "intro": intro_d, "content": C, "outro": outro_d,
               "segments": len(plan["segments"]), "geometry": geo})
    print(json.dumps({"output": out, "duration": round(T, 2), "content_seconds": round(C, 2),
                      "cuts": len(plan["segments"]) - 1}, indent=2))


def cmd_preview(a):
    """Fast layout check: overlays + card placeholder on the style colour, no video decode."""
    plan = load_json(a.plan)
    style = load_json(STYLES)[plan.get("style", "jtr-cinematic")]
    brand, _ = find_brand(a.brand)
    W, H = FORMATS[plan.get("format", "reel")]
    info = probe(plan["source"])
    work = a.work or workdir_for(plan["source"])
    geo = layer_geometry(plan, W, H, info["width"], info["height"])
    segs = sorted(plan.get("segments") or [{"start": 0, "end": info["duration"]}], key=lambda x: x["start"])
    intro_d = float(plan["intro"]["duration"]) if (plan.get("intro") or {}).get("enabled") else 0.0
    outro_d = float(plan["outro"]["duration"]) if (plan.get("outro") or {}).get("enabled") else 0.0
    tl = Timeline(segs, intro_d)
    T = intro_d + tl.content + outro_d
    ass_path = os.path.join(work, "preview.ass")
    build_ass(plan, style, W, H, geo, tl, intro_d, outro_d, T, ass_path, brand)
    times = [float(x) for x in a.at.split(",")] if a.at else [
        round(min(T - 0.1, x), 2) for x in (intro_d * 0.7, intro_d + 2.5, T * 0.5, T - outro_d * 0.4)]
    bgc = style["background"]["colors"][1].replace("#", "0x")
    fdir = FONTS_DIR.replace(":", "\\:")
    box = (f",drawbox=x={geo['x']}:y={geo['y']}:w={geo['w']}:h={geo['h']}:color=gray@0.6:t=fill:"
           f"enable='between(t,{intro_d},{intro_d + tl.content})'") if geo["card"] else ""
    tiles = []
    for t in times:
        p = os.path.join(work, f"preview_{t:07.2f}.png")
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c={bgc}:s={W}x{H}:r=10:d={T + 1:.2f}",
             "-vf", f"null{box},ass=filename={ass_path}:fontsdir={fdir}:shaping=complex,"
                    f"drawtext=fontfile={os.path.join(FONTS_DIR, 'Poppins-Bold.ttf')}:text='t={t:.2f}s':"
                    f"x=10:y=h-60:fontsize=40:fontcolor=red",
             "-ss", f"{t:.2f}", "-frames:v", "1", "-update", "1", p])
        tiles.append(p)
    sheet = os.path.join(work, "preview_sheet.png")
    ins = []
    for p in tiles:
        ins += ["-i", p]
    run(["ffmpeg", "-y", "-v", "error"] + ins + ["-filter_complex",
         f"{''.join(f'[{i}:v]' for i in range(len(tiles)))}hstack={len(tiles)},scale=-2:{min(960, H)}"
         if len(tiles) > 1 else "scale=-2:960", sheet])
    print(sheet)


# ---------------------------------------------------------------------------
# frames / background preview
# ---------------------------------------------------------------------------

def cmd_frames(a):
    work = a.work or workdir_for(a.video)
    outdir = os.path.join(work, "frames")
    os.makedirs(outdir, exist_ok=True)
    paths = []
    for t in [float(x) for x in a.at.split(",")]:
        p = os.path.join(outdir, f"{os.path.splitext(os.path.basename(a.video))[0]}_{t:08.2f}.jpg")
        run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", a.video, "-frames:v", "1",
             "-vf", f"scale={a.width}:-2", "-q:v", "3", p])
        paths.append(p)
    print("\n".join(paths))


def cmd_background(a):
    styles = load_json(STYLES)
    W, H = FORMATS[a.format]
    work = a.work or os.path.join(os.getcwd(), "videos", "work", "_bg")
    os.makedirs(work, exist_ok=True)


    style = styles[a.style]
    bg = style["background"]
    pat, tile, par = graphics.ensure_background_assets(work, W, H, style)
    T = a.seconds
    cols = bg["colors"]
    dx, dy = bg.get("pattern_drift", [6, 3])
    g = (f"gradients=s={W}x{H}:r={FPS}:d={T}:n={len(cols)}:" + ":".join(
        f"c{i}={c.replace('#', '0x')}" for i, c in enumerate(cols))
         + f":speed={bg.get('speed', 0.005)}:type={bg.get('type', 'radial')}:seed=11,format=yuv420p[g0];"
         f"[0:v]format=gray,crop={W}:{H}:x='mod(t*{dx},{tile})':y='mod(t*{dy},{tile})',"
         f"lut=y='val*{bg['pattern_opacity']}'[pm];"
         f"color=c={bg['pattern_color'].replace('#', '0x')}:s={W}x{H}:r={FPS}:d={T},format=yuva420p[pc];"
         f"[pc][pm]alphamerge[pl];[g0][pl]overlay=shortest=1[g1];"
         f"[1:v]format=gray,crop={W}:{H}:x=0:y='{H}-mod(t*{bg.get('particle_speed', 14)},{H})',"
         f"lut=y='val*{bg.get('particle_opacity', 0)}'[qm];"
         f"color=c={bg['particle_color'].replace('#', '0x')}:s={W}x{H}:r={FPS}:d={T},format=yuva420p[qc];"
         f"[qc][qm]alphamerge[ql];[g1][ql]overlay=shortest=1"
         + (",vignette=angle=PI/4.5" if bg.get("vignette") else "") + "[v]")
    out = a.output or os.path.join(os.getcwd(), "videos", "edited", f"bg_{a.style}_{a.format}.mp4")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-t", str(T), "-i", pat,
         "-loop", "1", "-framerate", str(FPS), "-t", str(T), "-i", par,
         "-filter_complex", g, "-map", "[v]", "-t", str(T), "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", out])
    print(out)


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(prog="dai", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)

    p = sub.add_parser("analyze")
    p.add_argument("video")
    p.add_argument("--work")
    p.add_argument("--noise", type=float, default=-35, help="silence threshold dB (raise to -30 for noisy rooms)")
    p.add_argument("--min-silence", type=float, default=0.45)
    p.set_defaults(fn=cmd_analyze)

    p = sub.add_parser("transcribe")
    p.add_argument("video")
    p.add_argument("--work")
    p.add_argument("--lang", default="ur", help="ur | hi | ar | en | auto")
    p.add_argument("--model", default="medium", help="tiny|base|small|medium|large-v3")
    p.add_argument("--device", default="cpu")
    p.add_argument("--prompt", help="vocabulary hint for whisper")
    p.set_defaults(fn=cmd_transcribe)

    p = sub.add_parser("autoplan")
    p.add_argument("video")
    p.add_argument("--work")
    p.add_argument("--format", choices=list(FORMATS), default="reel")
    p.add_argument("--layout", choices=["frame", "fill"])
    p.add_argument("--style", help="default: brand style or jtr-cinematic")
    p.add_argument("--lang", help="caption language ur|ar|hi|en (default: brand or ur)")
    p.add_argument("--brand")
    p.add_argument("--transcript")
    p.add_argument("--plan")
    p.add_argument("--output")
    p.add_argument("--noise", type=float, default=-35)
    p.add_argument("--min-silence", type=float, default=0.45)
    p.set_defaults(fn=cmd_autoplan)

    p = sub.add_parser("render")
    p.add_argument("plan")
    p.add_argument("--work")
    p.add_argument("--brand")
    p.add_argument("--output")
    p.add_argument("--draft", action="store_true", help="fast half-resolution preview")
    p.add_argument("--crf", type=int, default=18)
    p.add_argument("--preset", default="medium")
    p.set_defaults(fn=cmd_render)

    p = sub.add_parser("preview", help="fast overlay/layout check without rendering video")
    p.add_argument("plan")
    p.add_argument("--at", help="comma separated OUTPUT times (s)")
    p.add_argument("--brand")
    p.add_argument("--work")
    p.set_defaults(fn=cmd_preview)

    p = sub.add_parser("frames")
    p.add_argument("video")
    p.add_argument("--at", required=True, help="comma separated seconds")
    p.add_argument("--width", type=int, default=540)
    p.add_argument("--work")
    p.set_defaults(fn=cmd_frames)

    p = sub.add_parser("background")
    p.add_argument("--style", default="jtr-cinematic")
    p.add_argument("--format", choices=list(FORMATS), default="reel")
    p.add_argument("--seconds", type=float, default=10)
    p.add_argument("--output")
    p.add_argument("--work")
    p.set_defaults(fn=cmd_background)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
