# BHISHM AI Voice Robot — Python Server

FastAPI WebSocket server for the BHISHM robot (FIZ Robotic Solutions).
The ESP32 streams microphone PCM here; the server runs Gemini STT + reply + TTS and streams speech back.

## Setup

```bash
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Put your Gemini key in `.env` as `GEMINI_API_KEY`. Never commit `.env`.

## Run

```bash
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000/` — you should see `"status": "online"`.

ESP32 WebSocket path: `ws://<PC_LAN_IP>:8000/ws/robot_001`

Set `SERVER_HOST` in `esp32wroom32eCode.ino` to this PC’s IPv4 from `ipconfig`. The robot and the PC must be on the same Wi-Fi. Allow TCP port 8000 in Windows Firewall.
