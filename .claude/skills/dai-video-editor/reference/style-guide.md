# Dai Studio style guide

## A. Who we edit like

These are the reference points the user named. They describe a *style direction*, not footage to copy.
Never reuse anyone's logo, intro, music or graphics.

| Reference | What we take from it | Preset |
|---|---|---|
| **JTR Media / Jamia-tur-Rasheed Karachi** (institutional Islamic media) | dark cinematic palette, gold accents, calligraphic Arabic cards for ayat/ahadith, clean lower-thirds, slow and dignified motion, high audio quality | `jtr-cinematic` |
| **Maulana Wahiduddin Khan** style talks (CPS) | calm, intellectual, minimal: light backgrounds, few cuts, boxed readable captions, no flashy motion | `calm-scholar` |
| **Popular Islamic reel studios** (TikTok / Shorts / Instagram) | strong hook in the first 2 s, punch-in jump cuts, big word-highlighted captions, keyword pops, progress bar, tight pacing | `reel-dynamic` |
| Classical bayan / Juma clips | maroon and gold, long-form friendly | `maroon-classic` |

**The balance:** attractive (جاذبِ نظر) but **sanjeeda**. The scholar must always look like a respected da'i,
never like an entertainer. When unsure, choose the calmer option.

## B. Editing craft (what makes it look professional)

1. **The first 3 seconds decide everything** (reels). Start on a complete, strong sentence, not on "السلام علیکم… تو آج…".
   If the greeting is long, trim it to the greeting alone. The headline must state the topic immediately.
2. **Pacing.** Remove dead air, but keep natural breaths. Cutting the gaps between words makes the speaker look robotic.
   Merge gaps shorter than 0.3 s.
3. **Jump cuts with intent.** Every cut changes the framing (zoom 1.0 ↔ 1.12–1.25). Two consecutive segments must
   never have the same zoom.
4. **Motion with restraint.** Use a slow push-in for the emotional peak. No shakes, glitches, spins or flashy
   transitions. Fades, wipes and gentle scale are the whole vocabulary.
5. **Text hierarchy.** Headline > Arabic of the hadith/ayah > translation > captions > reference / handle.
   Use one accent colour (gold) and at most two typefaces visible at the same time.
6. **Safe areas (reels).** Keep text out of the bottom 12% and the right-hand 10% (TikTok/Instagram UI). The engine's
   layouts already respect this. Don't override it with extreme `y` values.
7. **Audio is half the video.** Denoise, de-ess, compress, then normalise to -14 LUFS. A clean voice reads as
   "professional" more than any animation does.
8. **Consistency.** One style per channel. Use the brand file's style unless the user asks otherwise.

## C. Islamic content rules (binding)

1. **Never alter meaning.** Do not cut words like "نہیں" or "مگر", or conditions and exceptions, in a way that changes the ruling
   or the message. When in doubt, keep the sentence whole.
2. **Quran and Hadith text must be exact.** Use only text the speaker recited or text you know verbatim. Never
   invent references, hadith numbers or gradings. List anything uncertain under "please verify".
   Do not put word-by-word karaoke highlight on Quranic Arabic. Quote cards fade the whole text in gently.
3. **Do not cut inside recitation** or a durood, and do not place a caption over the Arabic card.
4. **Music: off by default.** Many scholars avoid instrumental music. Use only what the user explicitly supplies
   (e.g. a vocal-only nasheed or ambience) and keep it low and ducked under the voice.
5. **Aniconic visuals.** Generated backgrounds are geometric patterns, light and colour only, with no living beings.
   For b-roll, prefer masjid, nature, sky, calligraphy, books. Avoid inappropriate imagery.
6. **No misleading hooks.** Titles and headlines must reflect what was actually said. No shock or clickbait.
7. **Respectful honorifics in captions:** write صلی اللہ علیہ وسلم (or ﷺ), رضی اللہ عنہ / عنہا, رحمہ اللہ.
   Spell Allah's names correctly.

## D. Style presets (presets/styles.json)

Each preset sets the background (gradient colours, pattern colour and opacity, particles), the accent colour, caption
behaviour (size, highlight, pop, box), the colour grade, the zoom cycle, the speaker card border/radius and the progress
bar. To create a custom channel look, copy a preset under a new key and change the colours. Keep
`pattern_opacity` between 0.06 and 0.14 so the pattern stays a texture, not a distraction.
