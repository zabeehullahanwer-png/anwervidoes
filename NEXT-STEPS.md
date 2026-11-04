# Next steps (handoff for a new session)

Read `CLAUDE.md` first: reply in Urdu, keep Qur'an and Hadith text exact, and never commit videos or the book PDFs.

## Keep usage low
- One task per session.
- Do not run several agents in parallel.
- Read the book one chapter at a time.
- Prefer the English text over viewing the scanned page images.

## Done (all in this repo)
- **Video editing skill:** `.claude/skills/dai-video-editor/` (`SKILL.md`, the scripts, and `reference/content-strategy.md` with the content strategy).
- **Brand:** logos in `brand/logo/` (navy/ivory/gold calligraphy), an intro (`intro_navy_16x9.mp4`), and the colours `#0F2A4A` / `#F7F3EA` / `#B08D57`.
- **Profile photos:** `brand/make_profile_base.py` (master retouch) and `make_profile_dai.py` (mihrab).
- **Platform kits:**

  | Platform | Script | Notes file |
  |---|---|---|
  | Facebook | `make_facebook.py` | — |
  | YouTube | `make_youtube.py` | `YOUTUBE-CHANNEL.md` |
  | Instagram and TikTok | `make_instagram_tiktok.py` | `INSTAGRAM-TIKTOK.md` |
  | LinkedIn | `make_linkedin.py` | `LINKEDIN.md` |
  | X and academic profiles | `make_x_academic.py` | `X-AND-ACADEMIC.md` |
  | Website assets | `make_website_photos.py`, `make_web_assets.py` | — |

  Generated images are git-ignored; re-run the scripts to recreate them.
- **Links:** `brand/SOCIAL-LINKS.md` lists every social and academic link and the website https://www.zabeehullahleghari.com.
- **Developer messages:** `brand/DEVELOPER-MESSAGE-2.md` is the latest. It covers the remaining fixes: icons, og-image, the hero cut-out, and the PhD sentence.
- **Research report (Urdu):** `reports/اسلامی مواد کا منظرنامہ اور مواقع.md`. The positioning is «سند کے ساتھ: محقق، مناظر نہیں».
- **Virtual studios:**
  - `brand/make_virtual_studios.py` renders 5 sets (library, broadcast, arches, brand, manuscript). Use `--vertical` for reels.
  - `brand/make_studio_demo.py` keys green-screen footage into a set.

## Open with the user
1. **PhD:** is the user enrolled? The bios say "pursuing doctoral research", but ORCID shows an MPhil (IUB 2024–26) and an MA (Punjab University 2021–23).
2. **Developer:** has the developer applied `DEVELOPER-MESSAGE-2.md`? Re-check the site afterwards.
3. **Green-screen test video:** the user will send one, recorded landscape, 1.5–2 m from the camera, waist-up, with a table covered in green cloth.
4. **Environment setup script:** line 3 contains only `huggingface.co`, which makes the script fail. Ask the user to remove that line and keep the domain under **Allowed domains**.

## Book documentary (in progress, restart from here)
- **Book:** Abul Hasan Ali Nadwi, «انسانی دنیا پر مسلمانوں کے عروج و زوال کا اثر» (Arabic: ماذا خسر العالم بانحطاط المسلمین; English: *Islam and the World*).
- **PDFs:** download them again from the official site (the domain `abulhasanalinadwi.org` must be allowed). Do not commit them.
  - Urdu: https://abulhasanalinadwi.org/books/insaanee%20dunya%20par%20musalmaano%20ke%20uruj%20aur%20zawal%20ka%20asar.pdf. 482 pages, scanned, 10th edition (1981, Lucknow). PDF page = printed page + 4.
  - English: https://abulhasanalinadwi.org/books/islam%20and%20the%20world.pdf. It has a text layer, so `pdftotext` works.
  - Arabic: on the same site; search for «ماذا».
- **Urdu chapter starts (printed pages):**

  | Section | Pages |
  |---|---|
  | Intro «کچھ کتاب کے متعلق» | 14 |
  | Ch. I «بعثتِ محمدی سے پہلے» | 37–99 |
  | Ch. II «بعثتِ محمدی کے بعد» | 100–154 |
  | Ch. III «مسلمانوں کا دورِ قیادت» | 155–188 |
  | Ch. IV «مسلمانوں کا تنزل» | 189–232 |
  | Ch. V «مغربی عہد» | 233–334 |
  | Ch. VI «معنوی خسارے» | 335–382 |
  | Ch. VII «عالمِ اسلام زندگی کے میدان میں» | 383–427 |
  | Ch. VIII «عالمِ عربی کی قیادت» | 427–450 |

- **Plan:** a 12–15 minute documentary built on the arc darkness → light → leadership → decline → real loss → hope. It has 6 sections. Each section combines:
  - the presenter in the library studio,
  - one on-screen quote with its Urdu page number,
  - a map or timeline.
- **Workflow:**
  1. Read one chapter at a time.
  2. Save notes to `book-notes/` in the repo. Keep them as summaries with page numbers, and only short quotes.
  3. Write the script.
  4. The user approves the script.
  5. Record and edit.
- **Verify with the user:**
  - «الحکمة ضالة المؤمن» (p. 220): the book gives no reference, and it is weak.
  - The Abu Raja report (pp. 69–70) is a Companion's statement.
  - p. 37 says "sixth century" but p. 98 says "seventh century".
  - Ruku-style verse references must be converted to ayah numbers.
