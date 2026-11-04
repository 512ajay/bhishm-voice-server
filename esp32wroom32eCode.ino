/*
 * ============================================================
 *        AAKAR AI ROBOT - ESP32 MASTER FIRMWARE v7
 * ============================================================
 *
 * Features:
 *  - INMP441 I2S microphone
 *  - MAX98357A I2S speaker
 *  - VAD
 *  - Streaming binary PCM audio
 *  - Persistent WebSocket
 *  - WiFi reconnect
 *  - TTS audio playback
 *  - Software volume control
 *  - SH1106 OLED
 *  - MAX7219 8x8 LED matrix
 *  - 5 push buttons
 *  - Pre-roll audio
 *  - Low-latency speech end + chunked playback
 *
 * IMPORTANT:
 * OLED is deliberately kept OUT of the microphone/audio path.
 *
 * Voice pipeline:
 *
 * INMP441
 *    ↓
 * I2S
 *    ↓
 * VAD
 *    ↓
 * PCM chunks
 *    ↓
 * WebSocket
 *    ↓
 * Python server
 *    ↓
 * STT → Gemini → TTS
 *    ↓
 * WebSocket
 *    ↓
 * MAX98357A
 *    ↓
 * Speaker
 *
 * ============================================================
 */

 #include <Arduino.h>
 #include <WiFi.h>
 #include <WebSocketsClient.h>
 #include <ArduinoJson.h>
 #include <Wire.h>
 #include <U8g2lib.h>
 #include <driver/i2s.h>
 #include <math.h>
 #include <string.h>
 #include <pgmspace.h>

 // 0 = quiet (saves time + flash). Set 1 only while debugging.
 #define SERIAL_LOG 0

 #if SERIAL_LOG
 #define LOG_PRINT(x)    Serial.print(x)
 #define LOG_PRINTLN(x)  Serial.println(x)
 #define LOG_PRINTF(...) Serial.printf(__VA_ARGS__)
 #else
 #define LOG_PRINT(x)
 #define LOG_PRINTLN(x)
 #define LOG_PRINTF(...)
 #endif
 
 
 // ============================================================
 //                    WIFI CONFIGURATION
 // ============================================================
 //
 // ESP32 and the PC MUST be on the SAME Wi-Fi.
 // From ipconfig, this PC is currently:
 //   Wi-Fi IPv4 = 192.168.1.21
 //   Gateway    = 192.168.1.1
 //
 // Put your home router name/password below (not the iPhone hotspot,
 // unless the PC is also connected to that hotspot).
 
 #define WIFI_SSID       "Ajay_Pc’s iPhone"
 #define WIFI_PASSWORD   "ajay1996"
 
 #define SERVER_HOST     "172.20.10.3"
 #define SERVER_PORT     8000
 #define SERVER_PATH     "/ws/robot_001"
 
 #define ROBOT_ID        "robot_001"
 
 
 // ============================================================
 //                    I2S CONFIGURATION
 // ============================================================
 
 #define I2S_PORT I2S_NUM_0
 
 #define SAMPLE_RATE        16000
 #define BITS_PER_SAMPLE    I2S_BITS_PER_SAMPLE_16BIT
 
