import io
import json
import re
import time
import wave

try:
    import audioop
except ImportError:
    import audioop_lts as audioop

from google import genai
from google.genai import types

from .config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_TTS_MODEL,
    GEMINI_TTS_VOICE,
    RECORDINGS_DIR,
    SAMPLE_RATE,
    CHANNELS,
    SAMPLE_WIDTH,
    SAVE_DEBUG_AUDIO,
    TTS_GAIN,
    MAX_SPOKEN_CHARS,
)
from .robot_config import (
    ROBOT_NAME,
    ROBOT_CREATOR,
    ROBOT_ORGANIZATION,
    ROBOT_PERSONALITY,
    check_custom_qa,
)


# ============================================================
# GEMINI CLIENT
# ============================================================

client = genai.Client(
    api_key=GEMINI_API_KEY
)


REPLY_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "transcript": {
            "type": "STRING",
            "description": "Exact words spoken by the human",
        },
        "response": {
            "type": "STRING",
            "description": "Short spoken answer from the robot",
        },
    },
    "required": ["transcript", "response"],
}


# ============================================================
# HELPERS
# ============================================================

def _pcm_to_wav_bytes(pcm_data: bytes) -> bytes:
    wav_buffer = io.BytesIO()

    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(SAMPLE_WIDTH)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(pcm_data)

    return wav_buffer.getvalue()


def _save_wav(path, pcm_data: bytes, rate: int = SAMPLE_RATE):
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(rate)
        wav_file.writeframes(pcm_data)


def _unescape_json_string(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return (
            value
            .replace('\\"', '"')
            .replace("\\n", " ")
            .replace("\\t", " ")
            .replace("\\\\", "\\")
            .strip()
        )


def _extract_json_field(text: str, key: str) -> str | None:
    """
    Pull a string field even from truncated / messy JSON.
    Handles: missing closing quote, code fences, partial objects.
    """

    if not text:
        return None

    pattern = (
        rf'"{re.escape(key)}"\s*:\s*"'
        rf'((?:\\.|[^"\\])*)'
        rf'(?:"|$)'
    )

    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)

    if not match:
        return None

    return _unescape_json_string(match.group(1)).strip()


def _parse_reply_payload(raw: str) -> tuple[str, str]:
    """
    Returns (transcript, response). Never returns raw JSON as response.
    """

    if not raw:
        return "", ""

    text = raw.strip()

    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    transcript = ""
    answer = ""

    # 1) Strict JSON
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            transcript = str(parsed.get("transcript", "")).strip()
            answer = str(parsed.get("response", "")).strip()
            if answer:
                return transcript, answer
    except json.JSONDecodeError:
        pass

    # 2) Embedded JSON object
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        try:
            parsed = json.loads(brace.group(0))
            if isinstance(parsed, dict):
                transcript = str(parsed.get("transcript", "")).strip()
                answer = str(parsed.get("response", "")).strip()
                if answer:
                    return transcript, answer
        except json.JSONDecodeError:
            pass

    # 3) Field regex (works on truncated JSON — the main bug from logs)
    transcript = _extract_json_field(text, "transcript") or ""
    answer = _extract_json_field(text, "response") or ""

    if answer:
        return transcript, answer

    # 4) Looks like JSON garbage → do NOT speak it
    lowered = text.lower()
    if (
        '"transcript"' in lowered
        or '"response"' in lowered
        or text.lstrip().startswith("{")
        or text.lstrip().startswith("```")
    ):
        return transcript, ""

    # 5) Plain text answer (no JSON)
    return "", text


def _looks_like_json_or_meta(text: str) -> bool:
    if not text:
        return True

    lowered = text.lower().strip()

    if lowered.startswith("{") or lowered.startswith("```"):
        return True

    bad_starts = (
        "transcript",
        "response",
        '"transcript"',
        '"response"',
        "json",
    )

    return any(lowered.startswith(b) for b in bad_starts)


