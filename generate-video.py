#!/usr/bin/env python3
"""generate-video.py — Convert HTML slides + narration JSON into MP4 with subtitles.

Usage:
    python3 generate-video.py presentation.html script.json [-o output.mp4]

Requires: edge-tts, ffmpeg, node+playwright (npx)
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, textwrap, time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ── Helpers ──────────────────────────────────────────────────
def info(msg): print(f"\033[0;36mℹ\033[0m {msg}")
def ok(msg):   print(f"\033[0;32m✓\033[0m {msg}")
def err(msg):  print(f"\033[0;31m✗\033[0m {msg}", file=sys.stderr)

def run(cmd, **kw):
    """Run a shell command, fail with stderr on error."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        err(f"Command failed: {cmd}\n{r.stderr.strip()}")
        sys.exit(1)
    return r.stdout.strip()

def check_deps():
    for tool, check in [("ffmpeg", "ffmpeg -version"), ("ffprobe", "ffprobe -version"),
                        ("node", "node --version"), ("npx", "npx --version"),
                        ("edge-tts", "python3 -c 'import edge_tts'")]:
        try:
            subprocess.run(check, shell=True, capture_output=True, check=True)
        except Exception:
            err(f"Missing dependency: {tool}"); sys.exit(1)
    ok("All dependencies found")

def get_duration(audio_path):
    """Get audio duration in seconds via ffprobe."""
    out = run(f'ffprobe -v quiet -show_entries format=duration -of csv=p=0 "{audio_path}"')
    return float(out)

# ── Step 1: TTS ──────────────────────────────────────────────
def generate_tts(slides, voice, tmp_dir, speed=1.0):
    """Generate MP3 + SRT for each slide narration."""
    info(f"Generating TTS audio...{f' (speed: {speed}x)' if speed != 1.0 else ''}")
    results = []
    for i, slide in enumerate(slides):
        narration = slide.get("narration", "").strip()
        prefix = os.path.join(tmp_dir, f"slide_{i+1:03d}")
        mp3 = prefix + ".mp3"
        srt = prefix + ".srt"

        if not narration:
            run(f'ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=mono -t 2 -q:a 9 "{mp3}"')
            duration = 2.0
            Path(srt).write_text("")
        else:
            txt_file = prefix + ".txt"
            Path(txt_file).write_text(narration, encoding="utf-8")
            raw_mp3 = prefix + "_raw.mp3" if speed != 1.0 else mp3
            cmd = f'python3 -m edge_tts --voice "{voice}" -f "{txt_file}" --write-media "{raw_mp3}" --write-subtitles "{srt}"'
            # Retry up to 3 times (edge-tts can fail transiently)
            for attempt in range(3):
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if r.returncode == 0:
                    break
                if attempt < 2:
                    time.sleep(2)
            else:
                err(f"TTS failed for slide {i+1} after 3 attempts:\n{r.stderr.strip()}")
                sys.exit(1)
            # Speed up audio with ffmpeg atempo if needed
            if speed != 1.0:
                run(f'ffmpeg -y -i "{raw_mp3}" -filter:a "atempo={speed}" "{mp3}"')
                # Adjust SRT timestamps by speed factor
                _adjust_srt_speed(srt, speed)
            duration = get_duration(mp3)

        results.append({"mp3": mp3, "srt": srt, "duration": duration})
        ok(f"  Slide {i+1}: {duration:.1f}s")
    return results

def _adjust_srt_speed(srt_path, speed):
    """Adjust SRT timestamps by dividing all times by speed factor."""
    content = Path(srt_path).read_text(encoding="utf-8")
    pattern = re.compile(r'(\d{2}:\d{2}:\d{2}[.,]\d{3})')
    def adjust(m):
        t = ts_to_sec(m.group(1))
        t /= speed
        return sec_to_srt_ts(t)
    content = pattern.sub(adjust, content)
    Path(srt_path).write_text(content, encoding="utf-8")