// 50 ms @ 16 kHz mono 16-bit
 #define AUDIO_CHUNK_SIZE   1600

 // Playback write timeout (ms). Keep short so WS loop stays responsive.
 #define I2S_WRITE_TIMEOUT_MS  40

 // ------------------------------------------------------------
 // I2S pins
 // ------------------------------------------------------------

 #define I2S_BCLK   26
 #define I2S_WS     25
 #define I2S_DOUT   23
 #define I2S_DIN    34


 // ============================================================
 //                    OLED CONFIGURATION
 // ============================================================

 // OLED updates only from loop(), never inside mic/play paths.
 #define ENABLE_OLED 1

 #define I2C_SDA 21
 #define I2C_SCL 22

 // Change to 0x3D if your OLED scanner shows 0x3D.
 #define OLED_I2C_ADDRESS 0x3C

 #if ENABLE_OLED
 U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(
     U8G2_R0,
     U8X8_PIN_NONE,
     I2C_SCL,
     I2C_SDA
 );
 #endif


 // ============================================================
 //                    MAX7219 8x8 MATRIX
 // ============================================================

 // GPIO 16 = DIN, GPIO 18 = CLK, GPIO 17 = CS/LOAD
 #define ENABLE_MATRIX 1

 #define MATRIX_DIN 16
 #define MATRIX_CLK 18
 #define MATRIX_CS  17

 #define MAX7219_DIGIT0      0x01
 #define MAX7219_DECODE      0x09
 #define MAX7219_INTENSITY   0x0A
 #define MAX7219_SCANLIMIT   0x0B
 #define MAX7219_SHUTDOWN    0x0C
 #define MAX7219_DISPLAYTEST 0x0F

 #if ENABLE_MATRIX
 bool matrixReady = false;
 unsigned long lastMatrixUpdate = 0;
 uint8_t matrixFrame = 0;
 #endif


 // ============================================================
 //                    BUTTON CONFIGURATION
 // ============================================================

 #define BUTTON_VOLUME_DOWN 32
 #define BUTTON_VOLUME_UP   33
 #define BUTTON_LISTEN      27
 #define BUTTON4            14
 #define BUTTON5            13


 // ============================================================
 //                    VAD CONFIGURATION
 // ============================================================

 // Lower silence timeout = faster speech_end → shorter question latency
 #define VAD_THRESHOLD       1100
 #define SILENCE_TIMEOUT     450
 #define MIN_RECORDING_MS    250
 #define MAX_RECORDING_MS    6000

 // 3 × 50 ms = 150 ms pre-roll
 #define PRE_ROLL_CHUNKS     3


 // ============================================================
 //                    VOLUME CONFIGURATION
 // ============================================================

 #define VOLUME_MIN     0
 #define VOLUME_MAX     100
 #define VOLUME_STEP    5

 int volumeLevel = 100;
 
 
 // ============================================================
 //                    ROBOT STATES
 // ============================================================
 
 enum RobotState {
 
     STATE_CONNECTING,
 
     STATE_READY,
 
     STATE_LISTENING,
 
     STATE_THINKING,
   
     STATE_SPEAKING,
 
     STATE_ERROR
 };
 
 RobotState robotState = STATE_CONNECTING;
 
 
 // ============================================================
 //                    WEBSOCKET
 // ============================================================
 
 WebSocketsClient webSocket;
 
 bool webSocketConnected = false;
 
 
 // ============================================================
 //                    AUDIO BUFFERS
 // ============================================================
 
 // Main microphone buffer
 uint8_t audioBuffer[AUDIO_CHUNK_SIZE];
 
 // Pre-roll buffer
 uint8_t preRollBuffer[
     PRE_ROLL_CHUNKS
 ][AUDIO_CHUNK_SIZE];
 
 int preRollIndex = 0;
 
 
 // ============================================================
 //                    VOICE STATE
 // ============================================================
 
 bool recording = false;
 bool processing = false;
 bool manualListen = false;
 
 unsigned long recordingStartTime = 0;
 unsigned long lastSpeechTime = 0;
 
 float currentRMS = 0;
 
 
 // ============================================================
 //                    OLED STATE
 // ============================================================
 
