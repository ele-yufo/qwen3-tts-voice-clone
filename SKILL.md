---
name: qwen3-tts-voice-clone
description: Use Qwen3-TTS to generate speech from text using voice cloning. Use this skill whenever the user asks you to do voiceover, dubbing, podcast narration, text-to-speech, TTS, voice cloning, or generate audio from text. Also use when the user asks to create podcast episodes, narrate content, or produce voice recordings. The skill interfaces with a local Qwen3-TTS API server.
---

# Qwen3-TTS Voice Clone Skill

Generate speech audio from text using the Qwen3-TTS voice cloning API service.

## Configuration

The API endpoint and authentication are configured via environment variables:

- `QWEN_TTS_BASE_URL` — API server URL (default: `http://localhost:8003`)
- `QWEN_TTS_API_KEY` — API key for authentication (default: none)

If the variables are set, all curl commands below will use them automatically. If not set, the skill defaults to `http://localhost:8003` without authentication.

**For all curl commands below, use this pattern:**

```bash
# Set these once at the start (or they may already be in your environment)
API_BASE="${QWEN_TTS_BASE_URL:-http://localhost:8003}"
AUTH_HEADER=""
if [ -n "$QWEN_TTS_API_KEY" ]; then
  AUTH_HEADER="Authorization: Bearer $QWEN_TTS_API_KEY"
fi
```

## When to Use

- User asks you to generate voice/audio from text
- User mentions dubbing, voiceover, narration, podcast recording
- User wants to convert a script or article into spoken audio
- User wants to clone a voice from a reference audio sample

## Prerequisites

Verify the service is healthy:

```bash
curl -s "${QWEN_TTS_BASE_URL:-http://localhost:8003}/v1/health"
```

If running locally via systemd: `sudo systemctl start qwen3-tts`

## Core Workflow

### Step 1: Check Available Speakers

```bash
curl -s -H "$AUTH_HEADER" "$API_BASE/v1/speakers" | python3 -m json.tool
```

If the user's desired voice is already registered, skip to Step 3.

### Step 2: Register a Speaker (if needed)

```bash
curl -X POST -H "$AUTH_HEADER" "$API_BASE/v1/speakers" \
  -F "name=<speaker_name>" \
  -F "ref_audio=@<path_to_reference_audio>" \
  -F "ref_text=<transcript of the reference audio>"
```

- `name`: Short identifier (lowercase, underscores). Examples: `podcast_host`, `narrator`
- `ref_audio`: WAV/MP3/FLAC file (5-30 seconds of clear speech works best)
- `ref_text`: Exact text spoken in the reference audio — always provide for best quality

Speakers persist across service restarts.

### Step 3: Generate Speech

**For short text (under ~200 chars) — synchronous mode:**

```bash
RESULT=$(curl -s -X POST -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  "$API_BASE/v1/tts/clone" \
  -d "{\"text\": \"<text>\", \"speaker_id\": \"<id>\", \"language\": \"Chinese\"}")

# Check status
echo "$RESULT" | python3 -m json.tool

# Download audio
TASK_ID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")
curl -H "$AUTH_HEADER" "$API_BASE/v1/tasks/$TASK_ID/audio" -o output.wav
```

**For long text — async mode:**

```bash
# Submit
RESP=$(curl -s -X POST -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  "$API_BASE/v1/tasks" \
  -d "{\"text\": \"<long text>\", \"speaker_id\": \"<id>\", \"language\": \"Chinese\"}")
TASK_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")

# Poll (wait a few seconds between polls)
curl -s -H "$AUTH_HEADER" "$API_BASE/v1/tasks/$TASK_ID"
# → {"status": "running"} or {"status": "completed", "audio_url": "..."} or {"status": "failed", "error": "..."}

# Download when completed
curl -H "$AUTH_HEADER" "$API_BASE/v1/tasks/$TASK_ID/audio" -o output.wav
```

### Step 4: Handle Long Documents

For very long content, use the batch script:

```bash
python /path/to/skills/qwen3-tts-voice-clone/scripts/batch_tts.py \
  --text-file script.txt \
  --speaker-id podcast_host \
  --output output.wav \
  --language Chinese
```

The script reads `QWEN_TTS_BASE_URL` and `QWEN_TTS_API_KEY` from environment automatically.
It splits text on blank lines, generates each segment, and concatenates with silence gaps.

## Language Support

`"Auto"`, `"Chinese"`, `"English"`, `"Japanese"`, `"Korean"`, `"French"`, `"German"`, `"Spanish"`, etc.

## Important Notes

- Output: WAV (PCM 16-bit, 24kHz)
- Speed: ~real-time (RTF ≈ 0.9-1.0)
- Always check `status` field in JSON responses before downloading audio
- If `status` is `"failed"`, the `error` field contains the reason
- Service management: `systemctl {start|stop|restart|status} qwen3-tts`
- Logs: `journalctl -u qwen3-tts -f`