# ── Step 2: Screenshots ─────────────────────────────────────
CAPTURE_SCRIPT = r"""
import { chromium } from 'playwright';
import { createServer } from 'http';
import { readFileSync, mkdirSync } from 'fs';
import { join, extname } from 'path';

const SERVE_DIR = process.argv[2];
const HTML_FILE = process.argv[3];
const OUT_DIR   = process.argv[4];
const VP_W = parseInt(process.argv[5]) || 1920;
const VP_H = parseInt(process.argv[6]) || 1080;

const MIME = {'.html':'text/html','.css':'text/css','.js':'application/javascript',
  '.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.gif':'image/gif',
  '.svg':'image/svg+xml','.webp':'image/webp','.woff':'font/woff','.woff2':'font/woff2'};

const server = createServer((req, res) => {
  let fp = join(SERVE_DIR, decodeURIComponent(req.url) === '/' ? HTML_FILE : decodeURIComponent(req.url));
  try { const c = readFileSync(fp); res.writeHead(200, {'Content-Type': MIME[extname(fp).toLowerCase()] || 'application/octet-stream'}); res.end(c); }
  catch { res.writeHead(404); res.end('Not found'); }
});
const port = await new Promise(r => server.listen(0, () => r(server.address().port)));

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: VP_W, height: VP_H } });
await page.goto(`http://localhost:${port}/`, { waitUntil: 'networkidle' });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(1500);

const count = await page.evaluate(() => document.querySelectorAll('.slide').length);
console.log(count);
mkdirSync(OUT_DIR, { recursive: true });

for (let i = 0; i < count; i++) {
  await page.evaluate((idx) => {
    const slides = document.querySelectorAll('.slide');
    slides.forEach((s, j) => {
      if (j === idx) { s.style.display=''; s.style.opacity='1'; s.style.visibility='visible'; s.style.position='relative'; s.style.transform='none'; s.classList.add('active','visible'); }
      else { s.style.display='none'; s.classList.remove('active','visible'); }
    });
    const cur = slides[idx];
    if (cur) cur.querySelectorAll('.reveal').forEach(el => { el.style.opacity='1'; el.style.transform='none'; el.style.visibility='visible'; });
    slides[idx]?.scrollIntoView({ behavior: 'instant' });
  }, i);
  await page.waitForTimeout(500);
  await page.screenshot({ path: join(OUT_DIR, `slide_${String(i+1).padStart(3,'0')}.png`), fullPage: false });
}
await browser.close(); server.close();
"""

def capture_slides(html_path, tmp_dir, resolution="1920x1080"):
    """Screenshot each slide using Node.js Playwright."""
    info("Capturing slide screenshots...")
    w, h = resolution.split("x")
    serve_dir = str(Path(html_path).parent)
    html_name = Path(html_path).name
    shot_dir = os.path.join(tmp_dir, "screenshots")

    # Write Node script + package.json
    node_dir = os.path.join(tmp_dir, "node_capture")
    os.makedirs(node_dir, exist_ok=True)
    Path(os.path.join(node_dir, "capture.mjs")).write_text(CAPTURE_SCRIPT)
    Path(os.path.join(node_dir, "package.json")).write_text('{"name":"cap","private":true,"type":"module"}')

    # Install playwright
    info("  Installing Playwright (first run may be slow)...")
    run(f'cd "{node_dir}" && npm install playwright 2>/dev/null')
    run(f'cd "{node_dir}" && npx playwright install chromium 2>/dev/null')

    # Run capture
    result = run(f'cd "{node_dir}" && node capture.mjs "{serve_dir}" "{html_name}" "{shot_dir}" {w} {h}')
    count = int(result.strip().split("\n")[0])
    ok(f"  Captured {count} slides")

    pngs = sorted(Path(shot_dir).glob("slide_*.png"))
    return [str(p) for p in pngs]

# ── Step 3: Subtitle merging ────────────────────────────────
def parse_vtt_to_cues(srt_path):
    """Parse edge-tts generated VTT/SRT into list of (start_sec, end_sec, text)."""
    content = Path(srt_path).read_text(encoding="utf-8").strip()
    if not content:
        return []
    cues = []
    # edge-tts outputs SRT with comma decimals: HH:MM:SS,mmm --> HH:MM:SS,mmm
    # Also handle VTT dot decimals: HH:MM:SS.mmm --> HH:MM:SS.mmm
    pattern = re.compile(r'(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})')
    blocks = re.split(r'\n\s*\n', content)
    for block in blocks:
        lines = block.strip().split('\n')
        for j, line in enumerate(lines):
            m = pattern.search(line)
            if m:
                start = ts_to_sec(m.group(1))
                end = ts_to_sec(m.group(2))
                text = ' '.join(l.strip() for l in lines[j+1:] if l.strip() and not l.strip().isdigit())
                if text:
                    cues.append((start, end, text))
    return cues

