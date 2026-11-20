# Pakistani religious media: editing patterns to borrow

Studied in Nov 2026 from frames of recent shorts:
- JTR Media House / JTR Media Official (2 shorts the user sent, plus 6 more)
- DawateIslami
- Mufti Tariq Masood clip channels
- Dr. Ammar Khan Nasir / Ammar Khan Yasir results

YouTube blocks video downloads from this environment, so the study used YouTube's sampled frames (`i.ytimg.com/vi/<id>/maxres1..3.jpg`), not full playback. To study a short in motion, ask the user to put the file on Google Drive.

## What the top channels do

| Pattern | Who | How we do it (`brand/make_reel.py`) |
|---|---|---|
| Channel logo always in the top-left corner, small | JTR, DawateIslami, Tariq Masood clips | `draw_logo`, using the gold calligraphy logo |
| Countdown timer pill, red dot, top-right ("00:01:45") | JTR, DawateIslami short films | `draw_timer`, plus a thin progress line at the bottom |
| Footer strip with social icons, handle and website | JTR templates | `draw_strip`, gold icons, handle and name |
| ONE big bold word over the speaker's chest (Naskh bold, white, heavy soft shadow) | JTR ("نوجوان"), DawateIslami ("UNCLE,") | `type: bold` (Noto Naskh Arabic Bold); yellow for the key word |
| The same word huge and faded in the background, behind the speaker | DawateIslami ("SOME MONEY"), JTR | `type: bgword`, painted between the room and the presenter |
| Grade shift on an emotional line: B&W or desaturated, smoke, warm/red light | JTR Khawarij series, Tariq Masood clips | `type: grade` (mono) for the span |
| Cutaway visuals while the voice continues | all | `type: broll`, aniconic visuals from `brand/broll.py`, full-screen with a caption or as a picture-in-picture card |
| Header template: question headline band, Arabic text, red arrow | Tariq Masood Q&A clips | not in reels by default; the user rejected the "frame" layout. Use only for masail Q&A |
| Big bilingual cover text: yellow and red block letters, Urdu headline on a band | JTR covers | `brand/make_thumb_bold.py` |
| Simple marks: yellow ✗ / ✓ pops for right and wrong | JTR quiz | the `pill` check marks; ✗ can be added the same way |
| Tight speech, no "umm" or repeated words | all | `subclips` keeps 0.16 s per pause; remove repeated phrases by hand in the plan |

## House rules that still apply
- Nothing that shows people other than the presenter: no stock people, no AI faces. B-roll is light, nature, objects, geometry and architecture only.
- Quran and Hadith text on cards must be exact, with the reference. If the recitation is unsure, mute the voice and show the card.
- Background nasheed only when the user supplies it. Keep it about 17 dB under the voice, ducked further while he speaks (`NASHEED=path`).
- The presenter's face is never altered. The chair stays: key only the green screen.
