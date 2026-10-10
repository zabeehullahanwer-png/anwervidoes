"""Short opening sting (reel 1080x1920, ~6 s) for Zabeehullah Leghari.

Light comes up on the calligraphy logo while the camera eases in, a shine sweeps across
the metal letters, dust drifts in the light, then the name appears beneath.
Sound: soft whoosh + low swell (no music).

  python3 brand/make_intro.py [--palette emerald|navy]
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.join(HERE, "..", ".claude", "skills", "dai-video-editor")
sys.path.insert(0, os.path.join(SK, "scripts"))
from ass_builder import AssDoc  # noqa: E402
import graphics  # noqa: E402

FONTS = os.path.join(SK, "assets", "fonts")
W, H, FPS, T = 1080, 1920, 30, 6.0


def esc(p):
    return p.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--palette", default="emerald")
    a = ap.parse_args()
    logo = os.path.join(HERE, "logo", f"reel_plate_{a.palette}.png")
    alpha = os.path.join(HERE, "logo", f"reel_mask_{a.palette}.png")
    out = os.path.join(HERE, "logo", f"intro_{a.palette}_reel.mp4")
    work = os.path.join(HERE, ".work")
    os.makedirs(work, exist_ok=True)

    # title text (libass: proper Nastaliq shaping)
    style = {"text": "#FFFFFF", "accent": "#CFE9DD" if a.palette == "emerald" else "#E9DFC6",
             "muted": "#DDE8E3"}
    doc = AssDoc(W, H, style, "ur")
    tag, scr, sz = doc.text_tag("ذبیح اللہ لغاری", 0.068, col="#FFFFFF", outline=0, shadow=0)
    doc.add(2.7, T, "{\\an5\\pos(540,1610)%s\\bord0\\shad2\\4a&H60&\\fad(700,0)\\blur8\\t(0,800,\\blur0)"
                    "\\fscx92\\fscy92\\t(0,1600,\\fscx100\\fscy100)}ذبیح اللہ لغاری" % tag, layer=5)
    doc.divider(3.3, T, 540, 1708, 300, delay_ms=0)
    etag, _, _ = doc.text_tag("ZABEEHULLAH LEGHARI", 0.026, col=style["accent"])
    doc.add(3.7, T, "{\\an5\\pos(540,1772)%s\\fsp6\\fad(600,0)}ZABEEHULLAH LEGHARI" % etag, layer=5)
    ass = os.path.join(work, "intro.ass")
    doc.write(ass)

    # dust particles
    par = os.path.join(work, "dust.pgm")
    graphics.write_pgm(par, W, 2 * H, graphics.particle_field(W, H, n=45, seed=21, rmax=4.5))

    zoom = "1.08-0.08*(1-pow(1-on/{n},3))".format(n=int(T * FPS))  # ease-out push
    fc = [
        # logo plate: ease-in camera push, crop to 9:16, light comes up
        f"[0:v]scale={W * 2}:{H * 2},zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih*0.45-(ih/zoom*0.45)':d=1:s={W}x{H}:fps={FPS},"
        f"format=yuv420p,"
        f"fade=t=in:st=0:d=1.6,eq=gamma=1.0[base]",
        # same transform for the letter mask (for the shine)
        f"[1:v]format=gray,scale={W * 2}:{H * 2},zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih*0.45-(ih/zoom*0.45)':d=1:s={W}x{H}:fps={FPS},"
        f"format=gray[m]",
        # diagonal shine band travelling across the frame between 1.4 s and 2.9 s
        f"color=black:s={W}x{H}:r={FPS}:d={T},format=gray,"
        f"geq=lum='255*exp(-pow((X*0.8+Y*0.45-(T-1.4)*1500+250)/90,2))'[band]",
        "[m][band]blend=all_mode=multiply[shm]",
        f"color=c=0xF4FFFB:s={W}x{H}:r={FPS}:d={T},format=yuva420p[shc]",
        "[shc][shm]alphamerge[shine]",
        "[base][shine]overlay=format=auto[b1]",
        # drifting dust in the light
        f"[2:v]format=gray,crop={W}:{H}:x=0:y='{H}-mod(t*16,{H})',lut=y='val*0.55',"
        f"fade=t=in:st=0.6:d=1.5[dm]",
        f"color=c=0xEFFFF6:s={W}x{H}:r={FPS}:d={T},format=yuva420p[dc]",
        "[dc][dm]alphamerge[dust]",
        "[b1][dust]overlay=format=auto[b2]",
        f"[b2]ass=filename='{esc(ass)}':fontsdir='{esc(FONTS)}':shaping=complex,"
        f"fade=t=out:st={T - 0.5}:d=0.5,format=yuv420p[v]",
        # sound: whoosh into the reveal + low swell
        f"anoisesrc=color=pink:d=2.2:a=0.6:r=48000,highpass=f=250,lowpass=f=5000,"
        f"afade=t=in:d=1.2:curve=exp,afade=t=out:st=1.2:d=1.0,volume=0.30,adelay=300:all=1[wh]",
        f"aevalsrc='0.35*sin(2*PI*55*t)*exp(-t*1.1)*(1-exp(-t*30))':s=48000:d=4.5,"
        f"aecho=0.8:0.6:120|260:0.35|0.2,adelay=1400:all=1[boom]",
        f"[wh][boom]amix=inputs=2:normalize=0,apad=whole_dur={T},atrim=0:{T},"
        f"aformat=channel_layouts=stereo,afade=t=out:st={T - 0.6}:d=0.6,loudnorm=I=-16:TP=-2[a]",
    ]
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-loop", "1", "-framerate", str(FPS), "-t", str(T), "-i", logo,
           "-loop", "1", "-framerate", str(FPS), "-t", str(T), "-i", alpha,
           "-loop", "1", "-framerate", str(FPS), "-t", str(T), "-i", par,
           "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]", "-t", str(T),
           "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    print(out)


if __name__ == "__main__":
    main()