def ts_to_sec(ts):
    """Convert HH:MM:SS.mmm to seconds."""
    parts = ts.replace(',', '.').split(':')
    return int(parts[0])*3600 + int(parts[1])*60 + float(parts[2])

def sec_to_srt_ts(s):
    """Convert seconds to SRT timestamp HH:MM:SS,mmm."""
    h = int(s // 3600); s %= 3600
    m = int(s // 60); s %= 60
    sec = int(s); ms = int((s - sec) * 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

def merge_subtitles(tts_results, padding):
    """Merge per-slide VTT cues into one SRT string with proper time offsets."""
    merged = []
    offset = 0.0
    for res in tts_results:
        cues = parse_vtt_to_cues(res["srt"])
        for start, end, text in cues:
            merged.append((start + offset, end + offset, text))
        offset += res["duration"] + padding

    # Group consecutive cues into sentence-level blocks for readability
    grouped = group_cues(merged)

    srt_lines = []
    for i, (start, end, text) in enumerate(grouped, 1):
        # Wrap long lines
        wrapped = textwrap.fill(text, width=55)
        srt_lines.append(f"{i}\n{sec_to_srt_ts(start)} --> {sec_to_srt_ts(end)}\n{wrapped}\n")
    return "\n".join(srt_lines)

def group_cues(cues, max_chars=55, max_gap=0.3):
    """Group word-level cues into sentence-level blocks."""
    if not cues:
        return []
    grouped = []
    cur_start, cur_end, cur_text = cues[0]
    for start, end, text in cues[1:]:
        gap = start - cur_end
        if gap < max_gap and len(cur_text) + len(text) + 1 <= max_chars:
            cur_text += " " + text
            cur_end = end
        else:
            grouped.append((cur_start, cur_end, cur_text))
            cur_start, cur_end, cur_text = start, end, text
    grouped.append((cur_start, cur_end, cur_text))
    return grouped

# ── Step 4: Audio concatenation ──────────────────────────────
def concat_audio(tts_results, padding, tmp_dir):
    """Concatenate slide audio files with silence padding between them."""
    info("Concatenating audio...")
    # Generate silence file
    silence = os.path.join(tmp_dir, "silence.mp3")
    run(f'ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=mono -t {padding} -q:a 9 "{silence}"')

    # Build concat list
    list_file = os.path.join(tmp_dir, "audio_list.txt")
    lines = []
    for i, res in enumerate(tts_results):
        lines.append(f"file '{res['mp3']}'")
        if i < len(tts_results) - 1:
            lines.append(f"file '{silence}'")
    Path(list_file).write_text("\n".join(lines))

    combined = os.path.join(tmp_dir, "combined.mp3")
    run(f'ffmpeg -y -f concat -safe 0 -i "{list_file}" -c copy "{combined}"')
    ok(f"  Combined audio: {get_duration(combined):.1f}s")
    return combined

# ── Step 5: Burn subtitles into images (Pillow) ─────────────
def get_font(size):
    """Get a font, falling back to default if needed."""
    for name in ["/System/Library/Fonts/Helvetica.ttc",
                 "/System/Library/Fonts/SFNSText.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if os.path.exists(name):
            try: return ImageFont.truetype(name, size)
            except: pass
    return ImageFont.load_default()

def burn_subtitle_on_image(png_path, text, font_size, out_path):
    """Burn subtitle text onto bottom of slide image using Pillow."""
    img = Image.open(png_path).convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = get_font(font_size)

    # Wrap text
    wrapped = textwrap.fill(text, width=60)
    lines = wrapped.split("\n")

    # Measure text block
    line_heights = []
    line_widths = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])
    total_h = sum(line_heights) + (len(lines) - 1) * 6
    max_w = max(line_widths) if line_widths else 0

    # Draw semi-transparent background bar
    margin_v = int(h * 0.04)
    pad_x, pad_y = 24, 12
    bar_x0 = (w - max_w) // 2 - pad_x
    bar_y0 = h - margin_v - total_h - pad_y
    bar_x1 = (w + max_w) // 2 + pad_x
    bar_y1 = h - margin_v + pad_y
    draw.rounded_rectangle([bar_x0, bar_y0, bar_x1, bar_y1], radius=10, fill=(0, 0, 0, 160))

    # Draw text lines centered
    y = bar_y0 + pad_y
    for i, line in enumerate(lines):
        lw = line_widths[i]
        x = (w - lw) // 2
        # Outline
        for dx in [-2, -1, 0, 1, 2]:
            for dy in [-2, -1, 0, 1, 2]:
                if dx or dy:
                    draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 255))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_heights[i] + 6

    result = Image.alpha_composite(img, overlay).convert("RGB")
    result.save(out_path, "PNG")

