"""Generate the FIZ Robotic Solutions project report PDF."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(__file__).resolve().parent / "FIZ_BHISHM_AI_Voice_Robot_Project_Report.pdf"

pdfmetrics.registerFont(TTFont("Arial", r"C:\Windows\Fonts\arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", r"C:\Windows\Fonts\arialbd.ttf"))

NAVY = colors.HexColor("#0B3A5B")
TEAL = colors.HexColor("#0E7C7B")
LIGHT = colors.HexColor("#F3F7FA")
LINE = colors.HexColor("#C5D4DE")
DARK = colors.HexColor("#1A2330")


def styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(
        "CoverOrg", fontName="Arial-Bold", fontSize=12, textColor=TEAL,
        alignment=TA_CENTER, spaceAfter=6, tracking=1,
    ))
    s.add(ParagraphStyle(
        "CoverTitle", fontName="Arial-Bold", fontSize=22, textColor=NAVY,
        alignment=TA_CENTER, leading=28, spaceAfter=8,
    ))
    s.add(ParagraphStyle(
        "CoverSub", fontName="Arial", fontSize=12, textColor=DARK,
        alignment=TA_CENTER, leading=16, spaceAfter=4,
    ))
    s.add(ParagraphStyle(
        "H1", fontName="Arial-Bold", fontSize=14, textColor=NAVY,
        spaceBefore=14, spaceAfter=8, borderPadding=2,
    ))
    s.add(ParagraphStyle(
        "H2", fontName="Arial-Bold", fontSize=11.5, textColor=TEAL,
        spaceBefore=10, spaceAfter=6,
    ))
    s.add(ParagraphStyle(
        "Body", fontName="Arial", fontSize=10, textColor=DARK,
        alignment=TA_JUSTIFY, leading=14, spaceAfter=6,
    ))
    s.add(ParagraphStyle(
        "BulletBody", fontName="Arial", fontSize=10, textColor=DARK,
        leading=13.5, leftIndent=4,
    ))
    s.add(ParagraphStyle(
        "Cell", fontName="Arial", fontSize=8.5, textColor=DARK, leading=11,
    ))
    s.add(ParagraphStyle(
        "CellH", fontName="Arial-Bold", fontSize=8.5, textColor=colors.white, leading=11,
    ))
    s.add(ParagraphStyle(
        "CodeBlock", fontName="Courier", fontSize=8, textColor=DARK,
        leading=11, backColor=LIGHT, leftIndent=6, rightIndent=6,
        spaceBefore=4, spaceAfter=8, borderPadding=6,
    ))
    s.add(ParagraphStyle(
        "Note", fontName="Arial", fontSize=9, textColor=NAVY,
        leading=12, backColor=colors.HexColor("#E8F3F3"),
        leftIndent=4, rightIndent=4, spaceBefore=4, spaceAfter=8,
    ))
    s.add(ParagraphStyle(
        "Footer", fontName="Arial", fontSize=8, textColor=colors.HexColor("#5A6A76"),
        alignment=TA_CENTER,
    ))
    return s


def bullets(items, st):
    return ListFlowable(
        [ListItem(Paragraph(i, st["BulletBody"]), leftIndent=12, bulletColor=TEAL)
         for i in items],
        bulletType="bullet",
        start="circle",
        leftIndent=18,
        spaceAfter=8,
    )


def table(headers, rows, col_widths):
    h = [Paragraph(x, styles()["CellH"]) for x in headers]
    body = [[Paragraph(str(c), styles()["Cell"]) for c in row] for row in rows]
    t = Table([h] + body, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, A4[1] - 12 * mm, A4[0], 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Arial", 8)
    canvas.drawString(18 * mm, A4[1] - 8 * mm, "FIZ Robotic Solutions  |  BHISHM AI Voice Robot")
    canvas.drawRightString(A4[0] - 18 * mm, A4[1] - 8 * mm, "Confidential project report")
    canvas.setFillColor(TEAL)
    canvas.rect(0, 0, A4[0], 10 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Arial", 8)
    canvas.drawString(18 * mm, 4 * mm, "Gwalior, India")
    canvas.drawRightString(A4[0] - 18 * mm, 4 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build():
    st = styles()
    story = []

    story.append(Spacer(1, 28 * mm))
    story.append(Paragraph("FIZ ROBOTIC SOLUTIONS", st["CoverOrg"]))
    story.append(Paragraph("BHISHM — AI Voice Robot", st["CoverTitle"]))
    story.append(Paragraph(
        "Technical Project Report<br/>Python Voice Server, ESP32-WROOM-32E Master Firmware,<br/>and Raspberry Pi Pico Motion Controller",
        st["CoverSub"],
    ))
    story.append(Spacer(1, 8 * mm))
    meta = table(
        ["Field", "Detail"],
        [
            ["Organization", "FIZ Robotic Solutions, Gwalior, India"],
            ["Robot name", "BHISHM"],
            ["Developer", "Ajay"],
            ["Document type", "System architecture, setup, wiring and operation"],
            ["Server stack", "Python 3, FastAPI, Uvicorn, Google Gemini"],
            ["Master MCU", "Espressif ESP32-WROOM-32E (esp32wroom32eCode.ino)"],
            ["Motion MCU", "Raspberry Pi Pico — picomove.ino (FS-iA6 + 2× IBT-2)"],
            ["Network", "Wi-Fi STA + WebSocket  ws://&lt;PC-IP&gt;:8000/ws/robot_001"],
        ],
        [45 * mm, 125 * mm],
    )
    story.append(meta)
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(
        "This document describes how the complete BHISHM voice robot is assembled, "
        "configured, started, and used. It is written for internal submission at "
        "FIZ Robotic Solutions.",
        st["Body"],
    ))

    story.append(PageBreak())

    # 1
    story.append(Paragraph("1. Executive summary", st["H1"]))
    story.append(Paragraph(
        "BHISHM is a conversational robot. A person speaks into an INMP441 microphone "
        "on the ESP32. The ESP32 detects speech, streams 16 kHz PCM audio over Wi-Fi "
        "to a Python server on a laptop, and waits. The server transcribes the speech, "
        "builds a short spoken answer with Google Gemini (and local custom Q&amp;A), "
        "synthesizes audio, and streams it back. The ESP32 plays the reply on a "
        "MAX98357A speaker, shows status on an SH1106 OLED, and animates an 8×8 "
        "MAX7219 LED face. Drive is handled separately by a Raspberry Pi Pico "
        "(picomove.ino): FlySky FS-iA6 PWM radio (CH1–CH3) mixed into two DC motors "
        "through two IBT-2 (BTS7960) drivers. Motor PWM stays on the Pico so ESP32 "
        "listening and playback are not blocked.",
        st["Body"],
    ))
    story.append(Paragraph(
        "The ESP32 and the PC must share the same Wi-Fi. SERVER_HOST in the ESP32 "
        "firmware must be the PC’s current IPv4 address (from ipconfig). If the PC "
        "IP changes, the firmware constant must be updated and the ESP32 re-flashed.",
        st["Body"],
    ))

    # 2
    story.append(Paragraph("2. System architecture", st["H1"]))
    story.append(Paragraph("2.1 High-level blocks", st["H2"]))
    story.append(Paragraph(
        "The system is split into three layers so voice, intelligence, and motion "
        "do not share one overloaded MCU.",
        st["Body"],
    ))
    story.append(table(
        ["Layer", "Hardware / software", "Responsibility"],
        [
            ["Perception &amp; playback", "ESP32-WROOM-32E + INMP441 + MAX98357A + OLED + MAX7219 + buttons",
             "Wi-Fi, VAD, WebSocket, I2S capture/playback, UI, volume"],
            ["Intelligence", "Windows PC, Python FastAPI app/ server, Gemini API",
             "STT, custom Q&amp;A, LLM reply, TTS, PCM streaming"],
            ["Motion / drive", "Raspberry Pi Pico + FS-iA6 + 2× IBT-2 (picomove.ino)",
             "RC PWM capture, arcade mix, dual DC motors; independent of ESP32 audio"],
        ],
        [38 * mm, 68 * mm, 64 * mm],
    ))
    story.append(Paragraph("2.2 Voice pipeline", st["H2"]))
    story.append(Preformatted(
        "  INMP441 mic  →  I2S RX (ESP32)  →  VAD + pre-roll\n"
        "       →  WebSocket binary PCM  →  Python FastAPI  /ws/robot_001\n"
        "       →  Gemini understand+reply  →  Gemini TTS  →  16 kHz PCM\n"
        "       →  WebSocket audio chunks  →  I2S TX  →  MAX98357A speaker",
        st["CodeBlock"],
    ))
    story.append(Paragraph("2.3 Robot states", st["H2"]))
    story.append(table(
        ["State", "Meaning", "LED matrix (8×8)"],
        [
            ["CONNECTING", "Joining Wi-Fi / WebSocket", "Moving bar"],
            ["READY", "Idle, waiting for speech", "Smile + slow blink"],
            ["LISTENING", "Capturing microphone audio", "Open mouth + blink"],
            ["THINKING", "Server is processing", "Blink + thinking dots"],
            ["SPEAKING", "Playing TTS audio", "Talking mouth animation"],
            ["ERROR", "Wi-Fi / I2S / server fault", "Blinking X"],
        ],
        [38 * mm, 72 * mm, 60 * mm],
    ))

    # 3
    story.append(Paragraph("3. Python server (app/)", st["H1"]))
    story.append(Paragraph(
        "The server lives in the robot_server project. It is a FastAPI application "
        "that keeps one persistent WebSocket per robot.",
        st["Body"],
    ))
    story.append(table(
        ["File", "Role"],
        [
            ["app/main.py", "HTTP GET / health check; WebSocket /ws/{robot_id}; speech buffer; send text then TTS audio"],
            ["app/gemini.py", "One multimodal understand+reply call; JSON parse safety; custom Q&amp;A; TTS; 16 kHz PCM + gain"],
            ["app/config.py", "API key from .env, model IDs, sample rate 16000, TTS_GAIN, chunk size 8192"],
            ["app/robot_config.py", "Name BHISHM, FIZ Robotic Solutions, personality, local FAQ answers"],
            [".env", "GEMINI_API_KEY (never commit this file)"],
            ["requirements.txt", "fastapi, uvicorn[standard], python-dotenv, google-genai"],
        ],
        [42 * mm, 128 * mm],
    ))
    story.append(Paragraph("3.1 What happens on one question", st["H2"]))
    story.append(bullets([
        "ESP32 sends JSON <b>speech_start</b>, then binary 16-bit PCM chunks, then <b>speech_end</b>.",
        "The server copies the PCM buffer and runs Gemini off the event loop (asyncio.to_thread) so the socket stays alive.",
        "Gemini returns transcript + short reply as JSON. Local custom Q&amp;A overrides Gemini if the question matches (name, creator, location, greetings, etc.).",
        "The server immediately sends JSON <b>ai_response</b> (OLED can show text before audio is ready).",
        "TTS (gemini-3.8-flash-lite-tts, voice Kore) produces WAV; the server converts to 16 kHz mono PCM16, applies gain (default ×2.8), and streams 8192-byte chunks.",
        "JSON <b>audio_start</b> / binary chunks / <b>audio_end</b> drive ESP32 playback.",
    ], st))
    story.append(Paragraph("3.2 Audio format contract", st["H2"]))
    story.append(table(
        ["Parameter", "Value"],
        [
            ["Sample rate", "16000 Hz"],
            ["Channels", "1 (mono)"],
            ["Sample format", "PCM signed 16-bit little-endian"],
            ["Mic chunk from ESP32", "1600 bytes ≈ 50 ms"],
            ["TTS chunk to ESP32", "8192 bytes"],
            ["Max recording", "about 6 seconds on device"],
        ],
        [55 * mm, 115 * mm],
    ))

    story.append(Paragraph("4. How to start the Python server", st["H1"]))
    story.append(Paragraph(
        "Use the project virtual environment. Bind to 0.0.0.0 so the ESP32 on the "
        "LAN can connect; 127.0.0.1 would only accept the PC itself.",
        st["Body"],
    ))
    story.append(Paragraph("4.1 One-time setup", st["H2"]))
    story.append(Preformatted(
        "  cd C:\\Users\\Ajay_Pc\\PycharmProjects\\robot_server\n"
        "  .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt\n"
        "\n"
        "  Create a file named .env in the project root:\n"
        "      GEMINI_API_KEY=your_key_here",
        st["CodeBlock"],
    ))
    story.append(Paragraph("4.2 Start command (recommended)", st["H2"]))
    story.append(Preformatted(
        "  cd C:\\Users\\Ajay_Pc\\PycharmProjects\\robot_server\n"
        "  .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000",
        st["CodeBlock"],
    ))
    story.append(Paragraph(
        "Alternatively run app/main.py from PyCharm (it calls uvicorn on port 8000). "
        "A browser GET to http://&lt;PC-IP&gt;:8000/ should return status online. "
        "When the robot connects, the console prints ROBOT CONNECTED: robot_001.",
        st["Body"],
    ))
    story.append(Paragraph("4.3 Windows Firewall", st["H2"]))
    story.append(Paragraph(
        "Allow inbound TCP port 8000 on a Private network. If the ESP32 joins Wi-Fi "
        "but never reaches CONNECTED, firewall or a wrong SERVER_HOST is the usual cause.",
        st["Body"],
    ))

    story.append(Paragraph("5. Wi-Fi configuration and SERVER_HOST", st["H1"]))
    story.append(Paragraph(
        "The ESP32 is a Wi-Fi station. It does not create the network. The laptop "
        "running the server and the ESP32 must be on the <b>same SSID</b> "
        "(home router or the same phone hotspot).",
        st["Body"],
    ))
    story.append(Paragraph("5.1 Firmware constants (esp32wroom32eCode.ino)", st["H2"]))
    story.append(Preformatted(
        "  #define WIFI_SSID       \"YourWiFiName\"\n"
        "  #define WIFI_PASSWORD   \"YourWiFiPassword\"\n"
        "  #define SERVER_HOST     \"192.168.1.21\"   // PC IPv4 — MUST match ipconfig\n"
        "  #define SERVER_PORT     8000\n"
        "  #define SERVER_PATH     \"/ws/robot_001\"\n"
        "  #define ROBOT_ID        \"robot_001\"",
        st["CodeBlock"],
    ))
    story.append(Paragraph("5.2 How to set SERVER_HOST from local IP", st["H2"]))
    story.append(bullets([
        "On the PC open Command Prompt and run: <b>ipconfig</b>.",
        "Under the adapter you actually use (Wi-Fi or Ethernet), copy <b>IPv4 Address</b>. Examples: 192.168.1.21 on a home router, or 172.20.10.3 on iPhone USB/personal hotspot.",
        "Paste that address into SERVER_HOST. Do not use the public WAN IP, and do not use 127.0.0.1.",
        "Confirm the Python server is listening on 0.0.0.0:8000.",
        "Flash the ESP32. After join, Serial (if SERIAL_LOG is 1) shows the ESP32 LAN IP and ws://HOST:8000/ws/robot_001.",
        "If the PC later gets a new DHCP address, repeat this procedure. Wrong SERVER_HOST is the most common disconnect.",
    ], st))
    story.append(Paragraph(
        "Do not mix networks: ESP32 on a phone hotspot while the PC is on 192.168.1.x home Wi-Fi will never reach the server.",
        st["Note"],
    ))

    # 6 ESP32 pins
    story.append(Paragraph("6. ESP32-WROOM-32E firmware (esp32wroom32eCode.ino)", st["H1"]))
    story.append(Paragraph(
        "This is the master firmware: microphone, speaker, OLED, LED matrix, buttons, "
        "and WebSocket client. OLED and MAX7219 are updated from loop() only, never "
        "inside the I2S microphone path, so display I2C/SPI does not stall audio.",
        st["Body"],
    ))
    story.append(Paragraph("6.1 Pin allocation and wiring", st["H2"]))
    story.append(table(
        ["Function", "Module pin", "ESP32 GPIO", "Notes"],
        [
            ["I2S bit clock", "BCLK (mic + amp)", "26", "Shared I2S port 0"],
            ["I2S word select", "WS / LRC", "25", "Shared"],
            ["I2S speaker data", "MAX98357A DIN", "23", "Playback TX"],
            ["I2S microphone data", "INMP441 SD", "34", "Input-only GPIO"],
            ["OLED SDA", "SH1106 SDA", "21", "I2C, address 0x3C (try 0x3D if blank)"],
            ["OLED SCL", "SH1106 SCL", "22", "I2C"],
            ["LED matrix DIN", "MAX7219 DIN", "16", "Software SPI"],
            ["LED matrix CLK", "MAX7219 CLK", "18", "Software SPI"],
            ["LED matrix CS", "MAX7219 CS / LOAD", "17", "Chip select"],
            ["Volume down", "Button to GND", "32", "INPUT_PULLUP"],
            ["Volume up", "Button to GND", "33", "INPUT_PULLUP"],
            ["Push-to-talk", "Button to GND", "27", "Press start, release stop"],
            ["Button 4", "Spare", "14", "Reserved"],
            ["Button 5", "Spare", "13", "Reserved"],
        ],
        [42 * mm, 42 * mm, 32 * mm, 54 * mm],
    ))
    story.append(Paragraph("6.2 Power and analog notes", st["H2"]))
    story.append(bullets([
        "ESP32 3.3 V logic. MAX98357A and INMP441 are 3.3 V devices. Typical MAX7219 modules prefer 5 V VCC with 3.3 V data (confirm your module).",
        "Common GND between ESP32, mic, amp, OLED, matrix, and USB/5 V supply.",
        "INMP441 L/R: tie to GND for left channel (firmware uses ONLY_LEFT).",
        "Keep mic wiring short; do not run I2S data next to motor cables from the Pico.",
    ], st))
    story.append(Paragraph("6.3 Voice activity and buttons", st["H2"]))
    story.append(table(
        ["Setting", "Value", "Purpose"],
        [
            ["VAD threshold", "1100 RMS", "Start capture when voice is loud enough"],
            ["Silence timeout", "450 ms", "End utterance quickly"],
            ["Min / max record", "250 ms / 6000 ms", "Ignore clicks; cap length"],
            ["Pre-roll", "3 × 50 ms", "Keep first syllable"],
            ["Volume", "0–100%, step 5, default 100%", "Software gain on playback"],
            ["SERIAL_LOG", "0", "Quiet serial; set 1 only for debug"],
        ],
        [40 * mm, 50 * mm, 80 * mm],
    ))
    story.append(Paragraph("6.4 WebSocket messages", st["H2"]))
    story.append(table(
        ["Direction", "Type", "Payload"],
        [
            ["ESP32 → server", "speech_start / speech_end", "JSON text"],
            ["ESP32 → server", "binary", "PCM16 mic chunks"],
            ["ESP32 → server", "status ready", "After WebSocket connect"],
            ["Server → ESP32", "status thinking", "OLED/matrix THINKING"],
            ["Server → ESP32", "ai_response", "transcript + spoken text"],
            ["Server → ESP32", "audio_start / audio_end", "Playback framing"],
            ["Server → ESP32", "binary", "PCM16 speaker chunks"],
            ["Server → ESP32", "error", "Recover to READY"],
        ],
        [40 * mm, 48 * mm, 82 * mm],
    ))
    story.append(Paragraph("6.5 Libraries (Arduino / PlatformIO)", st["H2"]))
    story.append(Paragraph(
        "WiFi, WebSocketsClient, ArduinoJson, U8g2 (SH1106), ESP-IDF I2S driver. "
        "MAX7219 is bit-banged (no extra library). Flash this file as a single sketch; "
        "do not compile max7219_matrix_test.ino in the same project.",
        st["Body"],
    ))

    # 7 Pico
    story.append(Paragraph("7. Raspberry Pi Pico drive firmware (picomove.ino)", st["H1"]))
    story.append(Paragraph(
        "picomove.ino runs on a Raspberry Pi Pico (Arduino-Pico / RP2040 core). "
        "It is a <b>direct-drive RC tank/skid mixer</b>: three PWM channels from a "
        "FlySky FS-iA6 receiver are captured with pin-change interrupts, shaped, "
        "mixed, and sent as 20 kHz PWM to two IBT-2 (BTS7960) H-bridges. There is "
        "no Wi-Fi and no Gemini on this board. Drive is independent of the ESP32 "
        "voice stack so motor PWM never stalls I2S or WebSocket.",
        st["Body"],
    ))
    story.append(Paragraph("7.1 Role split", st["H2"]))
    story.append(table(
        ["MCU", "Does", "Does not"],
        [
            ["ESP32-WROOM-32E", "Wi-Fi, mic, speaker, OLED, LED face, Gemini", "RC capture / motor PWM"],
            ["Raspberry Pi Pico", "FS-iA6 PWM in, arcade mix, 2× DC motors via IBT-2", "Speech, Wi-Fi, Gemini"],
        ],
        [42 * mm, 72 * mm, 56 * mm],
    ))
    story.append(Paragraph("7.2 Pico pin allocation and wiring", st["H2"]))
    story.append(table(
        ["Function", "Device pin", "Pico GP", "Notes"],
        [
            ["RC CH1 (turn)", "FS-iA6 CH1 signal", "GP7", "Interrupt CHANGE; ~1000–2000 µs PWM"],
            ["RC CH2 (throttle)", "FS-iA6 CH2 signal", "GP8", "Forward / reverse"],
            ["RC CH3 (extra turn)", "FS-iA6 CH3 signal", "GP9", "Added to CH1 turn"],
            ["Left motor RPWM", "IBT-2 #1 RPWM (IN1)", "GP2", "Forward PWM, 20 kHz, 8-bit"],
            ["Left motor LPWM", "IBT-2 #1 LPWM (IN2)", "GP3", "Reverse PWM"],
            ["Right motor RPWM", "IBT-2 #2 RPWM (IN1)", "GP11", "Forward PWM"],
            ["Right motor LPWM", "IBT-2 #2 LPWM (IN2)", "GP10", "Reverse PWM"],
            ["IBT-2 R_EN / L_EN", "Both enable pins", "Tied to VCC", "Firmware does not toggle enables"],
            ["Receiver GND / 5 V", "FS-iA6 power", "Common GND; 5 V from BEC/pack", "Do not power motors from Pico 3V3"],
            ["Motor battery", "IBT-2 B+ / B−", "Separate pack", "Common GND with Pico"],
            ["USB Serial", "Pico USB", "—", "115200 baud debug of CH / L / R"],
        ],
        [44 * mm, 46 * mm, 28 * mm, 52 * mm],
    ))
    story.append(Paragraph(
        "FS-iA6 signal wires are 3.3 V-tolerant PWM into Pico GPIOs with INPUT_PULLDOWN. "
        "IBT-2 logic is typically 3.3–5 V compatible; keep motor current on the IBT-2 "
        "power terminals only.",
        st["Body"],
    ))
    story.append(Paragraph("7.3 Control mapping", st["H2"]))
    story.append(table(
        ["Stick / channel", "Firmware name", "Effect"],
        [
            ["CH1", "CH_TURN", "Turn left / right (arcade yaw)"],
            ["CH2", "CH_THROTTLE", "Forward / backward"],
            ["CH3", "CH_TURN2", "Extra turn, summed with CH1 (clamped ±1)"],
            ["CH4", "not used", "No input in this sketch"],
        ],
        [42 * mm, 42 * mm, 86 * mm],
    ))
    story.append(Paragraph("7.4 Drive algorithm (what the code does)", st["H2"]))
    story.append(bullets([
        "<b>Direct drive:</b> no arming switch, no start-up lock, no failsafe freeze. Motors follow the sticks as soon as pulses are valid.",
        "<b>PWM capture:</b> CHANGE interrupts on GP7/8/9 store pulse width in microseconds.",
        "<b>Center calibration:</b> first 800 ms averages each channel (needs ≥10 good pulses) then expands min/max live as the stick is moved (800–2200 µs; spikes ignored).",
        "<b>Shaping:</b> 5% deadband, 0.30 expo (softer near center), optional invert flags for throttle/turn/left/right motors.",
        "<b>Mix:</b> left = throttle + turn, right = throttle − turn. Turn gain is 1.00 when still (pivot) and 0.65 at full speed. Outputs normalized and limited to 80% max speed.",
        "<b>Slew:</b> 20 ms loop; accelerate in 0.07 steps, decelerate in 0.18 steps so the robot does not jerk.",
        "<b>Motor PWM:</b> analogWrite at 20 kHz, 0–255. Below ~1% command both pins are off; otherwise a 8% minimum duty avoids the hum-only dead zone.",
        "<b>Watchdog:</b> rp2040.wdt_begin(1000) and wdt_reset() every loop so a hung sketch stops rather than running motors blindly (note: a reset still needs the receiver to be at center).",
        "Invalid pulses (&lt;800 or &gt;2200 µs), including an unplugged receiver, are treated as stick center (zero motion) for that channel.",
    ], st))
    story.append(Paragraph("7.5 How to flash and run picomove.ino", st["H2"]))
    story.append(bullets([
        "Board: Raspberry Pi Pico (Earle Philhower Arduino-Pico core; uses analogWriteFreq, analogWriteRange, rp2040.wdt_*).",
        "Select the Pico COM port, upload picomove.ino, Serial Monitor 115200.",
        "Power the FS-iA6 and IBT-2 from a proper BEC / battery. Bind the FlySky transmitter.",
        "On boot the Pico prints center baselines, then “Direct drive ready.” Sticks move motors immediately.",
        "If a motor runs backward, set INVERT_LEFT or INVERT_RIGHT true. If forward/back is reversed, set INVERT_THROTTLE. If left/right is swapped, set INVERT_TURN.",
        "Keep Pico GND common with receiver GND and IBT-2 GND. Do not share IBT-2 motor wires with ESP32 I2S or MAX7219 pins.",
        "Voice (ESP32) and drive (Pico) can run at the same time; they do not share a software link in the current firmware.",
    ], st))
    story.append(Paragraph(
        "Safety: this sketch has no transmitter-lost failsafe lock. If the radio drops, "
        "channels go to “center” only when pulse widths leave 800–2200 µs. Always be "
        "able to cut the motor battery.",
        st["Note"],
    ))

    # 8 features
    story.append(Paragraph("8. Features of the complete working system", st["H1"]))
    story.append(bullets([
        "Hands-free voice: energy VAD plus optional push-to-talk on GPIO 27.",
        "Low-latency path: inline audio (no Gemini Files upload), one understand+reply model call, TTS in parallel after text is sent, 450 ms silence end.",
        "Spoken identity: BHISHM, created by Ajay at FIZ Robotic Solutions, Gwalior.",
        "Custom FAQ in robot_config.py for name, creator, lab, location, greetings, thanks, goodbye.",
        "OLED status (READY / LISTENING / THINKING / SPEAKING), volume bar, Wi-Fi and socket markers.",
        "MAX7219 8×8 face animations including blink while thinking and talking mouth while answering.",
        "Software volume 0–100% on ESP32 plus server TTS_GAIN.",
        "Wi-Fi reconnect and WebSocket auto-reconnect.",
        "Quiet firmware (SERIAL_LOG 0) to save CPU and flash during demos.",
        "Independent Pico drive: FlySky FS-iA6 CH1–CH3 → arcade mix → two IBT-2 DC motors, so voice and driving run together.",
    ], st))

    story.append(Paragraph("9. End-to-end operating procedure", st["H1"]))
    story.append(bullets([
        "1. Connect the PC to the intended Wi-Fi. Run ipconfig. Note IPv4.",
        "2. Set WIFI_SSID, WIFI_PASSWORD, and SERVER_HOST in esp32wroom32eCode.ino. Flash the ESP32.",
        "3. Flash picomove.ino to the Pico. Wire FS-iA6 CH1/2/3 to GP7/8/9 and IBT-2 PWMs to GP2/3 and GP11/10. Common GND; separate motor battery. Bind the radio.",
        "4. Start Uvicorn on 0.0.0.0:8000 with GEMINI_API_KEY loaded.",
        "5. Power ESP32. OLED should go CONNECTING → READY. Server logs ROBOT CONNECTED.",
        "6. Speak a short question, or hold GPIO 27. Face shows LISTENING, then THINKING (blink), then SPEAKING (talk animation).",
        "7. Use GPIO 33 / 32 for volume. If there is no sound, confirm MAX98357A VIN/GND/SD and that TTS_GAIN / volume are not zero.",
        "8. If the robot does not connect, check same SSID, SERVER_HOST vs ipconfig, port 8000 firewall, and that uvicorn is not bound only to 127.0.0.1.",
    ], st))

    story.append(Paragraph("10. Project files to submit", st["H1"]))
    story.append(table(
        ["Path", "Submit?"],
        [
            ["esp32wroom32eCode.ino", "Yes — master firmware"],
            ["picomove.ino", "Yes — Pico RC drive firmware"],
            ["app/*.py", "Yes — server"],
            ["requirements.txt", "Yes"],
            [".env", "No — API key; provide a .env.example without the secret"],
            ["max7219_matrix_test/", "Optional hardware self-test"],
            ["This PDF", "Yes — this report"],
        ],
        [55 * mm, 115 * mm],
    ))

    story.append(Paragraph("11. Conclusion", st["H1"]))
    story.append(Paragraph(
        "BHISHM is a complete demonstration robot for FIZ Robotic Solutions: ESP32 "
        "for ears, mouth and face; a Python Gemini server for understanding and speech; "
        "and a Pico for FlySky-controlled dual-motor drive. Reliable voice operation "
        "depends on one Wi-Fi, SERVER_HOST equal to the PC local IP, and uvicorn on "
        "0.0.0.0:8000. Reliable drive depends on a bound FS-iA6, correct IBT-2 wiring, "
        "a dedicated motor pack, and common grounds — with motor PWM kept off the audio MCU.",
        st["Body"],
    ))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        "Prepared for FIZ Robotic Solutions, Gwalior, India.<br/>Robot: BHISHM &nbsp;|&nbsp; Developer: Ajay",
        st["CoverSub"],
    ))

    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title="BHISHM AI Voice Robot — Technical Report",
        author="Ajay / FIZ Robotic Solutions",
        subject="Python server, ESP32 firmware, Pico motion, Wi-Fi and wiring",
    )
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(OUT)


if __name__ == "__main__":
    build()
