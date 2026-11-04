import os
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

ENV_FILE = BASE_DIR / ".env"

load_dotenv(
    ENV_FILE,
    override=True
)


# ============================================================
# GEMINI
# ============================================================

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.8-flash"
)

GEMINI_TTS_MODEL = os.getenv(
    "GEMINI_TTS_MODEL",
    "gemini-3.8-flash-lite-tts"
)

GEMINI_TTS_VOICE = os.getenv(
    "GEMINI_TTS_VOICE",
    "Kore"
)


# ============================================================
# RECORDINGS
# ============================================================

RECORDINGS_DIR = BASE_DIR / "recordings"

RECORDINGS_DIR.mkdir(
    parents=True,
    exist_ok=True
)

SAVE_DEBUG_AUDIO = os.getenv(
    "SAVE_DEBUG_AUDIO",
    "0"
).strip().lower() in ("1", "true", "yes")


# ============================================================
# AUDIO
# ============================================================

SAMPLE_RATE = 16000

CHANNELS = 1

SAMPLE_WIDTH = 2

WS_AUDIO_CHUNK_SIZE = 8192

# Boost TTS loudness before sending to ESP32 (1.0 = unchanged)
TTS_GAIN = float(os.getenv("TTS_GAIN", "2.8"))

# Keep spoken answers short → faster TTS + less ramble
MAX_SPOKEN_CHARS = 180