def build_subtitle_frames(pngs, tts_results, padding, tmp_dir, font_size, no_subtitles):
    """Build frame sequence: for each time segment, an image (with or without subtitle)."""
    info("Building subtitle frames...")
    frames_dir = os.path.join(tmp_dir, "sub_frames")
    os.makedirs(frames_dir, exist_ok=True)

    # Parse all cues with global time offsets
    all_cues = []
    offset = 0.0
    for i, res in enumerate(tts_results):
        cues = parse_vtt_to_cues(res["srt"])
        grouped = group_cues(cues)
        for start, end, text in grouped:
            all_cues.append((start + offset, end + offset, text, i))
        offset += res["duration"] + padding

    concat_entries = []
    frame_idx = 0
    offset = 0.0

    for i, (png, res) in enumerate(zip(pngs, tts_results)):
        slide_start = offset
        slide_end = offset + res["duration"] + padding

        if no_subtitles or not all_cues:
            # No subtitles: just use original image for full duration
            concat_entries.append((png, res["duration"] + padding))
            offset = slide_end
            continue

        # Get cues for this slide
        slide_cues = [(s, e, t) for s, e, t, si in all_cues if si == i]

        if not slide_cues:
            concat_entries.append((png, res["duration"] + padding))
            offset = slide_end
            continue

        # Build time segments within this slide
        boundaries = sorted(set(
            [0.0] + [c[0] - slide_start for c in slide_cues] +
            [c[1] - slide_start for c in slide_cues] +
            [res["duration"] + padding]
        ))

        for k in range(len(boundaries) - 1):
            seg_start = boundaries[k]
            seg_end = boundaries[k + 1]
            seg_dur = seg_end - seg_start
            if seg_dur < 0.01:
                continue

            abs_mid = slide_start + (seg_start + seg_end) / 2
            active = next((t for s, e, t in slide_cues if s <= abs_mid - slide_start + 0.01 and abs_mid - slide_start - 0.01 < e), None)

            if active:
                out_path = os.path.join(frames_dir, f"frame_{frame_idx:05d}.png")
                burn_subtitle_on_image(png, active, font_size, out_path)
                concat_entries.append((out_path, seg_dur))
            else:
                concat_entries.append((png, seg_dur))
            frame_idx += 1

        offset = slide_end

    ok(f"  {frame_idx} subtitle frames generated")
    return concat_entries

# ── Step 6: Final assembly ───────────────────────────────────
def assemble_video(concat_entries, combined_audio, output, tmp_dir):
    """Assemble final MP4 from image sequence + audio."""
    info("Assembling video...")

    slides_file = os.path.join(tmp_dir, "slides.txt")
    lines = []
    for img_path, dur in concat_entries:
        lines.append(f"file '{img_path}'")
        lines.append(f"duration {dur:.3f}")
    # Repeat last entry (ffmpeg concat demuxer quirk)
    lines.append(f"file '{concat_entries[-1][0]}'")
    Path(slides_file).write_text("\n".join(lines))

    cmd = (
        f'ffmpeg -y -f concat -safe 0 -i "{slides_file}" -i "{combined_audio}" '
        f'-vf "fps=30" '
        f'-c:v libx264 -pix_fmt yuv420p -r 30 -c:a aac -b:a 192k '
        f'-shortest -movflags +faststart "{output}"'
    )
    run(cmd)
    ok(f"  Video saved: {output}")

