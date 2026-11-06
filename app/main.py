import asyncio
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .config import WS_AUDIO_CHUNK_SIZE
from .gemini import (
    understand_and_reply,
    text_to_speech,
)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="AI Voice Robot Server"
)


@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {
        "status": "online",
        "message": "AI Voice Robot Server"
    }


# ============================================================
# WEBSOCKET
# ============================================================

@app.websocket("/ws/{robot_id}")
async def robot_websocket(websocket: WebSocket, robot_id: str):

    await websocket.accept()

    print("\n==========================================")
    print(f"ROBOT CONNECTED: {robot_id}")
    print("==========================================")

    receiving_speech = False
    audio_buffer = bytearray()
    audio_chunks = 0

    try:
        while True:
            message = await websocket.receive()

            # --------------------------------------------------
            # TEXT
            # --------------------------------------------------
            if "text" in message:
                data = message["text"]
                print(f"[RX TEXT] {data}")

                if '"speech_start"' in data:
                    receiving_speech = True
                    audio_buffer.clear()
                    audio_chunks = 0
                    print("[AUDIO] Speech started")

                elif '"speech_end"' in data:
                    if not receiving_speech:
                        print("[AUDIO] speech_end without speech_start")
                        continue

                    receiving_speech = False
                    pcm_data = bytes(audio_buffer)
                    total = len(pcm_data)
                    audio_buffer.clear()

                    print(
                        f"[AUDIO] Speech ended | "
                        f"{total} bytes | {audio_chunks} chunks"
                    )

                    if total < 1600:
                        print("[AUDIO] Too short, ignoring")
                        await websocket.send_json({
                            "type": "ai_response",
                            "robot_id": robot_id,
                            "transcript": "",
                            "response": "I didn't catch that.",
                        })
                        continue

                    await process_speech(websocket, robot_id, pcm_data)

            # --------------------------------------------------
            # BINARY AUDIO
            # --------------------------------------------------
            elif "bytes" in message:
                if receiving_speech:
                    audio_buffer.extend(message["bytes"])
                    audio_chunks += 1
                    # Avoid per-chunk logging (major latency on Windows)

    except WebSocketDisconnect:
        print(f"[DISCONNECTED] {robot_id}")

    except Exception as e:
        print(f"[ERROR] WebSocket error: {e}")


# ============================================================
# PROCESS SPEECH (pipelined for lower perceived latency)
# ============================================================

async def process_speech(
    websocket: WebSocket,
    robot_id: str,
    pcm_data: bytes,
):
    t0 = time.perf_counter()

    try:
        await websocket.send_json({
            "type": "status",
            "status": "thinking",
        })

        # Run blocking Gemini work off the event loop
        transcript, response_text = await asyncio.to_thread(
            understand_and_reply,
            pcm_data,
        )

        # Send text ASAP so OLED / UI update before TTS finishes
        await websocket.send_json({
            "type": "ai_response",
            "robot_id": robot_id,
            "transcript": transcript,
            "response": response_text,
        })

        print(
            f"[TX AI] {response_text} "
            f"(text in {time.perf_counter() - t0:.2f}s)"
        )

        audio = await asyncio.to_thread(
            text_to_speech,
            response_text,
        )

        if not audio:
            print("[TTS] No audio generated")
            return

        await websocket.send_json({
            "type": "audio_start",
            "sample_rate": 16000,
            "format": "pcm16",
            "channels": 1,
        })

        chunk_size = WS_AUDIO_CHUNK_SIZE
        total = len(audio)

        print(f"[TX AUDIO] {total} bytes in ~{chunk_size}-byte chunks")

        for i in range(0, total, chunk_size):
            await websocket.send_bytes(audio[i:i + chunk_size])
            # Yield so the ESP32 can drain / play without stalling the server
            if i and (i // chunk_size) % 4 == 0:
                await asyncio.sleep(0)

        await websocket.send_json({"type": "audio_end"})

        print(
            f"[TX AUDIO] Finished in {time.perf_counter() - t0:.2f}s total"
        )

    except Exception as e:
        print(f"[PROCESS ERROR] {e}")

        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
            })
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn

    # Pass app object so this works from project root or app/
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
