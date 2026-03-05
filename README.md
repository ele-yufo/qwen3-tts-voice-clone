# Qwen3-TTS Voice Clone Skill

Agent skill for text-to-speech voice cloning using a self-hosted [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) API server.

> ⚠️ **Private skill** — requires a running Qwen3-TTS API server. This is not a standalone skill.

## Features

- 🎙️ Voice cloning from reference audio
- 📝 Sync & async TTS generation
- 🔐 API key authentication support
- 📦 Batch processing for long documents
- 💾 Persistent speaker registration

## Install

```bash
npx skills add ele-yufo/qwen3-tts-voice-clone
```

## Configuration

Set environment variables for your Agent:

```bash
export QWEN_TTS_BASE_URL=https://your-tts-api.example.com
export QWEN_TTS_API_KEY=your-api-key
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/speakers` | Register a speaker |
| `POST` | `/v1/tts/clone` | Sync voice clone |
| `POST` | `/v1/tasks` | Async voice clone |
| `GET` | `/v1/tasks/{id}/audio` | Download audio |

See [SKILL.md](SKILL.md) for full usage instructions.
