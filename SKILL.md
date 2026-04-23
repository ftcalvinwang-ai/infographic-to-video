---
name: info-to-video
description: Convert an infographic, article, or video script into a narrated video with AI voiceover and subtitles. Orchestrates the full pipeline — read input, write narration, generate HTML slides (via frontend-slides), then produce MP4 with Edge TTS voiceover and burned-in subtitles.
---

# Infographic to Video

Convert infographics, articles, or video scripts into narrated MP4 videos with AI voiceover and subtitles.

## Workflow

### Phase 1: Collect Input

Ask the user what kind of input they have, using AskUserQuestion:

**Question** (header: "Input Type"):
What would you like to turn into a video?

Options:
- **Infographic image** — "I have an infographic image to share"
- **Article / text** — "I have an article, blog post, or text content"
- **Video script** — "I already have a written video script / narration"
- **YouTube link** — "I have a YouTube video URL"

Then based on their choice:

- **Infographic:** Ask the user to share the image. Use the Read tool to view it.
- **Article / text:** Ask the user to share the text (paste it, or provide a file path / URL). If a URL, use WebFetch to retrieve it. If a file path, use Read.
- **Video script:** Ask the user to share the script. This can go almost directly to narration (Phase 2 step 3), but still needs slide structure design.
- **YouTube link:** Ask the user to paste the YouTube URL. Then run the extraction script:
  ```bash
  python3 ~/.claude/skills/info-to-video/extract-youtube.py "<url>" -o /tmp/yt_transcript.json
  ```
  Read the output JSON. If extraction fails (no subtitles and no whisper), ask the user if they want to try with whisper (`--whisper-model base`). Present the video title and a summary of the extracted transcript to the user for confirmation before proceeding.

### Phase 2: Read & Script

**Step 1 & 2 depend on input type:**

#### If Infographic:
1. **Read the infographic** — Extract ALL text, data, structure, and visual flow from the image.
2. **Design slide structure** — Map the infographic sections to slides (typically 8-12 slides). Follow the same content structure as the original infographic.

#### If Article / Text:
1. **Analyze the article** — Identify the core thesis, key arguments, supporting data, and conclusion. Understand the logical flow.
2. **Design slide structure** — Break the article into 8-12 slide-sized chunks. Each slide should cover ONE key idea. Don't try to include everything — distill the most important and interesting points. Create a compelling narrative arc: hook → context → key points → conclusion.

#### If YouTube Link:
1. **Read the transcript** — The extracted transcript is raw speech (auto-captions or whisper output). It will contain filler words, repetition, incomplete sentences, and no structure. Clean it up mentally before designing slides.
2. **Design slide structure** — Identify the core topics and key points from the transcript. Break into 8-12 slides. Ignore tangents, repetition, and filler. Focus on the most valuable and teachable content. Use the video title and description for additional context about the topic.

**YouTube-specific narration rules:**
- The transcript is a starting point, NOT the final narration. Rewrite it completely.
- Distill a 10-minute rambling video into a tight 3-4 minute narrated slide deck.
- Reorganize the content logically — the original video may jump around.
- Keep the speaker's key insights but express them more clearly and concisely.

#### If Video Script:
1. **Analyze the script** — Read the full script. Identify natural section breaks and key topics.
2. **Design slide structure** — Split the script into slides (one topic per slide). Each slide's narration should be 15-25 seconds of speech. If the user's script is too long for one slide, split it; if too short, combine sections.

**Step 3 (all input types):**

3. **Write narration script** — This is the most important step. Follow these rules:

**Narration Writing Rules (CRITICAL):**

- **DO NOT just read the infographic text aloud.** The narration should EXPLAIN and TEACH, not recite.
- **Be conversational.** Write as if you're a friend explaining the concept over coffee. Use "you", ask rhetorical questions, use transitions like "Here's the thing...", "Now imagine...", "So what does this mean?"
- **Add context and analogies.** If the infographic says "$100 → $80", the narration should say something like: "Imagine you bought a stock at a hundred dollars, but now it's dropped to eighty. That's a twenty percent loss sitting in your portfolio. Most people would just wait and hope — but there's a much smarter approach."
- **Explain WHY, not just WHAT.** Don't just state facts — help the viewer understand the reasoning behind each concept.
- **Use natural speech patterns.** Short sentences. Pauses. Emphasis words. Avoid jargon without explanation.
- **Each slide: 3-5 sentences, 15-25 seconds of speech.** This gives the viewer time to absorb both the visual and the audio.
- **Opening slide should hook.** Start with a question or bold statement, not "Welcome to this presentation."
- **Closing slide should motivate.** End with a clear takeaway and call to action.

**Example — BAD (just reading the infographic):**
> "Bought at 100 dollars, current price 80 dollars. Goal: recover losses and reduce cost basis."

