# AI Personalized Tutor Dashboard with Persistent Custom Avatars

A production-oriented full-stack starter for generating personalized video lessons with persistent browser-stored tutor personas.

## Stack

- React + Vite + Tailwind CSS dark dashboard
- IndexedDB for durable portrait and voice-sample storage
- FastAPI backend with Gemini 1.5 Flash orchestration
- Local/free media pipeline using Matplotlib, Pillow, ImageIO/FFmpeg, and pyttsx3 fallback TTS
- Hook-ready architecture for Wav2Lip, SadTalker, Bark, MeloTTS, or Coqui XTTS

## Run locally

```bash
npm install
npm run dev
```

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Set `GEMINI_API_KEY` or `GOOGLE_API_KEY` for live Gemini output. Without a key, the backend returns a safe deterministic lesson fallback so the media pipeline still works.

## Media behavior

Uploaded assets remain in the browser's IndexedDB. When generating a lesson, the active portrait and optional voice sample are sent to FastAPI for one render job. The server normalizes output to even 1280x720 dimensions to avoid H.264 macro-block failures, synthesizes or falls back to generated WAV audio, renders synchronized avatar/visual frames, and returns `/media/<job>/output.mp4` with transcript subtitles.
