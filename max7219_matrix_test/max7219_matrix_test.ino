/*
 * MAX7219 8x8 LED matrix hardware test
 * Board: ESP32-WROOM-32E
 *
 * Wiring:
 *   MAX7219 DIN  -> GPIO 16
 *   MAX7219 CLK  -> GPIO 18
 *   MAX7219 CS   -> GPIO 17
 *   MAX7219 VCC  -> 5V (or 3.3V if your module is 3.3V)
 *   MAX7219 GND  -> GND
 *
 * Upload this sketch by itself (do not compile it together
 * with esp32wroom32eCode.ino).
 *
 * Serial Monitor: 115200
 * Expected: all LEDs on, then off, then a pixel chase,
 * then a smiley face.
 */

#define MATRIX_DIN 16
#define MATRIX_CLK 18
#define MATRIX_CS  17

#define MAX7219_NOOP        0x00
#define MAX7219_DIGIT0      0x01
#define MAX7219_DECODE      0x09
#define MAX7219_INTENSITY   0x0A
#define MAX7219_SCANLIMIT   0x0B
#define MAX7219_SHUTDOWN    0x0C
#define MAX7219_DISPLAYTEST 0x0F

static const uint8_t FACE_SMILE[8] = {
    0b00111100,
    0b01000010,
    0b10100101,
    0b10000001,
    0b10100101,
    0b10011001,
    0b01000010,
    0b00111100
};

void max7219Write(uint8_t address, uint8_t data) {
    digitalWrite(MATRIX_CS, LOW);

    shiftOut(MATRIX_DIN, MATRIX_CLK, MSBFIRST, address);
    shiftOut(MATRIX_DIN, MATRIX_CLK, MSBFIRST, data);

    digitalWrite(MATRIX_CS, HIGH);
}

void matrixClear() {
    for (uint8_t row = 0; row < 8; row++) {
        max7219Write(MAX7219_DIGIT0 + row, 0x00);
    }
}

void matrixFill(uint8_t value) {
    for (uint8_t row = 0; row < 8; row++) {
        max7219Write(MAX7219_DIGIT0 + row, value);
    }
}

void matrixDraw(const uint8_t pattern[8]) {
    for (uint8_t row = 0; row < 8; row++) {
        max7219Write(MAX7219_DIGIT0 + row, pattern[row]);
    }
}

void setupMatrix() {
    pinMode(MATRIX_DIN, OUTPUT);
    pinMode(MATRIX_CLK, OUTPUT);
    pinMode(MATRIX_CS, OUTPUT);
    digitalWrite(MATRIX_CS, HIGH);

    max7219Write(MAX7219_DISPLAYTEST, 0x00);
    max7219Write(MAX7219_DECODE, 0x00);
    max7219Write(MAX7219_SCANLIMIT, 0x07);
    max7219Write(MAX7219_INTENSITY, 0x08);
    max7219Write(MAX7219_SHUTDOWN, 0x01);
    matrixClear();
}

void setup() {
    Serial.begin(115200);
    delay(300);

    Serial.println();
    Serial.println("MAX7219 8x8 matrix test");
    Serial.println("DIN=16  CLK=18  CS=17");

    setupMatrix();
}

void loop() {
    Serial.println("1) All LEDs ON");
    matrixFill(0xFF);
    delay(800);

    Serial.println("2) All LEDs OFF");
    matrixClear();
    delay(400);

    Serial.println("3) Pixel chase");
    for (uint8_t row = 0; row < 8; row++) {
        for (uint8_t col = 0; col < 8; col++) {
            matrixClear();
            max7219Write(MAX7219_DIGIT0 + row, (uint8_t)(1 << col));
            delay(40);
        }
    }

    Serial.println("4) Rows");
    for (uint8_t row = 0; row < 8; row++) {
        matrixClear();
        max7219Write(MAX7219_DIGIT0 + row, 0xFF);
        delay(120);
    }

    Serial.println("5) Columns");
    for (uint8_t col = 0; col < 8; col++) {
        matrixFill((uint8_t)(1 << col));
        delay(120);
    }

    Serial.println("6) Smiley");
    matrixDraw(FACE_SMILE);
    delay(1500);
}