#if ENABLE_OLED
 bool oledReady = false;
 unsigned long lastOLEDUpdate = 0;
 // Slower OLED refresh while speaking keeps I2S playback smoother
 #define OLED_UPDATE_INTERVAL_IDLE     400
 #define OLED_UPDATE_INTERVAL_SPEAKING 1000
 char oledStatusLine[40] = "";
 #endif


 // ============================================================
 //                    BUTTON STATE
 // ============================================================

 bool lastVolumeDown = HIGH;
 bool lastVolumeUp   = HIGH;
 bool lastListen     = HIGH;
 bool lastButton4    = HIGH;
 bool lastButton5    = HIGH;

 unsigned long lastButtonTime = 0;

 #define BUTTON_DEBOUNCE 180
 
 
 // ============================================================
 //                    FUNCTION DECLARATIONS
 // ============================================================
 
 void setupI2S();
 
 void setupOLED();
 
 void updateOLED();

 void setupMatrix();

 void updateMatrix();

 void max7219Write(uint8_t address, uint8_t data);

 void matrixDraw(const uint8_t pattern[8]);
 
 void setRobotState(RobotState newState);
 
 void handleMicrophone();
 
 void startRecording();
 
 void stopRecording();
 
 void sendPreRoll();
 
 void handleButtons();
 
 void changeVolume(int amount);
 
 void applyVolume(int16_t *samples, size_t sampleCount);
 
 void playAudio(uint8_t *data, size_t length);
 
 void testSpeaker();
 
 void webSocketEvent(
     WStype_t type,
     uint8_t *payload,
     size_t length
 );
 
 void handleWebSocketMessage(
     uint8_t *payload,
     size_t length
 );
 
 void sendStatus(const char *status);
 
 void connectWiFi();
 
 
 // ============================================================
 //                    SETUP
 // ============================================================
 
 void setup() {
 
#if SERIAL_LOG
     Serial.begin(115200);
     delay(200);
#endif
 
     LOG_PRINTLN();
     LOG_PRINTLN();
     LOG_PRINTLN("======================================");
     LOG_PRINTLN("       AAKAR AI ROBOT ESP32");
     LOG_PRINTLN("======================================");
 
     pinMode(BUTTON_VOLUME_DOWN, INPUT_PULLUP);
     pinMode(BUTTON_VOLUME_UP, INPUT_PULLUP);
     pinMode(BUTTON_LISTEN, INPUT_PULLUP);
     pinMode(BUTTON4, INPUT_PULLUP);
     pinMode(BUTTON5, INPUT_PULLUP);
 
 #if ENABLE_OLED
     setupOLED();
 #endif

 #if ENABLE_MATRIX
     setupMatrix();
 #endif
 
     setupI2S();
 
     // Optional hardware test: uncomment temporarily to test MAX98357A.
     // testSpeaker();
 
     connectWiFi();

     LOG_PRINTF(
         "[WS] Connecting to ws://%s:%d%s\n",
         SERVER_HOST,
         SERVER_PORT,
         SERVER_PATH
     );
 
     webSocket.begin(
         SERVER_HOST,
         SERVER_PORT,
         SERVER_PATH
     );
 
     webSocket.onEvent(webSocketEvent);
     webSocket.setReconnectInterval(3000);
     webSocket.enableHeartbeat(15000, 3000, 2);
 
     setRobotState(STATE_CONNECTING);
 
     LOG_PRINTLN();
     LOG_PRINTLN("System initialization complete.");
 }
 
 
 // ============================================================
 //                    MAIN LOOP
 // ============================================================
 
 void loop() {
 
     webSocket.loop();
 
     if (WiFi.status() != WL_CONNECTED) {
 
         static unsigned long lastWiFiAttempt = 0;
 
         if (millis() - lastWiFiAttempt > 5000) {
             lastWiFiAttempt = millis();
 
             LOG_PRINTLN("[WiFi] Reconnecting...");
 
             WiFi.disconnect();
             WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
         }
     }
 
     handleButtons();
 
     if (!processing) {
         handleMicrophone();
     }
 
#if ENABLE_OLED
     if (oledReady) {
         unsigned long interval =
             (robotState == STATE_SPEAKING)
                 ? OLED_UPDATE_INTERVAL_SPEAKING
                 : OLED_UPDATE_INTERVAL_IDLE;

         if (millis() - lastOLEDUpdate >= interval) {
             lastOLEDUpdate = millis();
             updateOLED();
         }
     }
 #endif

 #if ENABLE_MATRIX
     if (matrixReady) {
         unsigned long matrixInterval = 200;

         if (robotState == STATE_THINKING ||
             robotState == STATE_SPEAKING) {
             matrixInterval = 90;
         } else if (robotState == STATE_LISTENING ||
                    robotState == STATE_CONNECTING) {
             matrixInterval = 120;
         }

         if (millis() - lastMatrixUpdate >= matrixInterval) {
             lastMatrixUpdate = millis();
             updateMatrix();
         }
     }
 #endif

     delay(1);
 }
 
 
 // ============================================================
 //                    I2S SETUP
 // ============================================================
 
 void setupI2S() {
 
     // NOTE: This project currently uses the legacy i2s_driver_install()
     // API. Arduino-ESP32 may emit a deprecation warning, but it is
     // still supported by the installed core.
 
     LOG_PRINTLN("[I2S] Initializing...");
 
     i2s_config_t i2s_config;
 
     memset(
         &i2s_config,
         0,
         sizeof(i2s_config)
     );
 
     i2s_config.mode =
         (i2s_mode_t)(
             I2S_MODE_MASTER |
             I2S_MODE_TX |
             I2S_MODE_RX
         );
 
     i2s_config.sample_rate =
         SAMPLE_RATE;
 
     i2s_config.bits_per_sample =
         BITS_PER_SAMPLE;
 
     i2s_config.channel_format =
         I2S_CHANNEL_FMT_ONLY_LEFT;
 
     i2s_config.communication_format =
         I2S_COMM_FORMAT_STAND_I2S;
 
     i2s_config.intr_alloc_flags =
         ESP_INTR_FLAG_LEVEL1;
 
    // More/larger DMA buffers reduce underruns during TTS playback
     i2s_config.dma_desc_num =
         12;

     i2s_config.dma_frame_num =
         512;
 
     i2s_config.use_apll =
         false;
 
     i2s_config.tx_desc_auto_clear =
         true;
 
     i2s_config.fixed_mclk =
         0;
 
 
     esp_err_t result;
 
     result = i2s_driver_install(
         I2S_PORT,
         &i2s_config,
         0,
         NULL
     );
 
     if (result != ESP_OK) {
 
         LOG_PRINTF(
             "[I2S] Driver install failed: %d\n",
             result
         );
 
         setRobotState(STATE_ERROR);
 
         return;
     }
 
 
     // MAX98357A and INMP441 do not require MCLK.
     // Initialize the whole structure so mck_io_num cannot contain
     // an uninitialized/random GPIO number.
     i2s_pin_config_t pin_config = {};
 
     pin_config.mck_io_num = I2S_PIN_NO_CHANGE;
     pin_config.bck_io_num = I2S_BCLK;
     pin_config.ws_io_num = I2S_WS;
     pin_config.data_out_num = I2S_DOUT;
     pin_config.data_in_num = I2S_DIN;
 
 
     result = i2s_set_pin(
         I2S_PORT,
         &pin_config
     );
 
     if (result != ESP_OK) {
 
         LOG_PRINTF(
             "[I2S] Pin configuration failed: %d\n",
             result
         );
 
         setRobotState(STATE_ERROR);
 
         return;
     }
 
 
     i2s_set_clk(
         I2S_PORT,
         SAMPLE_RATE,
         I2S_BITS_PER_SAMPLE_16BIT,
         I2S_CHANNEL_MONO
     );
 
     i2s_zero_dma_buffer(I2S_PORT);
 
     LOG_PRINTLN("[I2S] TX/RX clock configured");
     LOG_PRINTLN("[I2S] Ready");
 
     LOG_PRINTF(
         "[I2S] Sample rate: %d\n",
         SAMPLE_RATE
     );
 
     LOG_PRINTF(
         "[I2S] BCLK: %d\n",
         I2S_BCLK
     );
 
     LOG_PRINTF(
         "[I2S] WS: %d\n",
         I2S_WS
     );
 
     LOG_PRINTF(
         "[I2S] DIN: %d\n",
         I2S_DIN
     );
 
     LOG_PRINTF(
         "[I2S] DOUT: %d\n",
         I2S_DOUT
     );
 }
 
 
 // ============================================================
 //                    OLED SETUP
 // ============================================================
 
 void setupOLED() {
 
 #if ENABLE_OLED
 
     LOG_PRINTLN("[OLED] Initializing...");
 
     // U8g2 owns the hardware I2C bus.
     // Do not call Wire.begin()/Wire.setClock() here.
     oled.setI2CAddress(OLED_I2C_ADDRESS << 1);
 
     if (!oled.begin()) {
         LOG_PRINTLN("[OLED] Initialization failed");
         oledReady = false;
         return;
     }
 
     oled.setContrast(180);
 
     oled.clearBuffer();
     oled.setFont(u8g2_font_6x10_tf);
     oled.drawStr(0, 12, "AAKAR ROBOT");
     oled.drawStr(0, 28, "Starting...");
     oled.sendBuffer();
 
     oledReady = true;
     lastOLEDUpdate = millis();
 
     LOG_PRINTLN("[OLED] Ready");
 
 #else
 
     LOG_PRINTLN("[OLED] Disabled");
 
 #endif
 }
 
 // ============================================================
 //                    OLED UPDATE
 // ============================================================
 
 void updateOLED() {
 
 #if ENABLE_OLED
 
     if (!oledReady) {
         return;
     }
 
     oled.clearBuffer();
 
     oled.setFont(u8g2_font_7x14B_tf);
     oled.drawStr(0, 13, "AAKAR");
 
     oled.setFont(u8g2_font_6x10_tf);
 
     const char *stateText = "UNKNOWN";
 
     switch (robotState) {
         case STATE_CONNECTING: stateText = "CONNECTING"; break;
         case STATE_READY:      stateText = "READY";      break;
         case STATE_LISTENING:  stateText = "LISTENING";  break;
         case STATE_THINKING:   stateText = "THINKING";   break;
         case STATE_SPEAKING:   stateText = "SPEAKING";   break;
         case STATE_ERROR:      stateText = "ERROR";      break;
         default:               stateText = "UNKNOWN";    break;
     }
 
     oled.drawStr(0, 27, stateText);
 
     char volumeText[20];
     snprintf(volumeText, sizeof(volumeText), "VOL %d%%", volumeLevel);
     oled.drawStr(0, 40, volumeText);
 
oled.drawFrame(55, 32, 70, 9);

     int volumeWidth = map(volumeLevel, 0, 100, 0, 66);
     volumeWidth = constrain(volumeWidth, 0, 66);
     oled.drawBox(57, 34, volumeWidth, 5);

     if (oledStatusLine[0] != '\0' &&
         (robotState == STATE_THINKING || robotState == STATE_SPEAKING)) {

         oled.drawStr(0, 55, oledStatusLine);
     } else {
         oled.drawStr(0, 53, "MIC");

         int micLevel = (int)(currentRMS / 100.0f);
         micLevel = constrain(micLevel, 0, 100);

         int micWidth = map(micLevel, 0, 100, 0, 90);

         oled.drawFrame(35, 46, 93, 9);
         oled.drawBox(37, 48, micWidth, 5);
     }

     if (WiFi.status() == WL_CONNECTED) {
         oled.drawStr(100, 13, "W");
     }

     if (webSocketConnected) {
         oled.drawStr(116, 13, "*");
     }

     oled.sendBuffer();

 #endif
 }


 // ============================================================
 //                    MAX7219 MATRIX
 // ============================================================

 void max7219Write(uint8_t address, uint8_t data) {

 #if ENABLE_MATRIX
     digitalWrite(MATRIX_CS, LOW);
     shiftOut(MATRIX_DIN, MATRIX_CLK, MSBFIRST, address);
     shiftOut(MATRIX_DIN, MATRIX_CLK, MSBFIRST, data);
     digitalWrite(MATRIX_CS, HIGH);
 #endif
 }


 void matrixDraw(const uint8_t pattern[8]) {

 #if ENABLE_MATRIX
     for (uint8_t row = 0; row < 8; row++) {
         max7219Write(MAX7219_DIGIT0 + row, pattern[row]);
     }
 #endif
 }


