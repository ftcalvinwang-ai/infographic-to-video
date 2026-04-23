#!/usr/bin/env python3
"""extract-youtube.py — Extract transcript from a YouTube video.

Usage:
    python3 extract-youtube.py <youtube-url> [-o output.json] [--whisper-model base]

Strategy:
    1. Try youtube-transcript-api (fast, no download)
    2. If no subtitles, fall back to yt-dlp + whisper (slower)

Output: JSON with { "title", "transcript", "language", "source" }
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path


def info(msg): print(f"\033[0;36mℹ\033[0m {msg}")
def ok(msg):   print(f"\033[0;32m✓\033[0m {msg}")
def err(msg):  print(f"\033[0;31m✗\033[0m {msg}", file=sys.stderr)


def extract_video_id(url):
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:embed/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def get_video_info(url):
    """Get video title and description via yt-dlp."""
    try:
        r = subprocess.run(
            ['python3', '-m', 'yt_dlp', '--dump-json', '--no-download', url],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode == 0:
            data = json.loads(r.stdout)
            return data.get('title', ''), data.get('description', '')
    except Exception:
        pass
    return '', ''


def try_transcript_api(video_id):
    """Tier 1: Try youtube-transcript-api for subtitles."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        # Try common languages
        for langs in [['en'], ['zh'], ['zh-Hans'], ['zh-Hant'], ['ja'], ['ko']]:
            try:
                result = api.fetch(video_id, languages=langs)
                text = ' '.join(seg.text for seg in result)
                return text, langs[0]
            except Exception:
                continue
        # Try any available transcript
        transcript_list = api.list(video_id)
        for t in transcript_list:
            result = api.fetch(video_id, languages=[t.language_code])
            text = ' '.join(seg.text for seg in result)
            return text, t.language_code
    except Exception as e:
        info(f"  Subtitle API: {e}")
    return None, None


def try_whisper(url, model, tmp_dir):
    """Tier 2: Download audio with yt-dlp, transcribe with whisper."""
    info("  Downloading audio...")
    audio_path = os.path.join(tmp_dir, "audio.mp3")
    r = subprocess.run(
        ['python3', '-m', 'yt_dlp', '-x', '--audio-format', 'mp3',
         '-o', audio_path, '--no-playlist', url],
        capture_output=True, text=True, timeout=300
    )
    if r.returncode != 0:
        err(f"  yt-dlp failed: {r.stderr.strip()}")
        return None, None

    # Find the actual audio file (yt-dlp may add extension)
    audio_files = list(Path(tmp_dir).glob("audio*"))
    if not audio_files:
        err("  No audio file downloaded")
        return None, None
    audio_path = str(audio_files[0])

    info(f"  Transcribing with whisper ({model} model)...")
    try:
        import whisper
        m = whisper.load_model(model)
        result = m.transcribe(audio_path)
        return result['text'], result.get('language', 'en')
    except ImportError:
        err("  whisper not installed. Run: pip3 install openai-whisper")
        return None, None
    except Exception as e:
        err(f"  Whisper failed: {e}")
        return None, None


def main():
    parser = argparse.ArgumentParser(description="Extract transcript from YouTube video")
    parser.add_argument("url", help="YouTube video URL or ID")
    parser.add_argument("-o", "--output", help="Output JSON path (default: stdout)")
    parser.add_argument("--whisper-model", default="base", help="Whisper model size (default: base)")
    args = parser.parse_args()

    video_id = extract_video_id(args.url)
    if not video_id:
        err(f"Could not extract video ID from: {args.url}")
        sys.exit(1)

    info(f"Video ID: {video_id}")

    # Get video title
    info("Fetching video info...")
    title, description = get_video_info(args.url)
    if title:
        ok(f"  Title: {title}")

    # Tier 1: Try subtitle API
    info("Trying subtitle extraction...")
    transcript, language = try_transcript_api(video_id)

    source = "subtitles"
    if transcript:
        ok(f"  Subtitles found ({language})")
    else:
        # Tier 2: Whisper fallback
        info("No subtitles available. Falling back to whisper transcription...")
        source = "whisper"
        tmp_dir = tempfile.mkdtemp(prefix="yt_extract_")
        try:
            transcript, language = try_whisper(args.url, args.whisper_model, tmp_dir)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        if transcript:
            ok(f"  Transcribed ({language})")
        else:
            err("Failed to extract transcript from this video.")
            sys.exit(1)

    result = {
        "title": title,
        "transcript": transcript,
        "language": language,
        "source": source,
        "video_id": video_id
    }

    if args.output:
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        ok(f"Saved to {args.output}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
