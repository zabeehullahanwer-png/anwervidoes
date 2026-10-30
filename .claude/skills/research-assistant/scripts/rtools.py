#!/usr/bin/env python3
"""Research toolkit for the research-assistant skill.

Commands:
  extract  PDF/DOCX/TXT -> Markdown/text
  outline  headings, words per section, footnote count
  overlap  n-gram overlap of a draft against source texts (self-plagiarism check)
  style    sentence rhythm, stock phrases, repeated sentence openers
  refs     list footnotes / citations, flag unverified markers
  export   Markdown -> DOCX (pandoc, optional citeproc)

Only the standard library is required; pandoc, pdftotext, pypdf and python-docx are used when present.
"""
import argparse
import re
import shutil
import statistics
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path

UNVERIFIED = ["[تصدیق طلب]", "[دلیل درکار]", "[verify]", "[citation needed]"]

STOCK_EN = [
    "delve", "delves", "delving", "tapestry", "in today's world", "in today's fast-paced",
    "it is important to note", "it is worth noting", "plays a pivotal role", "plays a crucial role",
    "a testament to", "navigate the complexities", "in the realm of", "shed light on", "sheds light on",
    "multifaceted", "underscores", "furthermore,", "moreover,", "in conclusion,", "holistic",
    "intricate", "landscape of", "serves as a", "nuanced understanding", "at its core",
]
STOCK_UR = [
    "یہ بات قابل ذکر ہے", "یہ بات قابلِ ذکر ہے", "موجودہ دور میں", "اس کی اہمیت اور بھی بڑھ جاتی ہے",
    "خلاصۂ کلام", "خلاصہ کلام", "مزید برآں", "اس میں کوئی شک نہیں", "بلاشبہ", "نہایت اہمیت کا حامل",
    "اہم کردار ادا", "روشنی ڈالی", "جامع انداز", "کلیدی کردار",
]


def die(msg):
    sys.exit(f"rtools: {msg}")


def read_text(path):
    p = Path(path)
    if not p.exists():
        die(f"not found: {path}")
    ext = p.suffix.lower()
    if ext == ".pdf":
        return pdf_text(p)
    if ext == ".docx":
        return docx_text(p)
    return p.read_text(encoding="utf-8", errors="replace")


def pdf_text(p):
    if shutil.which("pdftotext"):
        out = subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True)
        text = out.stdout.decode("utf-8", errors="replace")
        if text.strip():
            return text
    try:
        from pypdf import PdfReader
    except ImportError:
        die("install poppler (pdftotext) or `pip install pypdf` to read PDFs")
    reader = PdfReader(str(p))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n\f\n".join(pages)


def docx_text(p):
    if shutil.which("pandoc"):
        out = subprocess.run(["pandoc", str(p), "-t", "gfm", "--wrap=none"], capture_output=True)
        if out.returncode == 0:
            return out.stdout.decode("utf-8", errors="replace")
    try:
        import docx
    except ImportError:
        die("install pandoc or `pip install python-docx` to read DOCX")
    d = docx.Document(str(p))
    lines = []
    for para in d.paragraphs:
        style = (para.style.name or "").lower()
        m = re.match(r"heading (\d)", style)
        lines.append(("#" * int(m.group(1)) + " " if m else "") + para.text)
    return "\n\n".join(lines)


# ---------- normalisation for overlap ----------

ARABIC_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
FOLD = str.maketrans({"ي": "ی", "ى": "ی", "ئ": "ی", "ك": "ک", "ة": "ہ", "ه": "ہ", "ۀ": "ہ",
                      "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ؤ": "و", "ے": "ی"})


def norm_tokens(text, display=False):
    text = ARABIC_DIACRITICS.sub("", unicodedata.normalize("NFKC", text))
    if not display:
        text = text.translate(FOLD).lower()
    return re.findall(r"\w+", text)


def words(text):
    return re.findall(r"\w+", text)


# ---------- commands ----------

def cmd_extract(a):
    text = read_text(a.file)
    if a.output:
        Path(a.output).parent.mkdir(parents=True, exist_ok=True)
        Path(a.output).write_text(text, encoding="utf-8")
        print(f"wrote {a.output}: {len(words(text)):,} words")
    else:
        sys.stdout.write(text)


HEADING = re.compile(r"^(#{1,6})\s+(.*)")
CHAPTER = re.compile(r"^\s*(chapter|باب|فصل|الفصل|الباب)\s*[\w\-:،]*", re.I)


def cmd_outline(a):
    text = read_text(a.file)
    sections, cur = [], ["(start)", 0, 0]
    for line in text.splitlines():
        m = HEADING.match(line)
        if m or (CHAPTER.match(line) and len(line) < 120):
            sections.append(cur)
            level = len(m.group(1)) if m else 1
            title = (m.group(2) if m else line).strip()
            cur = [("  " * (level - 1)) + title, 0, level]
            continue
        cur[1] += len(words(line))
    sections.append(cur)
    total = sum(s[1] for s in sections)
    for title, n, _ in sections:
        if n or title != "(start)":
            print(f"{n:>7,}  {title[:100]}")
    notes = len(re.findall(r"\[\^[^\]]+\]:", text))
    print(f"\n{total:,} words, {len(sections) - 1} headings, {notes} markdown footnotes")


