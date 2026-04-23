# Infographic to Video

A Claude Code skill that converts **infographics, articles, or video scripts** into narrated MP4 videos with AI voiceover and burned-in subtitles.

## What This Does

You give Claude an infographic image, an article, or a video script, and it automatically:

1. **Reads your input** — extracts content from images, text, or URLs
2. **Writes a narration script** — conversational, educational voiceover (not just reading the text)
3. **Generates HTML slides** — using [frontend-slides](https://github.com/zarazhangrui/frontend-slides) for stunning visuals
4. **Produces AI voiceover** — via Edge TTS (free, no API key needed)
5. **Burns in subtitles** — word-level timing, rendered with Pillow
6. **Assembles the final MP4** — with ffmpeg

The entire pipeline runs locally. No cloud APIs, no costs.

## Demo

Input: an infographic about options trading strategies

Output: a 4-minute narrated video with slides, voiceover, and subtitles

## Installation

```bash
git clone https://github.com/ftcalvinwang-ai/info-to-video.git ~/.claude/skills/info-to-video
```

Then use it by typing `/info-to-video` in Claude Code.

## Requirements

- [Claude Code](https://claude.ai/claude-code) CLI
- Python 3.9+ with `edge-tts` and `Pillow`
- Node.js (for Playwright screenshots)
- ffmpeg

### Install dependencies

```bash
pip3 install edge-tts Pillow
brew install ffmpeg  # macOS
```

Playwright is installed automatically on first run (via npm in a temp directory).

## Usage

### Via Claude Code (Recommended)

```
/info-to-video
```

Then follow the prompts — share your infographic, confirm the script, choose a voice, and get your video.

### Standalone Script

You can also use `generate-video.py` directly if you already have HTML slides and a narration JSON:

```bash
python3 generate-video.py presentation.html script.json -o output.mp4
```

**script.json format:**

```json
{
  "voice": "en-US-AndrewMultilingualNeural",
  "slides": [
    { "narration": "Text spoken during slide 1..." },
    { "narration": "Text spoken during slide 2..." }
  ]
}
```

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `-o, --output` | `{html}_video.mp4` | Output MP4 path |
| `--padding` | `1.5` | Seconds of silence between slides |
| `--font-size` | `36` | Subtitle font size |
| `--resolution` | `1920x1080` | Video resolution |
| `--no-subtitles` | `false` | Skip subtitle burn-in |

## Available Voices

### English

| Voice | Gender | Vibe |
|-------|--------|------|
| en-US-AndrewMultilingualNeural | Male | Warm, confident, authentic |
| en-US-BrianMultilingualNeural | Male | Approachable, casual |
| en-US-AvaMultilingualNeural | Female | Expressive, friendly |
| en-US-EmmaMultilingualNeural | Female | Cheerful, conversational |
| en-US-GuyNeural | Male | Passionate, energetic |

### Chinese

| Voice | Gender | Vibe |
|-------|--------|------|
| zh-CN-YunxiNeural | Male | Lively, natural |
| zh-CN-YunyangNeural | Male | Professional, reliable |
| zh-CN-XiaoxiaoNeural | Female | Warm |

## How It Works

1. **Edge TTS** generates MP3 audio + SRT subtitles with word-level timing for each slide
2. **Playwright** (Node.js) screenshots each `.slide` element at 1920x1080 via a local HTTP server
3. **Pillow** burns subtitle text onto slide images with semi-transparent background bars
4. **ffmpeg** assembles the image sequence + concatenated audio into the final MP4

Subtitles are burned into images (not via ffmpeg's `subtitles` filter) so it works with any ffmpeg build — no `libass` required.

## Architecture

```
SKILL.md              — Skill definition (workflow for Claude Code)
generate-video.py     — Video generation pipeline (~400 lines)
README.md             — This file
```

## Credits

Built with [Claude Code](https://claude.ai/claude-code). Uses [frontend-slides](https://github.com/zarazhangrui/frontend-slides) for HTML slide generation.

## License

MIT
