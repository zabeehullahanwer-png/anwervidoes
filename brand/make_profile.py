"""Professional profile pictures from a plain phone portrait.

The face is NOT retouched or reshaped: only the background is replaced (MODNet portrait
matting via onnxruntime) and global light/colour is corrected (curtain colour cast removed).

  python3 brand/make_profile.py brand/profile/src1.jpg [--name tag]
Outputs 1080x1080 PNGs in brand/profile/out/ (git-ignored: personal photos).
"""
import argparse
import os

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "profile", "out")


def matte(img):
    """MODNet alpha matte (0..1) at the image's own resolution."""
    model = hf_hub_download("Xenova/modnet", "onnx/model.onnx")
    sess = ort.InferenceSession(model, providers=["CPUExecutionProvider"])
    w, h = img.size
    ref = 768
    s = ref / max(w, h)
    rw, rh = max(32, int(w * s) // 32 * 32), max(32, int(h * s) // 32 * 32)
    x = np.asarray(img.resize((rw, rh), Image.BICUBIC)).astype(np.float32) / 255.0
    x = ((x - 0.5) / 0.5).transpose(2, 0, 1)[None]
    name = sess.get_inputs()[0].name
    m = sess.run(None, {name: x})[0][0, 0]
    m = Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    return np.asarray(m).astype(np.float32) / 255.0


def backdrop(w, h, kind, cx, cy):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - cx) / (w * 0.55)) ** 2 + ((yy - cy) / (h * 0.55)) ** 2)
    glow = np.exp(-d ** 2 * 1.4)
    if kind == "charcoal":      # classic studio: charcoal with a soft light behind the head
        inner, outer = np.array([0.36, 0.37, 0.39]), np.array([0.06, 0.065, 0.075])
    elif kind == "emerald":     # brand colour (matches the logo and videos)
        inner, outer = np.array([0.10, 0.36, 0.29]), np.array([0.010, 0.07, 0.055])
    else:                       # light grey, clean and bright
        inner, outer = np.array([0.93, 0.93, 0.92]), np.array([0.62, 0.63, 0.64])
    bg = outer + (inner - outer) * glow[..., None]
    # subtle film grain so the gradient never bands
    bg += np.random.default_rng(1).normal(0, 0.006, bg.shape)
    return np.clip(bg, 0, 1)


def grade(rgb, mask):
    """neutralise the warm curtain cast using the (neutral) blue kurta + skin, gentle contrast."""
    person = mask > 0.9
    means = rgb[person].mean(axis=0)
    gray = means.mean()
    wb = np.clip(gray / means, 0.92, 1.08)  # mild white-balance pull only
    out = rgb * wb
    out = np.clip((out - 0.5) * 1.05 + 0.5 + 0.01, 0, 1)  # +5% contrast, tiny lift
    return out


def _blur(a, r):
    if a.ndim == 2:
        im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(r))
        return np.asarray(im).astype(np.float32) / 255.0
    return np.dstack([_blur(a[..., i], r) for i in range(a.shape[2])])


def decontaminate(rgb, alpha, bg):
    """Remove the old background colour that bleeds into soft edges (beard, cap, shoulders):
    estimate the old background behind each edge pixel and solve I = a*F + (1-a)*B for F."""
    a = alpha[..., None]
    w = 1 - a
    b_old = _blur(rgb * w, 18) / np.maximum(_blur(w, 18), 1e-3)
    f = (rgb - (1 - a) * b_old) / np.maximum(a, 0.08)
    edge = ((a > 0.03) & (a < 0.97)).astype(np.float32)
    return np.clip(rgb * (1 - edge) + f * edge, 0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--name", default=None)
    a = ap.parse_args()
    tag = a.name or os.path.splitext(os.path.basename(a.src))[0]
    img = Image.open(a.src).convert("RGB")
    w, h = img.size
    alpha = matte(img)
    alpha = np.clip((alpha - 0.06) / 0.9, 0, 1)  # choke the matte slightly: no curtain halo
    rgb = np.asarray(img).astype(np.float32) / 255.0
    rgb = grade(rgb, alpha)

    # framing: head-and-shoulders square, eyes ~38% from the top
    ys, xs = np.where(alpha > 0.5)
    top, cx = ys.min(), np.median(xs)
    side = int(min(w, h, (h - top) * 1.18))
    x0 = int(np.clip(cx - side / 2, 0, w - side))
    y0 = int(np.clip(top - side * 0.10, 0, h - side))
    crop = (x0, y0, x0 + side, y0 + side)

    os.makedirs(OUT, exist_ok=True)
    for kind in ("charcoal", "emerald", "light"):
        bg = backdrop(w, h, kind, cx, top + (h - top) * 0.25)
        fg = decontaminate(rgb, alpha, bg)
        a3 = alpha[..., None]
        comp = fg * a3 + bg * (1 - a3)
        # soft vignette to focus the face
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        v = 1 - 0.18 * np.clip(np.sqrt(((xx - cx) / w) ** 2 + ((yy - h * 0.45) / h) ** 2) * 1.6 - 0.3, 0, 1)
        comp = np.clip(comp * v[..., None], 0, 1)
        im = Image.fromarray((comp * 255).astype(np.uint8)).crop(crop).resize((1080, 1080), Image.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(1.2, 40, 3))  # gentle crispness, no skin smoothing
        p = os.path.join(OUT, f"profile_{tag}_{kind}.png")
        im.save(p)
        print(p)
    # transparent cut-out (for posters / thumbnails)
    cut = np.dstack([rgb, alpha])
    Image.fromarray((cut * 255).astype(np.uint8), "RGBA").save(os.path.join(OUT, f"cutout_{tag}.png"))


if __name__ == "__main__":
    main()
