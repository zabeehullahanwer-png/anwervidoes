# Anwer Videos: Dai Studio 🎬

**Dai Studio** ایک Claude Code اسکل ہے جو آپ کی سادہ (raw) ویڈیو کو ایک پروفیشنل اسلامی اسٹوڈیو جیسی ایڈیٹنگ میں بدل دیتی ہے:
خاموشی اور غلطیوں کی کٹنگ، زوم کٹس، صاف آواز، کلر گریڈ، پیچھے چلتا ہوا اسلامی جیومیٹرک اینیمیشن، اردو نستعلیق / عربی کیپشنز،
حدیث و آیت کارڈز، نام کی پٹی (lower-third)، انٹرو (بسم اللہ) اور آؤٹرو۔

**Dai Studio** is a Claude Code skill that turns a raw talking-head recording into a professionally edited
Islamic video (a 9:16 reel, a 16:9 YouTube video or a 1:1 square).

## How to use / استعمال کا طریقہ

1. Install **ffmpeg** (Windows: `winget install ffmpeg`, Mac: `brew install ffmpeg`) and optionally
   `pip install faster-whisper` for automatic captions.
2. Put your raw video in `videos/raw/`.
3. Open Claude Code in this folder and say, for example:
   > `videos/raw/dars1.mp4` کی ایک بہترین ریل بنا دیں
   > or: *"Edit videos/raw/bayan.mp4 for YouTube in the calm style"*
4. Claude (as your editor) analyses, transcribes, cuts, designs the edit, previews it and renders it to `videos/edited/`.

The first time, Claude asks for your on-screen name, title and channel handle, and saves them in `dai-brand.json`.

## Styles

| Style | Look |
|---|---|
| `jtr-cinematic` | dark navy, gold, cinematic, institutional |
| `calm-scholar` | light cream, minimal, calm |
| `reel-dynamic` | emerald and gold, fast reels, word-highlighted captions |
| `maroon-classic` | maroon and gold, classical bayan |

Recording checklist (Urdu): [`RECORDING-GUIDE.md`](RECORDING-GUIDE.md).
The details are in [`.claude/skills/dai-video-editor/SKILL.md`](.claude/skills/dai-video-editor/SKILL.md).
Fonts (Amiri, Noto Nastaliq Urdu, Poppins, Hind) are bundled under the SIL Open Font License.

## Research Assistant / ریسرچ اسسٹنٹ 📚

دوسری اسکل **Muhaqqiq** (`.claude/skills/research-assistant/`) تحقیقی کام کے لیے ہے: ایم فل تھیسس سے مقالہ،
HEC (Y/X/W) اور بین الاقوامی (Scopus/WoS) جرائد کے لیے مقالات، حوالہ جات کی تصدیق، اردو و انگریزی خلاصے،
تھیسس سے سیلف پلیجرزم کی جانچ، ریویورز کو جواب، اور پی ایچ ڈی پروپوزل۔ ورک اسپیس: [`research/`](research/README.md)۔