**Example — GOOD (explaining and teaching):**
> "Picture this: you bought a stock at a hundred dollars, feeling confident. But then it dropped to eighty. Now you're staring at a twenty percent loss. Most investors would just sit there and hope it bounces back. But what if I told you there's a strategy that lets you get paid while you wait — and actually lowers the price you need to break even?"

### Phase 3: Confirm with User

Present the following for user confirmation using AskUserQuestion:

**Show the full script** as a numbered list:
```
Slide 1 — [Title]: "narration text..."
Slide 2 — [Section]: "narration text..."
...
```

**Ask these questions in a single AskUserQuestion call:**

1. **Script confirmation** (header: "Script"): Does this narration script look good? Options: Looks good / Needs changes

2. **Language** (header: "Language"): What language for voiceover and subtitles? Options: English / Chinese / Other

3. **Style** (header: "Style"): Which visual style for the slides? Options: Neon Cyber (Recommended) / Bold Signal / Creative Voltage / Show me options
   - If "Show me options", defer to frontend-slides Phase 2 style discovery

If the user wants changes, iterate until confirmed.

### Phase 4: Select Voice

Based on language choice, present voice options using AskUserQuestion.

**English voices:**

| Voice | Gender | Vibe | Best For |
|-------|--------|------|----------|
| en-US-AndrewMultilingualNeural | Male | Warm, confident, authentic | Teaching, explainers (Recommended) |
| en-US-BrianMultilingualNeural | Male | Approachable, casual, sincere | Casual tutorials |
| en-US-AvaMultilingualNeural | Female | Expressive, caring, friendly | Storytelling, engaging content |
| en-US-EmmaMultilingualNeural | Female | Cheerful, clear, conversational | Upbeat explainers |
| en-US-AriaNeural | Female | Positive, confident | News-style narration |
| en-US-GuyNeural | Male | Passionate, energetic | Motivational content |
| en-US-ChristopherNeural | Male | Reliable, authoritative | Professional, formal |

**Chinese voices:**

| Voice | Gender | Vibe | Best For |
|-------|--------|------|----------|
| zh-CN-YunxiNeural | Male | Lively, sunshine | Teaching, casual (Recommended) |
| zh-CN-YunyangNeural | Male | Professional, reliable | News-style, formal |
| zh-CN-YunjianNeural | Male | Passionate, energetic | Sports, motivational |
| zh-CN-XiaoxiaoNeural | Female | Warm | General purpose |
| zh-CN-XiaoyiNeural | Female | Lively | Casual, youthful |

**Use Multilingual voices when available** — they sound more natural and less robotic than standard Neural voices.

Ask the user (header: "Voice") to pick from 3-4 best options for their use case. Default to AndrewMultilingual (EN) or YunxiNeural (ZH).

### Phase 5: Generate HTML Slides

Use the **frontend-slides** skill to generate the HTML presentation:
- Pass in all the slide content from Phase 2
- Use the style chosen in Phase 3
- Save to a working directory (e.g., `~/Desktop/[topic]-slides/presentation.html`)

### Phase 6: Generate Script JSON

Create a `script.json` file alongside the HTML:

```json
{
  "voice": "en-US-AriaNeural",
  "slides": [
    { "narration": "Narration text for slide 1..." },
    { "narration": "Narration text for slide 2..." }
  ]
}
```

Save to the same directory as the HTML file.

### Phase 7: Generate Video

Run the video generation script:

```bash
python3 ~/.claude/skills/info-to-video/generate-video.py \
  <path-to-html> <path-to-script.json> \
  -o <output-path>.mp4
```

This will:
1. Generate TTS audio for each slide (Edge TTS)
2. Screenshot each slide (Playwright)
3. Merge subtitles with proper timing
4. Concatenate audio with padding
5. Assemble final MP4 with burned-in subtitles

### Phase 8: Delivery

1. Open the video: `open <output>.mp4`
2. Tell the user:
   - File location and size
   - Video duration and slide count
   - How to customize: re-run with `--padding`, `--font-size`, `--no-subtitles` flags

## Error Handling

- If `generate-video.py` fails on TTS, check that `edge-tts` is installed: `pip3 install edge-tts`
- If screenshots fail, Playwright may need chromium: `npx playwright install chromium`
- If ffmpeg fails, check it's installed: `brew install ffmpeg`

## Script Reference

**generate-video.py flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `html` | required | HTML presentation path |
| `script` | required | Narration JSON path |
| `-o` | `{html}_video.mp4` | Output MP4 path |
| `--padding` | `1.5` | Seconds of silence between slides |
| `--font-size` | `22` | Subtitle font size |
| `--resolution` | `1920x1080` | Video resolution |
| `--no-subtitles` | false | Skip subtitle burn-in |
