# Edit plan schema (`edit_plan.json`)

All times are **seconds in the raw source video**, the same clock as `transcript.json`. The renderer
maps them through the kept segments. An overlay whose span falls entirely inside a removed gap disappears.

```jsonc
{
  "source": "/abs/path/videos/raw/dars.mp4",
  "output": "/abs/path/videos/edited/dars_reel.mp4",
  "format": "reel",              // reel 1080x1920 | youtube 1920x1080 | square 1080x1080
  "layout": "frame",             // frame: speaker in a rounded gold-bordered card over the animated background
                                 // fill:  speaker fills the screen (background shows in intro/outro/cards)
                                 // keyed: green/blue-screen speaker cut out over the animated background
  "keying": {"enabled": true, "screen": "green", "color": "auto",   // auto = sampled after grading
             "similarity": 0.13, "blend": 0.05, "despill": 0.15},   // keyed layout only
  "keyed_scale": 1.0,            // keyed: speaker width as a fraction of the canvas (bottom-anchored)
  "card_aspect": "1:1",          // frame layout only: crop of the speaker card ("1:1", "4:5", "16:9", "3:4")
  "style": "jtr-cinematic",      // key in presets/styles.json
  "language": "ur",              // caption/UI script: ur | ar | hi | en
  "grade": "warm",               // none | neutral | warm | cinematic

  "segments": [                  // kept pieces, in order; everything else is cut
    {"start": 0.70, "end": 4.20, "zoom": 1.0,  "focus": [0.5, 0.40]},
    {"start": 5.40, "end": 10.2, "zoom": 1.15, "focus": [0.52, 0.38], "motion": "push", "push": 0.06}
  ],
  // zoom   : 1.0 = full frame, 1.2 = 20% punch-in
  // focus  : [x, y] 0..1 point in the source to keep centred (the face)
  // motion : "push" = slow push-in over the segment (use sparingly)

  "headline": {"text": "نیت کی اہمیت", "kicker": "درسِ حدیث"},   // reel+frame only; null to disable

  "captions": {
    "enabled": true,
    "items": [
      {"start": 0.8, "end": 2.4, "text": "السلام علیکم آج ہم",
       "words": [{"w": "السلام", "s": 0.8, "e": 1.2}, {"w": "علیکم", "s": 1.2, "e": 1.6}]}
    ]                             // "words" optional; enables word-by-word highlight
  },

  "overlays": [
    {"type": "lower_third", "at": 2.0, "duration": 5, "name": "مولانا ...", "title": "استاذِ حدیث، جامعہ ..."},

    {"type": "quote_card", "start": 6.0, "end": 11.5, "mode": "fullscreen",   // fullscreen | overlay
     "label": "حدیث",                                    // or "قرآن", "قولِ صحابی", "دعا"
     "arabic": "إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ",
     "translation": "اعمال کا دارومدار نیتوں پر ہے",
     "reference": "صحیح بخاری: 1",
     "hide_captions": true},                              // default true: captions pause under the card

    {"type": "keyword", "start": 12.0, "end": 13.4, "text": "نیت"},

    {"type": "text", "start": 20, "end": 24, "text": "تین باتیں", "kicker": "خلاصہ", "y": 0.15},

    {"type": "broll", "start": 30, "end": 34, "file": "videos/raw/masjid.jpg"}   // image (slow pan) or video; full-screen
  ],

  "intro":  {"enabled": true, "duration": 2.8, "top_text": "بِسْمِ اللّٰهِ الرَّحْمٰنِ الرَّحِيْمِ",
             "name": "مولانا ...", "subtitle": "..."},
  "outro":  {"enabled": true, "duration": 4.0, "name": "مولانا ...",
             "cta": "Subscribe • Share — صدقہ جاریہ", "handle": "@channel"},
  "watermark": {"enabled": true, "text": "@channel", "logo": ""},   // logo PNG (transparent) wins over text
  "progress_bar": false,

  "audio": {"denoise": "medium",   // off | light | medium | strong
            "loudness": -14,       // LUFS target (YouTube/TikTok/Instagram: -14)
            "music": "",           // optional user-supplied file; auto-ducked under the voice
            "music_volume": 0.07,
            "whoosh": false}       // soft swoosh at full-screen cards / b-roll
}
```

## Placement rules the renderer applies for you

* Captions are suppressed while a `quote_card` is on screen (unless `hide_captions: false`).
* A lower-third is shortened if a quote card starts while it is showing.
* RTL text (Urdu/Arabic) is laid out right to left. Mixed English/Urdu lines get the correct font per run.
* Arabic-script text in `arabic` fields uses **Amiri** (Naskh, full harakat). Urdu uses **Noto Nastaliq Urdu**.
  Latin uses **Poppins**, and Devanagari uses **Hind**.

## Good editorial values

| Item | Reel | YouTube |
|---|---|---|
| caption chunk | 3–5 words, ≤ 2.6 s | 5–7 words, ≤ 3.2 s |
| quote card | ≥ 3.5 s (Arabic needs reading time) | ≥ 4 s |
| keyword pop | 1.2–1.6 s, ≤ 1 per 15 s | rarely |
| lower-third | 4–6 s, once | once at start, optionally again mid-video |
| zoom change | at every cut | at most cuts; keep 1.0 for long stretches |