def shingles(tokens, n):
    return {tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def cmd_overlap(a):
    n = a.n
    raw = read_text(a.draft)
    draft, shown = norm_tokens(raw), norm_tokens(raw, display=True)
    if len(draft) < n:
        die("draft too short")
    src = set()
    for s in a.sources:
        src |= shingles(norm_tokens(read_text(s)), n)
    hits = [tuple(draft[i:i + n]) in src for i in range(len(draft) - n + 1)]
    pct = 100 * sum(hits) / len(hits)
    # merge consecutive hits into passages
    passages, i = [], 0
    while i < len(hits):
        if hits[i]:
            j = i
            while j + 1 < len(hits) and hits[j + 1]:
                j += 1
            passages.append((i, j + n))
            i = j + 1
        else:
            i += 1
    covered = sum(e - s for s, e in passages)
    print(f"{n}-gram overlap: {pct:.1f}% of draft sequences; "
          f"{covered:,} of {len(draft):,} words inside {len(passages)} matching passages")
    verdict = "OK" if pct < 5 else ("REVIEW" if pct < 15 else "HIGH: rewrite")
    print(f"verdict: {verdict} (target < 5%; quotations of primary sources are expected matches)")
    for s, e in sorted(passages, key=lambda p: p[0] - p[1])[:a.top]:
        print(f"\n[{e - s} words] " + " ".join(shown[s:e])[:400])


SENT_SPLIT = re.compile(r"(?<=[.!?۔؟])\s+")


def cmd_style(a):
    text = read_text(a.file)
    body = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith(("#", "[^", ">")))
    sents = [s.strip() for s in SENT_SPLIT.split(body) if len(words(s)) >= 3]
    if not sents:
        die("no sentences found")
    lens = [len(words(s)) for s in sents]
    mean = statistics.mean(lens)
    sd = statistics.pstdev(lens)
    print(f"{len(words(body)):,} words, {len(sents)} sentences, mean {mean:.1f} words, sd {sd:.1f}, "
          f"cv {sd / mean:.2f}")
    if sd / mean < 0.35:
        print("  rhythm: monotone (sentence lengths too similar); vary them where the argument allows")
    long_ = sum(1 for n in lens if n > 45)
    if long_:
        print(f"  {long_} sentences over 45 words: consider splitting")
    low = body.lower()
    found = [(p, low.count(p)) for p in STOCK_EN + STOCK_UR if low.count(p)]
    if found:
        print("\nstock phrases (replace with specific claims):")
        for p, c in sorted(found, key=lambda x: -x[1]):
            print(f"  {c:>3}  {p}")
    openers = Counter(" ".join(words(s)[:2]).lower() for s in sents)
    rep = [(o, c) for o, c in openers.most_common(10) if c >= 3]
    if rep:
        print("\nrepeated sentence openers:")
        for o, c in rep:
            print(f"  {c:>3}  {o} ...")
    paras = [p for p in re.split(r"\n\s*\n", body) if len(words(p)) > 20]
    if paras:
        pl = [len(words(p)) for p in paras]
        print(f"\n{len(paras)} paragraphs, {min(pl)}–{max(pl)} words (mean {statistics.mean(pl):.0f})")


def cmd_refs(a):
    text = read_text(a.file)
    defs = re.findall(r"^\[\^([^\]]+)\]:\s*(.+)$", text, re.M)
    calls = set(re.findall(r"\[\^([^\]]+)\](?!:)", text))
    cites = re.findall(r"\[@[^\]]+\]|(?<![\w@])@[A-Za-z][\w:-]*\d{4}\w*", text)
    print(f"{len(defs)} footnotes, {len(cites)} pandoc citations")
    for k, v in defs:
        flag = " <-- UNVERIFIED" if any(u in v for u in UNVERIFIED) else ""
        print(f"  [^{k}] {v[:160]}{flag}")
    missing = calls - {k for k, _ in defs}
    if missing:
        print("footnote calls without text: " + ", ".join(sorted(missing)))
    for u in UNVERIFIED:
        c = text.count(u)
        if c:
            print(f"{c} x {u} still in the text")
    if cites:
        keys = Counter(re.findall(r"@([\w:-]+)", " ".join(cites)))
        print("citation keys: " + ", ".join(f"{k}({c})" for k, c in keys.most_common()))


def cmd_export(a):
    if not shutil.which("pandoc"):
        die("pandoc is required for export (https://pandoc.org/installing.html)")
    out = a.output or str(Path(a.file).with_suffix(".docx"))
    cmd = ["pandoc", a.file, "-o", out]
    if a.bib:
        cmd += ["--citeproc", "--bibliography", a.bib]
    if a.csl:
        cmd += ["--csl", a.csl]
    if a.ref:
        cmd += ["--reference-doc", a.ref]
    if a.rtl:
        cmd += ["-M", "dir=rtl", "-M", "lang=ur"]
    r = subprocess.run(cmd)
    if r.returncode:
        die("pandoc failed")
    print(f"wrote {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("extract"); p.add_argument("file"); p.add_argument("-o", "--output")
    p.set_defaults(f=cmd_extract)
    p = sp.add_parser("outline"); p.add_argument("file"); p.set_defaults(f=cmd_outline)
    p = sp.add_parser("overlap"); p.add_argument("draft"); p.add_argument("sources", nargs="+")
    p.add_argument("-n", type=int, default=8, help="n-gram size (default 8)")
    p.add_argument("--top", type=int, default=10, help="longest passages to show")
    p.set_defaults(f=cmd_overlap)
    p = sp.add_parser("style"); p.add_argument("file"); p.set_defaults(f=cmd_style)
    p = sp.add_parser("refs"); p.add_argument("file"); p.set_defaults(f=cmd_refs)
    p = sp.add_parser("export"); p.add_argument("file"); p.add_argument("-o", "--output")
    p.add_argument("--bib"); p.add_argument("--csl"); p.add_argument("--ref", help="reference .docx template")
    p.add_argument("--rtl", action="store_true", help="Urdu / Arabic right-to-left document")
    p.set_defaults(f=cmd_export)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
