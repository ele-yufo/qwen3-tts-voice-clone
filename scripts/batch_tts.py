#!/usr/bin/env python3
"""
Batch TTS Script for Qwen3-TTS Voice Clone API

Splits a long text file into segments, generates audio for each,
and concatenates them into a single output WAV file.

Usage:
    python batch_tts.py --text-file script.txt --speaker-id podcast_host --output output.wav
    python batch_tts.py --text "直接输入文本" --speaker-id podcast_host --output output.wav
    python batch_tts.py --text-file script.txt --speaker-id host --output out.wav --language Chinese

The script splits text on blank lines (paragraphs). Each paragraph is
synthesized as a separate segment (with a short silence gap between them)
and then concatenated into the final file.
"""

import argparse
import json
import os
import struct
import sys
import tempfile
import time
import urllib.request
import wave

_config = {
    "api_base": os.environ.get("QWEN_TTS_BASE_URL", "http://localhost:8003"),
    "api_key": os.environ.get("QWEN_TTS_API_KEY", ""),
}
SILENCE_DURATION = 0.5  # seconds of silence between segments
SAMPLE_RATE = 24000
POLL_INTERVAL = 2  # seconds between status polls


def _make_request(url: str, data=None, headers=None, method=None) -> urllib.request.Request:
    """Create a request with auth header if API key is configured."""
    hdrs = headers or {}
    if _config["api_key"]:
        hdrs["Authorization"] = f"Bearer {_config['api_key']}"
    req = urllib.request.Request(url, data=data, headers=hdrs)
    if method:
        req.method = method
    return req


def check_health():
    """Verify the API server is running."""
    try:
        req = _make_request(f"{_config['api_base']}/v1/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            if data.get("status") != "ok":
                print(f"ERROR: API server unhealthy: {data}", file=sys.stderr)
                sys.exit(1)
            if not data.get("model_loaded"):
                print("ERROR: Model not loaded yet. Wait and retry.", file=sys.stderr)
                sys.exit(1)
    except Exception as e:
        print(f"ERROR: Cannot reach API server at {_config['api_base']}: {e}", file=sys.stderr)
        print("Make sure the service is running: sudo systemctl start qwen3-tts", file=sys.stderr)
        sys.exit(1)


def check_speaker(speaker_id: str):
    """Verify the speaker exists."""
    req = _make_request(f"{_config['api_base']}/v1/speakers")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
        ids = [s["speaker_id"] for s in data.get("speakers", [])]
        if speaker_id not in ids:
            print(f"ERROR: Speaker '{speaker_id}' not found.", file=sys.stderr)
            print(f"Available speakers: {ids}", file=sys.stderr)
            sys.exit(1)


def split_text(text: str) -> list:
    """Split text into paragraphs (on blank lines), filtering empty ones."""
    paragraphs = text.split("\n\n")
    return [p.strip().replace("\n", " ") for p in paragraphs if p.strip()]


def submit_task(text: str, speaker_id: str, language: str) -> str:
    """Submit an async TTS task, return task_id."""
    payload = json.dumps({
        "text": text,
        "speaker_id": speaker_id,
        "language": language,
    }).encode()
    req = _make_request(
        f"{_config['api_base']}/v1/tasks",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
        return data["task_id"]


def wait_for_task(task_id: str) -> dict:
    """Poll until task completes or fails."""
    while True:
        req = _make_request(f"{_config['api_base']}/v1/tasks/{task_id}")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            status = data.get("status")
            if status == "completed":
                return data
            elif status == "failed":
                print(f"ERROR: Task {task_id} failed: {data.get('error')}", file=sys.stderr)
                sys.exit(1)
        time.sleep(POLL_INTERVAL)


def download_audio(task_id: str, output_path: str):
    """Download WAV audio from a completed task."""
    req = _make_request(f"{_config['api_base']}/v1/tasks/{task_id}/audio")
    with urllib.request.urlopen(req) as resp:
        with open(output_path, "wb") as f:
            f.write(resp.read())


def generate_silence(duration: float, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Generate silent PCM16 samples."""
    n_samples = int(duration * sample_rate)
    return struct.pack(f"<{n_samples}h", *([0] * n_samples))


def concatenate_wavs(wav_files: list, output_path: str, silence_duration: float = SILENCE_DURATION):
    """Concatenate WAV files with silence gaps between them."""
    silence = generate_silence(silence_duration)

    with wave.open(output_path, "wb") as out:
        params_set = False
        for i, wav_file in enumerate(wav_files):
            with wave.open(wav_file, "rb") as inp:
                if not params_set:
                    out.setparams(inp.getparams())
                    params_set = True
                out.writeframes(inp.readframes(inp.getnframes()))
                # Add silence between segments (not after the last one)
                if i < len(wav_files) - 1:
                    out.writeframes(silence)


def main():
    parser = argparse.ArgumentParser(description="Batch TTS with Qwen3-TTS Voice Clone API")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text-file", help="Path to a text file to synthesize")
    group.add_argument("--text", help="Text string to synthesize directly")
    parser.add_argument("--speaker-id", required=True, help="Registered speaker ID")
    parser.add_argument("--output", required=True, help="Output WAV file path")
    parser.add_argument("--language", default="Auto", help="Language (default: Auto)")
    parser.add_argument("--silence", type=float, default=SILENCE_DURATION,
                        help=f"Silence between segments in seconds (default: {SILENCE_DURATION})")
    parser.add_argument("--api-base", default=_config["api_base"],
                        help="API base URL (default: from QWEN_TTS_BASE_URL or http://localhost:8003)")
    parser.add_argument("--api-key", default=_config["api_key"],
                        help="API key (default: from QWEN_TTS_API_KEY env var)")
    args = parser.parse_args()

    _config["api_base"] = args.api_base
    _config["api_key"] = args.api_key

    # Read text
    if args.text_file:
        with open(args.text_file, "r") as f:
            text = f.read()
    else:
        text = args.text

    # Split into segments
    segments = split_text(text)
    if not segments:
        print("ERROR: No text segments found.", file=sys.stderr)
        sys.exit(1)

    print(f"Text split into {len(segments)} segments")

    # Preflight checks
    check_health()
    check_speaker(args.speaker_id)

    # Generate each segment
    tmpdir = tempfile.mkdtemp(prefix="batch_tts_")
    wav_files = []
    total_duration = 0
    total_inference = 0

    for i, segment in enumerate(segments):
        print(f"[{i + 1}/{len(segments)}] Generating: {segment[:50]}...")
        task_id = submit_task(segment, args.speaker_id, args.language)
        result = wait_for_task(task_id)

        wav_path = os.path.join(tmpdir, f"segment_{i:04d}.wav")
        download_audio(task_id, wav_path)
        wav_files.append(wav_path)

        dur = result.get("audio_duration", 0)
        inf = result.get("inference_time", 0)
        total_duration += dur
        total_inference += inf
        print(f"  → {dur:.1f}s audio, {inf:.1f}s inference")

    # Concatenate
    print(f"\nConcatenating {len(wav_files)} segments...")
    concatenate_wavs(wav_files, args.output, args.silence)

    # Cleanup temp files
    for f in wav_files:
        os.unlink(f)
    os.rmdir(tmpdir)

    print(f"\n✅ Done! Output: {args.output}")
    print(f"   Total audio: {total_duration:.1f}s")
    print(f"   Total inference: {total_inference:.1f}s")
    print(f"   Average RTF: {total_inference / total_duration:.3f}" if total_duration > 0 else "")


if __name__ == "__main__":
    main()