def _truncate_spoken(text: str, limit: int = MAX_SPOKEN_CHARS) -> str:
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) <= limit:
        return text

    cut = text[:limit]
    # Prefer ending on a sentence boundary
    for sep in (". ", "! ", "? "):
        idx = cut.rfind(sep)
        if idx >= 40:
            return cut[: idx + 1].strip()

    idx = cut.rfind(" ")
    if idx >= 40:
        return cut[:idx].strip()

    return cut.strip()


def _prefer_complete_sentences(text: str) -> str:
    """Drop a dangling unfinished clause after the last sentence end."""

    text = text.strip()
    if not text:
        return text

    ends = list(re.finditer(r"[.!?]", text))
    if ends:
        return text[: ends[-1].end()].strip()

    return text


def _clean_spoken_answer(answer: str) -> str:
    answer = (answer or "").strip()
    answer = re.sub(r"```(?:json)?|```", "", answer).strip()
    answer = answer.replace("*", "").replace("#", "").strip()

    if _looks_like_json_or_meta(answer):
        rescued = _extract_json_field(answer, "response")
        if rescued and not _looks_like_json_or_meta(rescued):
            answer = rescued
        else:
            return "I didn't catch that clearly. Please ask again."

    # Keep the configured robot name consistent if model mangles casing
    answer = re.sub(
        re.escape(ROBOT_NAME),
        ROBOT_NAME,
        answer,
        flags=re.IGNORECASE,
    )

    answer = _prefer_complete_sentences(answer)
    answer = _truncate_spoken(answer)

    if not answer:
        return "I didn't understand that."

    return answer


def _boost_pcm(pcm_data: bytes, gain: float = TTS_GAIN) -> bytes:
    if gain <= 1.01 or not pcm_data:
        return pcm_data

    # Soft clip after gain
    samples = memoryview(pcm_data).cast("h")
    out = bytearray(len(pcm_data))
    out_samples = memoryview(out).cast("h")

    for i, sample in enumerate(samples):
        boosted = int(sample * gain)
        if boosted > 32767:
            boosted = 32767
        elif boosted < -32768:
            boosted = -32768
        out_samples[i] = boosted

    return bytes(out)


# ============================================================
# UNDERSTAND + REPLY
# ============================================================

def understand_and_reply(pcm_data: bytes) -> tuple[str, str]:
    """
    Multimodal turn → (transcript, spoken_answer).
    Falls back to separate STT + reply if JSON is unusable.
    """

    t0 = time.perf_counter()

    print(f"[AI] Received {len(pcm_data)} bytes")

    if not pcm_data:
        return "", "I didn't hear anything."

    wav_bytes = _pcm_to_wav_bytes(pcm_data)

    if SAVE_DEBUG_AUDIO:
        _save_wav(RECORDINGS_DIR / "latest_input.wav", pcm_data)

    prompt = f"""
You are {ROBOT_NAME}, a voice robot.
Created by {ROBOT_CREATOR} at {ROBOT_ORGANIZATION}.

{ROBOT_PERSONALITY}

Listen to the attached human speech.

Return JSON with:
- transcript: exact words the human said (English or Hindi as spoken)
- response: your answer, max 2 short sentences, ready for text-to-speech

Hard rules:
- Your name is ONLY "{ROBOT_NAME}". Never invent another name.
- Do NOT repeat the user's question in the response.
- Do NOT include the word transcript or response in the spoken answer.
- No markdown, no code fences, no bullet points.
- Keep response under 35 words.
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            prompt,
            types.Part.from_bytes(
                data=wav_bytes,
                mime_type="audio/wav",
            ),
        ],
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=512,
            response_mime_type="application/json",
            response_schema=REPLY_SCHEMA,
        ),
    )

    raw = (response.text or "").strip()
    print(f"[AI] Raw model output: {raw[:240]!r}")

    transcript, answer = _parse_reply_payload(raw)
    answer = _clean_spoken_answer(answer) if answer else ""

    needs_fallback = (
        not answer
        or _looks_like_json_or_meta(answer)
        or answer.startswith("I didn't catch")
    )

    if needs_fallback:
        print("[AI] Multimodal parse weak — falling back to STT + reply")
        fb_transcript = transcribe_audio(pcm_data)
        if fb_transcript:
            transcript = fb_transcript
        answer = generate_response(transcript)
        answer = _clean_spoken_answer(answer)

    if transcript:
        custom = check_custom_qa(transcript)
        if custom:
            print("[AI] Using custom Q&A")
            answer = custom

    print(f"[AI] Transcript: {transcript}")
    print(f"[AI] Response: {answer}")
    print(f"[AI] Understand+reply: {time.perf_counter() - t0:.2f}s")

    return transcript, answer


# ============================================================
# STT / REPLY (fallback path)
# ============================================================

def transcribe_audio(pcm_data: bytes) -> str:
    print(f"[STT] Received {len(pcm_data)} bytes")

    if not pcm_data:
        return ""

    wav_bytes = _pcm_to_wav_bytes(pcm_data)

    if SAVE_DEBUG_AUDIO:
        _save_wav(RECORDINGS_DIR / "latest_input.wav", pcm_data)

    prompt = (
        "Transcribe ONLY the human speech in this audio. "
        "Return plain text words only. "
        "No JSON. No quotes. No labels. "
        "If unclear, return an empty string."
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            prompt,
            types.Part.from_bytes(
                data=wav_bytes,
                mime_type="audio/wav",
            ),
        ],
        config=types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=128,
        ),
    )

    transcript = (response.text or "").strip()
    transcript = transcript.strip('"').strip()
    transcript = re.sub(r"^(transcript\s*:)\s*", "", transcript, flags=re.I)

    print(f"[STT] Transcript: {transcript}")
    return transcript


def generate_response(transcript: str) -> str:
    transcript = transcript.strip()

    if not transcript:
        return "I didn't hear anything."

    custom_answer = check_custom_qa(transcript)
    if custom_answer:
        print("[AI] Using custom Q&A")
        return custom_answer

    prompt = f"""