#if ENABLE_MATRIX
 // Stored in flash, not RAM.
 static const uint8_t FACE_SMILE[] PROGMEM = {
     0b00111100,
     0b01000010,
     0b10100101,
     0b10000001,
     0b10100101,
     0b10011001,
     0b01000010,
     0b00111100
 };

 static const uint8_t FACE_BLINK[] PROGMEM = {
     0b00111100,
     0b01000010,
     0b10000001,
     0b10111101,
     0b10000001,
     0b10011001,
     0b01000010,
     0b00111100
 };

 static const uint8_t FACE_LISTEN[] PROGMEM = {
     0b00111100,
     0b01000010,
     0b10100101,
     0b10000001,
     0b10000001,
     0b10111101,
     0b01000010,
     0b00111100
 };

 static const uint8_t FACE_THINK0[] PROGMEM = {
     0b00111100,
     0b01000010,
     0b10100101,
     0b10000001,
     0b10000001,
     0b10001001,
     0b01000010,
     0b00111100
 };

 static const uint8_t FACE_THINK1[] PROGMEM = {
     0b00111100,
     0b01000010,
     0b10100101,
     0b10000001,
     0b10000001,
     0b10011001,
     0b01000010,
     0b00111100
 };

 static const uint8_t FACE_THINK2[] PROGMEM = {
     0b00111100,
     0b01000010,
     0b10100101,
     0b10000001,
     0b10000001,
     0b10111001,
     0b01000010,
     0b00111100
 };

 static const uint8_t FACE_TALK_CLOSED[] PROGMEM = {
     0b00111100,
     0b01000010,
     0b10100101,
     0b10000001,
     0b10100101,
     0b10011001,
     0b01000010,
     0b00111100
 };

 static const uint8_t FACE_TALK_HALF[] PROGMEM = {
     0b00111100,
     0b01000010,
     0b10100101,
     0b10000001,
     0b10000001,
     0b10111101,
     0b01000010,
     0b00111100
 };

 static const uint8_t FACE_TALK_OPEN[] PROGMEM = {
     0b00111100,
     0b01000010,
     0b10100101,
     0b10000001,
     0b10000001,
     0b10111101,
     0b01111110,
     0b00111100
 };

 static const uint8_t FACE_ERROR[] PROGMEM = {
     0b10000001,
     0b01000010,
     0b00100100,
     0b00011000,
     0b00011000,
     0b00100100,
     0b01000010,
     0b10000001
 };

 static void matrixDraw_P(const uint8_t *flashPattern) {
     uint8_t pattern[8];
     memcpy_P(pattern, flashPattern, 8);
     matrixDraw(pattern);
 }
