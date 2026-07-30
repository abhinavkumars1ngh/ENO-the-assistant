# Project Changelog

This file tracks all modifications, additions, and deletions made to the codebase to maintain a clear history of what was changed, where it was changed, and why.

---

## [2026-07-25] - Optimized Voice Transcription

### Changed
- **`backend/services/voice_service.py`**: Swapped out the heavy `openai-whisper` package for Apple's highly optimized `mlx_whisper`. The default model is now `mlx-community/whisper-tiny-mlx`, which is only ~122MB and runs transcription near-instantaneously on Apple Silicon chips.
- **`requirements.txt`**: Added `mlx-whisper` dependency.

## [2026-07-25] - Full-Duplex Voice Chat Mode

### Added
- **`frontend/src/app/page.tsx`**: Added a dedicated `Voice Chat` mode. Users can now click the Headphones icon next to the Send button to open a hands-free Voice Mode modal.
- **Web Speech API TTS**: When in Voice Mode, the AI's responses are automatically read aloud natively in the browser using the zero-latency `SpeechSynthesis` API, completely stripped of markdown artifacts for a clean conversational flow.

---

## [2026-07-25] - Intelligent Docker Auto-Startup

### Added
- **`start_project.py`**: The main startup script now intelligently auto-detects if Docker is running on your Mac (e.g., if you have your external SSD plugged in). 
  - If Docker **is** running, the script automatically spins up the `eno_qdrant` and `eno_redis` Docker containers (starting them if they exist, or creating them if they don't) and launches the Celery background worker process.
  - If Docker **is not** running, it gracefully skips those commands and automatically falls back to the fully local, in-memory/on-disk mode without throwing errors.

---

## [2026-07-25] - Optimized Voice Transcription

### Added
- **`frontend/src/app/page.tsx`**: Enhanced the auto-reconnect logic with clear visual feedback. When the WebSocket connection drops, the text input box now temporarily disables itself and changes its placeholder text to `"Reconnecting..."`. This prevents users from blindly typing into a dead connection and makes it obvious that the app is actively healing itself in the background without needing a manual page reload.

---

## [2026-07-19] - Anti-Hallucination for Failed YouTube Transcripts

### Fixed
- **`backend/core/scraper.py`**: Added strict system prompt injection when a YouTube transcript fails to load. The model previously tried to "helpfully" guess the contents of inaccessible videos based on its training data, leading to completely hallucinated summaries (e.g., guessing a random RStudio video). It is now explicitly instructed: "ABSOLUTE RULE: DO NOT guess, hallucinate, or assume the contents of this video. Explicitly tell the user you cannot access the transcript."

---

## [2026-07-19] - Added Frontend Auto-Reconnect

### Added
- **`frontend/src/app/page.tsx`**: Implemented an automatic WebSocket reconnection loop. If the connection drops (e.g., due to a proxy timeout, network issue, or Ngrok restarting), the client will seamlessly attempt to reconnect every 3 seconds instead of requiring the user to manually refresh the page.

---

## [2026-07-19] - Fix Infinite Loading & YouTube Rate Limit Bug

### Fixed
- **`frontend/src/app/page.tsx`**: Added `setIsGenerating(false)` inside the `ws.onclose` and `ws.onerror` handlers. Previously, if the WebSocket disconnected unexpectedly (e.g. proxy timeout), the UI would stay stuck in an infinite loading state ("...").
- **`backend/core/scraper.py`**: Truncated the generic error message string in `fetch_youtube_transcript`. When YouTube rate limits an IP (429 Error), it returns a massive HTML blob. This massive string caused the MLX model prefill to take 10+ seconds, which subsequently caused the WebSocket proxy to timeout and disconnect. Truncating the error string ensures rapid generation and prevents the timeout.

---

## [2026-07-19] - Initial Setup of Changelog

### Added
- Created `CHANGELOG.md` in the project root to track all future codebase modifications, specific line changes, and architectural updates as requested.

---
*(Future changes will be at the top of this file)*