# ── Main ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Convert HTML slides + narration to MP4 video")
    parser.add_argument("html", help="Path to HTML presentation")
    parser.add_argument("script", help="Path to narration JSON")
    parser.add_argument("-o", "--output", help="Output MP4 path")
    parser.add_argument("--padding", type=float, default=1.5, help="Seconds of silence between slides (default: 1.5)")
    parser.add_argument("--font-size", type=int, default=22, help="Subtitle font size (default: 22)")
    parser.add_argument("--resolution", default="1920x1080", help="Video resolution (default: 1920x1080)")
    parser.add_argument("--no-subtitles", action="store_true", help="Skip subtitle burn-in")
    parser.add_argument("--speed", type=float, default=1.0, help="TTS speech speed multiplier (default: 1.0, e.g. 1.5 for 1.5x)")
    parser.add_argument("--assets-only", action="store_true", help="Only generate voiceover MP3 + SRT, skip video assembly")
    args = parser.parse_args()

    # Validate inputs
    html_path = str(Path(args.html).resolve())
    if not os.path.isfile(html_path):
        err(f"HTML file not found: {html_path}"); sys.exit(1)

    script_path = str(Path(args.script).resolve())
    if not os.path.isfile(script_path):
        err(f"Script file not found: {script_path}"); sys.exit(1)

    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    voice = script_data.get("voice", "en-US-AriaNeural")
    slides = script_data.get("slides", [])
    if not slides:
        err("No slides in script JSON"); sys.exit(1)

    output = args.output or str(Path(html_path).with_suffix("")) + "_video.mp4"
    output = str(Path(output).resolve())

    print()
    print("\033[1m╔══════════════════════════════════════╗\033[0m")
    print("\033[1m║    Infographic → Video Pipeline      ║\033[0m")
    print("\033[1m╚══════════════════════════════════════╝\033[0m")
    print()

    check_deps()
    tmp_dir = tempfile.mkdtemp(prefix="infographic_video_")
    try:
        # Step 1: TTS
        tts_results = generate_tts(slides, voice, tmp_dir, args.speed)

        # Step 2: Audio concatenation
        combined_audio = concat_audio(tts_results, args.padding, tmp_dir)

        # Step 3: Merge subtitles
        info("Merging subtitles...")
        srt_content = merge_subtitles(tts_results, args.padding)
        ok("  Subtitles merged")

        if args.assets_only:
            # Assets-only mode: copy MP3 + SRT to output directory
            out_dir = str(Path(html_path).parent)
            mp3_out = os.path.join(out_dir, "voiceover.mp3")
            srt_out = os.path.join(out_dir, "subtitles.srt")
            shutil.copy2(combined_audio, mp3_out)
            Path(srt_out).write_text(srt_content, encoding="utf-8")

            total = sum(r['duration'] for r in tts_results) + args.padding * (len(tts_results) - 1)
            print()
            print("\033[1m════════════════════════════════════════\033[0m")
            ok("Assets generated successfully!")
            print(f"  Voiceover: {mp3_out}")
            print(f"  Subtitles: {srt_out}")
            print(f"  HTML:      {html_path}")
            print(f"  Duration:  {total:.0f}s ({len(tts_results)} slides)")
            print("\033[1m════════════════════════════════════════\033[0m")
            print()
        else:
            # Full video mode
            # Step 4: Screenshots
            pngs = capture_slides(html_path, tmp_dir, args.resolution)

            slide_count = min(len(pngs), len(tts_results))
            if len(pngs) != len(tts_results):
                info(f"  Warning: {len(pngs)} slides captured, {len(tts_results)} narrations. Using first {slide_count}.")
            pngs = pngs[:slide_count]
            tts_results = tts_results[:slide_count]

            # Step 5: Subtitle frames (Pillow-based burn-in)
            concat_entries = build_subtitle_frames(
                pngs, tts_results, args.padding, tmp_dir,
                args.font_size, args.no_subtitles)

            # Step 6: Assemble
            assemble_video(concat_entries, combined_audio, output, tmp_dir)

            print()
            print("\033[1m════════════════════════════════════════\033[0m")
            ok("Video generated successfully!")
            size = os.path.getsize(output) / (1024*1024)
            print(f"  File: {output}")
            print(f"  Size: {size:.1f} MB")
            total = sum(r['duration'] for r in tts_results) + args.padding * (len(tts_results) - 1)
            print(f"  Duration: {total:.0f}s ({len(tts_results)} slides)")
            print("\033[1m════════════════════════════════════════\033[0m")
            print()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