#endif


 void setupMatrix() {

 #if ENABLE_MATRIX
     pinMode(MATRIX_DIN, OUTPUT);
     pinMode(MATRIX_CLK, OUTPUT);
     pinMode(MATRIX_CS, OUTPUT);
     digitalWrite(MATRIX_CS, HIGH);

     max7219Write(MAX7219_DISPLAYTEST, 0x00);
     max7219Write(MAX7219_DECODE, 0x00);
     max7219Write(MAX7219_SCANLIMIT, 0x07);
     max7219Write(MAX7219_INTENSITY, 0x06);
     max7219Write(MAX7219_SHUTDOWN, 0x01);

     uint8_t blank[8] = {0, 0, 0, 0, 0, 0, 0, 0};
     matrixDraw(blank);

     matrixReady = true;
     lastMatrixUpdate = 0;
     matrixFrame = 0;
 #endif
 }


 void updateMatrix() {

 #if ENABLE_MATRIX
     if (!matrixReady) {
         return;
     }

     matrixFrame++;

     switch (robotState) {

         case STATE_CONNECTING: {
             uint8_t pattern[8];
             uint8_t bit = (uint8_t)(1 << (matrixFrame % 8));
             for (uint8_t i = 0; i < 8; i++) {
                 pattern[i] = bit;
             }
             matrixDraw(pattern);
             break;
         }

         case STATE_READY:
             // Slow idle blink
             if ((matrixFrame % 12) == 0) {
                 matrixDraw_P(FACE_BLINK);
             } else {
                 matrixDraw_P(FACE_SMILE);
             }
             break;

         case STATE_LISTENING:
             if ((matrixFrame % 8) == 0) {
                 matrixDraw_P(FACE_BLINK);
             } else {
                 matrixDraw_P(FACE_LISTEN);
             }
             break;

         case STATE_THINKING:
             // Blink eyes + thinking dots
             if ((matrixFrame % 4) == 0) {
                 matrixDraw_P(FACE_BLINK);
             } else if ((matrixFrame % 3) == 0) {
                 matrixDraw_P(FACE_THINK0);
             } else if ((matrixFrame % 3) == 1) {
                 matrixDraw_P(FACE_THINK1);
             } else {
                 matrixDraw_P(FACE_THINK2);
             }
             break;

         case STATE_SPEAKING:
             // Talking mouth while answering; blink now and then
             if ((matrixFrame % 10) == 0) {
                 matrixDraw_P(FACE_BLINK);
             } else {
                 uint8_t mouth = matrixFrame % 3;
                 if (mouth == 0) {
                     matrixDraw_P(FACE_TALK_CLOSED);
                 } else if (mouth == 1) {
                     matrixDraw_P(FACE_TALK_HALF);
                 } else {
                     matrixDraw_P(FACE_TALK_OPEN);
                 }
             }
             break;

         case STATE_ERROR:
         default:
             if (matrixFrame & 1) {
                 matrixDraw_P(FACE_ERROR);
             } else {
                 uint8_t blank[8] = {0, 0, 0, 0, 0, 0, 0, 0};
                 matrixDraw(blank);
             }
             break;
     }
 #endif
 }
 
 // ============================================================
 //                    ROBOT STATE
 // ============================================================
 
 void setRobotState(
     RobotState newState
 ) {
 
     if (robotState == newState) {
         return;
     }

     robotState = newState;

 #if ENABLE_MATRIX
     matrixFrame = 0;
     lastMatrixUpdate = 0;
 #endif
 }
 
 
 // ============================================================
 //                    MICROPHONE HANDLING
 // ============================================================
 
 void handleMicrophone() {
 
     size_t bytesRead = 0;
 
 
     esp_err_t result =
         i2s_read(
             I2S_PORT,
             audioBuffer,
             AUDIO_CHUNK_SIZE,
             &bytesRead,
             20 / portTICK_PERIOD_MS
         );
 
 
     if (result != ESP_OK) {
 
         return;
     }
 
 
     if (bytesRead == 0) {
 
         return;
     }
 
 
     // --------------------------------------------------------
     // Calculate RMS
     // --------------------------------------------------------
 
     int16_t *samples =
         (int16_t *)audioBuffer;
 
 
     size_t sampleCount =
         bytesRead / 2;
 
 
     uint64_t sumSquares = 0;
 
 
     for (
         size_t i = 0;
         i < sampleCount;
         i++
     ) {
 
         int32_t sample =
             samples[i];
 
         sumSquares +=
             (uint64_t)(
                 sample * sample
             );
     }
 
 
     float rms =
         sqrt(
             (float)sumSquares /
             sampleCount
         );
 
 
     currentRMS = rms;
 
 
     /*
      * DO NOT call updateOLED() here.
      *
      * This is important.
      */
 
     // Only tell OLED that new information exists.
     // Actual rendering happens from loop().
 
 
     // --------------------------------------------------------
     // Store pre-roll
     // --------------------------------------------------------
 
     memcpy(
         preRollBuffer[preRollIndex],
         audioBuffer,
         bytesRead
     );
 
 
     preRollIndex++;
 
     if (
         preRollIndex >= PRE_ROLL_CHUNKS
     ) {
 
         preRollIndex = 0;
     }
 
 
     // --------------------------------------------------------
     // Speech detection
     // --------------------------------------------------------
 
     bool speechDetected =
         rms >= VAD_THRESHOLD;
 
 
     // --------------------------------------------------------
     // NOT RECORDING
     // --------------------------------------------------------
 
     if (!recording) {
 
         if (
             speechDetected ||
             manualListen
         ) {
 
             startRecording();
         }
 
         return;
     }
 
 
     // --------------------------------------------------------
     // RECORDING
     // --------------------------------------------------------
 
     if (webSocketConnected) {
 
         webSocket.sendBIN(
             audioBuffer,
             bytesRead
         );
     }
 
 
     // --------------------------------------------------------
     // Speech activity
     // --------------------------------------------------------
 
     if (speechDetected) {
 
         lastSpeechTime =
             millis();
     }
 
 
     // --------------------------------------------------------
     // Minimum recording time
     // --------------------------------------------------------
 
     unsigned long recordingTime =
         millis() -
         recordingStartTime;
 
 
     if (
         recordingTime <
         MIN_RECORDING_MS
     ) {
 
         return;
     }
 
 
     // --------------------------------------------------------
     // Silence timeout
     // --------------------------------------------------------
 
     if (
         !manualListen &&
         millis() - lastSpeechTime >
         SILENCE_TIMEOUT
     ) {
 
         stopRecording();
 
         return;
     }
 
 
     // --------------------------------------------------------
     // Maximum recording time
     // --------------------------------------------------------
 
     if (
         recordingTime >=
         MAX_RECORDING_MS
     ) {
 
        stopRecording();

         return;
     }
 }


 // ============================================================
 //                    START RECORDING
 // ============================================================

 void startRecording() {

     if (recording || processing) {
         return;
     }

     if (!webSocketConnected) {
         LOG_PRINTLN("[MIC] Not connected, cannot record");
         return;
     }

     recording = true;
     recordingStartTime = millis();
     lastSpeechTime = millis();

     setRobotState(STATE_LISTENING);

     LOG_PRINTLN("[MIC] Speech start");

     webSocket.sendTXT(
         "{\"type\":\"speech_start\",\"robot_id\":\"robot_001\"}"
     );

     sendPreRoll();
 }


 // ============================================================
 //                    STOP RECORDING
 // ============================================================

 void stopRecording() {

     if (!recording) {
         return;
     }

     recording = false;
     manualListen = false;
     processing = true;

     setRobotState(STATE_THINKING);

     LOG_PRINTLN("[MIC] Speech end");

     webSocket.sendTXT(
         "{\"type\":\"speech_end\",\"robot_id\":\"robot_001\"}"
     );
 }


 // ============================================================
 //                    SEND PRE-ROLL
 // ============================================================

 void sendPreRoll() {

     if (!webSocketConnected) {
         return;
     }

     for (int i = 0; i < PRE_ROLL_CHUNKS; i++) {

         int index = (preRollIndex + i) % PRE_ROLL_CHUNKS;

         webSocket.sendBIN(
             preRollBuffer[index],
             AUDIO_CHUNK_SIZE
         );
     }
 }


 // ============================================================
 //                    BUTTONS
 // ============================================================

 void handleButtons() {

     unsigned long now = millis();

     if (now - lastButtonTime < BUTTON_DEBOUNCE) {
         return;
     }

     bool volumeDown = digitalRead(BUTTON_VOLUME_DOWN);
     bool volumeUp   = digitalRead(BUTTON_VOLUME_UP);
     bool listenBtn  = digitalRead(BUTTON_LISTEN);
     bool button4    = digitalRead(BUTTON4);
     bool button5    = digitalRead(BUTTON5);

     if (lastVolumeDown == HIGH && volumeDown == LOW) {
         lastButtonTime = now;
         changeVolume(-VOLUME_STEP);
     }

     if (lastVolumeUp == HIGH && volumeUp == LOW) {
         lastButtonTime = now;
         changeVolume(VOLUME_STEP);
     }

     // Push-to-talk: press = start, release = stop
     if (lastListen == HIGH && listenBtn == LOW) {
         lastButtonTime = now;
         manualListen = true;

         if (!recording && !processing) {
             startRecording();
         }
     }

     if (lastListen == LOW && listenBtn == HIGH) {
         lastButtonTime = now;

         if (manualListen && recording) {
             stopRecording();
         }

         manualListen = false;
     }

     if (lastButton4 == HIGH && button4 == LOW) {
         lastButtonTime = now;
         LOG_PRINTLN("[BTN] Button4 pressed");
     }

     if (lastButton5 == HIGH && button5 == LOW) {
         lastButtonTime = now;
         LOG_PRINTLN("[BTN] Button5 pressed");
     }

     lastVolumeDown = volumeDown;
     lastVolumeUp   = volumeUp;
     lastListen     = listenBtn;
     lastButton4    = button4;
     lastButton5    = button5;
 }


 // ============================================================
 //                    VOLUME
 // ============================================================

 void changeVolume(int amount) {

     volumeLevel += amount;

     if (volumeLevel < VOLUME_MIN) {
         volumeLevel = VOLUME_MIN;
     }

     if (volumeLevel > VOLUME_MAX) {
         volumeLevel = VOLUME_MAX;
     }

     LOG_PRINTF("[VOL] %d%%\n", volumeLevel);

 #if ENABLE_OLED
     lastOLEDUpdate = 0;
 #endif
 }


 void applyVolume(int16_t *samples, size_t sampleCount) {

     if (volumeLevel >= 100) {
         return;
     }

     if (volumeLevel <= 0) {
         memset(samples, 0, sampleCount * sizeof(int16_t));
         return;
     }

     for (size_t i = 0; i < sampleCount; i++) {

         int32_t sample = samples[i];
         sample = (sample * volumeLevel) / 100;

         if (sample > 32767) {
             sample = 32767;
         }

         if (sample < -32768) {
             sample = -32768;
         }

         samples[i] = (int16_t)sample;
     }
 }


 // ============================================================
 //                    PLAY AUDIO
 // ============================================================

 void playAudio(uint8_t *data, size_t length) {

     if (data == NULL || length == 0) {
         return;
     }

     if (length & 1) {
         length--;
     }

     applyVolume((int16_t *)data, length / 2);

     size_t bytesWritten = 0;
     size_t offset = 0;

     while (offset < length) {

         webSocket.loop();

         size_t chunk = length - offset;

         if (chunk > 2048) {
             chunk = 2048;
         }

         esp_err_t result = i2s_write(
             I2S_PORT,
             data + offset,
             chunk,
             &bytesWritten,
             I2S_WRITE_TIMEOUT_MS / portTICK_PERIOD_MS
         );

         if (result != ESP_OK) {
             LOG_PRINTF("[I2S] Write error: %d\n", result);
             break;
         }

         if (bytesWritten == 0) {
             break;
         }

         offset += bytesWritten;
     }
 }


 // ============================================================
 //                    SPEAKER TEST
 // ============================================================

 void testSpeaker() {

     LOG_PRINTLN("[I2S] Speaker test tone...");

     const int samples = 1600;
     int16_t tone[samples];

     for (int i = 0; i < samples; i++) {
         float t = (float)i / (float)SAMPLE_RATE;
         tone[i] = (int16_t)(
             8000.0f * sinf(2.0f * 3.14159265f * 440.0f * t)
         );
     }

     for (int n = 0; n < 20; n++) {
         playAudio((uint8_t *)tone, sizeof(tone));
     }

     i2s_zero_dma_buffer(I2S_PORT);

     LOG_PRINTLN("[I2S] Speaker test done");
 }


 // ============================================================
 //                    WEBSOCKET EVENT
 // ============================================================

 void webSocketEvent(
     WStype_t type,
     uint8_t *payload,
     size_t length
 ) {

     switch (type) {

         case WStype_DISCONNECTED:
             webSocketConnected = false;
             recording = false;
             processing = false;
             setRobotState(STATE_CONNECTING);
             LOG_PRINTLN("[WS] Disconnected");
             break;

         case WStype_CONNECTED:
             webSocketConnected = true;
             processing = false;
             recording = false;
             setRobotState(STATE_READY);
             LOG_PRINTF("[WS] Connected to: %s\n", payload);
             sendStatus("ready");
             break;

         case WStype_TEXT:
             handleWebSocketMessage(payload, length);
             break;

         case WStype_BIN:
             if (robotState != STATE_SPEAKING) {
                 setRobotState(STATE_SPEAKING);
             }
             playAudio(payload, length);
             break;

         case WStype_ERROR:
             LOG_PRINTLN("[WS] Error");
             setRobotState(STATE_ERROR);
             break;

         case WStype_PING:
         case WStype_PONG:
             break;

         default:
             break;
     }
 }


 // ============================================================
 //                    WEBSOCKET TEXT HANDLER
 // ============================================================

 void handleWebSocketMessage(
     uint8_t *payload,
     size_t length
 ) {

     JsonDocument doc;

     DeserializationError err = deserializeJson(doc, payload, length);

     if (err) {
         LOG_PRINTF("[WS] JSON parse error: %s\n", err.c_str());
         return;
     }

     const char *msgType = doc["type"] | "";

     if (strcmp(msgType, "status") == 0) {

         const char *status = doc["status"] | "";

         if (strcmp(status, "thinking") == 0) {
             processing = true;
             setRobotState(STATE_THINKING);
         }

         return;
     }

     if (strcmp(msgType, "ai_response") == 0) {

         const char *response = doc["response"] | "";
         const char *transcript = doc["transcript"] | "";

         LOG_PRINTF("[AI] Heard: %s\n", transcript);
         LOG_PRINTF("[AI] Reply: %s\n", response);

 #if ENABLE_OLED
         snprintf(oledStatusLine, sizeof(oledStatusLine), "%.22s", response);
         lastOLEDUpdate = 0;
 #endif

         processing = true;
         setRobotState(STATE_THINKING);
         return;
     }

     if (strcmp(msgType, "audio_start") == 0) {

         processing = true;
         setRobotState(STATE_SPEAKING);
         i2s_zero_dma_buffer(I2S_PORT);
         LOG_PRINTLN("[AUDIO] Playback start");
         return;
     }

     if (strcmp(msgType, "audio_end") == 0) {

         delay(30);
         i2s_zero_dma_buffer(I2S_PORT);

         processing = false;
         recording = false;
         setRobotState(STATE_READY);

 #if ENABLE_OLED
         oledStatusLine[0] = '\0';
 #endif

         LOG_PRINTLN("[AUDIO] Playback end");
         return;
     }

     if (strcmp(msgType, "error") == 0) {

         const char *message = doc["message"] | "error";
         LOG_PRINTF("[WS] Server error: %s\n", message);

         processing = false;
         recording = false;
         setRobotState(STATE_READY);
         return;
     }
 }


 // ============================================================
 //                    STATUS
 // ============================================================

 void sendStatus(const char *status) {

     if (!webSocketConnected) {
         return;
     }

     char buffer[96];

     snprintf(
         buffer,
         sizeof(buffer),
         "{\"type\":\"status\",\"robot_id\":\"%s\",\"status\":\"%s\"}",
         ROBOT_ID,
         status
     );

     webSocket.sendTXT(buffer);
 }


 // ============================================================
 //                    WIFI
 // ============================================================

 void connectWiFi() {

     LOG_PRINTF("[WiFi] Connecting to %s\n", WIFI_SSID);

     WiFi.mode(WIFI_STA);
     WiFi.setSleep(false);
     WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

     unsigned long start = millis();

     while (
         WiFi.status() != WL_CONNECTED &&
         millis() - start < 20000
     ) {
         delay(250);
         LOG_PRINT(".");
     }

     LOG_PRINTLN();

     if (WiFi.status() == WL_CONNECTED) {
         LOG_PRINT("[WiFi] Connected. IP: ");
         LOG_PRINTLN(WiFi.localIP());
         LOG_PRINT("[WiFi] Gateway: ");
         LOG_PRINTLN(WiFi.gatewayIP());
         LOG_PRINTF(
             "[WiFi] Server must be reachable at %s:%d\n",
             SERVER_HOST,
             SERVER_PORT
         );
     } else {
         LOG_PRINTLN("[WiFi] Connection failed");
         LOG_PRINTLN("[WiFi] Check SSID/password — use the SAME Wi-Fi as the PC");
         setRobotState(STATE_ERROR);
     }
 }