You are {ROBOT_NAME}, created by {ROBOT_CREATOR} at {ROBOT_ORGANIZATION}.

{ROBOT_PERSONALITY}

Answer the user in at most 2 short sentences for speech.
Your name is ONLY {ROBOT_NAME}. Never invent another name.
Do not repeat the question.
No markdown. No JSON. No labels.

User said: {transcript}
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.4,
            max_output_tokens=120,
        ),
    )

    answer = _clean_spoken_answer((response.text or "").strip())
    print(f"[AI] Gemini response: {answer}")
    return answer


# ============================================================
# WAV → PCM / RESAMPLE
# ============================================================

def wav_to_pcm(wav_data: bytes):
    buffer = io.BytesIO(wav_data)

    with wave.open(buffer, "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        pcm_data = wav_file.readframes(wav_file.getnframes())

    return pcm_data, sample_rate, channels, sample_width


def resample_to_16khz(
    pcm_data: bytes,
    input_rate: int,
    channels: int,
    sample_width: int,
) -> bytes:

    if input_rate == SAMPLE_RATE and channels == 1:
        return pcm_data

    data = pcm_data

    if channels == 2:
        data = audioop.tomono(data, sample_width, 0.5, 0.5)
        channels = 1

    if input_rate != SAMPLE_RATE:
        print(f"[TTS] Resampling {input_rate} Hz → {SAMPLE_RATE} Hz")
        data, _ = audioop.ratecv(
            data,
            sample_width,
            channels,
            input_rate,
            SAMPLE_RATE,
            None,
        )

    return data


def _audio_bytes_to_pcm16(audio_data: bytes, mime_type: str | None) -> bytes:
    mime = (mime_type or "").lower()

    if audio_data[:4] == b"RIFF" or "wav" in mime:
        pcm_data, sample_rate, channels, sample_width = wav_to_pcm(audio_data)
        return resample_to_16khz(pcm_data, sample_rate, channels, sample_width)

    assumed_rate = 24000
    print(f"[TTS] Treating as raw PCM @ {assumed_rate} Hz")
    return resample_to_16khz(audio_data, assumed_rate, 1, 2)


# ============================================================
# TEXT TO SPEECH
# ============================================================

def _tts_contents(spoken: str):
    # Gemini 3.8 TTS: text is the transcript; style goes in speech_metadata.
    return [{
        "role": "user",
        "parts": [{
            "text": spoken,
            "speech_metadata": {
                "style": "friendly, clear, and conversational",
            },
        }],
    }]


def _tts_config() -> dict:
    # google-genai 3.x: voice lives under speech_config.voice_config.voice
    # (not generation_config.speechConfig.prebuiltVoiceConfig).
    return {
        "response_modalities": ["AUDIO"],
        "speech_config": {
            "voice_config": {
                "voice": GEMINI_TTS_VOICE,
            }
        },
    }


def _extract_tts_audio(response):
    parts = []

    if getattr(response, "parts", None):
        parts.extend(response.parts)

    try:
        parts.extend(response.candidates[0].content.parts)
    except Exception:
        pass

    for part in parts:
        inline = getattr(part, "inline_data", None)
        if inline is not None and getattr(inline, "data", None):
            return inline.data, getattr(inline, "mime_type", None)

    raise RuntimeError("TTS response had no audio data")


def text_to_speech(text: str) -> bytes:
    t0 = time.perf_counter()

    spoken = _clean_spoken_answer(text)

    if _looks_like_json_or_meta(spoken):
        spoken = "I didn't catch that clearly. Please ask again."

    print(f"[TTS] Generating speech for: {spoken!r}")

    models_to_try = [GEMINI_TTS_MODEL]

    if GEMINI_TTS_MODEL != "gemini-3.8-flash-tts":
        models_to_try.append("gemini-3.8-flash-tts")

    last_error = None
    response = None
    used_model = models_to_try[0]

    for model_name in models_to_try:
        try:
            print(f"[TTS] Model: {model_name}")
            response = client.models.generate_content(
                model=model_name,
                contents=_tts_contents(spoken),
                config=_tts_config(),
            )
            used_model = model_name
            break
        except Exception as e:
            last_error = e
            print(f"[TTS] {model_name} failed: {e}")

    if response is None:
        raise RuntimeError(f"TTS failed: {last_error}")

    audio_data, mime_type = _extract_tts_audio(response)

    print(
        f"[TTS] {used_model} returned "
        f"{len(audio_data)} bytes ({mime_type})"
    )

    pcm_data = _audio_bytes_to_pcm16(audio_data, mime_type)
    pcm_data = _boost_pcm(pcm_data, TTS_GAIN)

    print(f"[TTS] Applied gain x{TTS_GAIN}")

    if SAVE_DEBUG_AUDIO:
        _save_wav(RECORDINGS_DIR / "tts_test.wav", pcm_data)
        print(f"[TTS] Saved: {RECORDINGS_DIR / 'tts_test.wav'}")

    print(
        f"[TTS] Done in {time.perf_counter() - t0:.2f}s "
        f"({len(pcm_data)} PCM bytes)"
    )

    return pcm_data


# ============================================================
# COMPLETE AUDIO PROCESSING
# ============================================================

def process_audio(pcm_data: bytes):
    print("\n==============================")
    print("PROCESSING AUDIO")
    print("==============================")

    t0 = time.perf_counter()

    try:
        transcript, response_text = understand_and_reply(pcm_data)
        response_text = _clean_spoken_answer(response_text)

        if not transcript and response_text == "I didn't hear anything.":
            return {
                "success": False,
                "transcript": "",
                "response": response_text,
                "audio": None,
            }

        audio = text_to_speech(response_text)

        print("==============================")
        print(f"PROCESSING COMPLETE in {time.perf_counter() - t0:.2f}s")
        print("==============================\n")

        return {
            "success": True,
            "transcript": transcript,
            "response": response_text,
            "audio": audio,
        }

    except Exception as e:
        print(f"[PROCESS ERROR] {repr(e)}")

        return {
            "success": False,
            "transcript": "",
            "response": "Sorry, something went wrong.",
            "audio": None,
            "error": str(e),
        }
