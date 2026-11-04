#include <Arduino.h>

// =====================================================================
//  Pico + FS-iA6 (PWM) -> 2 DC motors via 2x IBT-2
//  CH1 = turn left/right
//  CH2 = forward/backward
//  CH3 = turn left/right (added to CH1)
//  No CH4.
//
//  DIRECT DRIVE MODE:
//  - All arming checks removed
//  - All start conditions removed
//  - All failsafe locks removed
//  - Motors respond immediately to current stick inputs
// =====================================================================

// ---------------- CONFIG ----------------
// Receiver pins. Index 0..2 = CH1..CH3 (GP7, GP8, GP9).
const uint8_t RX_PINS[3] = {7, 8, 9};
enum { CH_TURN = 0, CH_THROTTLE = 1, CH_TURN2 = 2 };

// Motors (IBT-2: RPWM = in1, LPWM = in2). R_EN and L_EN must be tied to VCC.
const uint8_t LEFT_IN1  = 2,  LEFT_IN2  = 3;
const uint8_t RIGHT_IN1 = 11, RIGHT_IN2 = 10;
const bool INVERT_LEFT     = false;
const bool INVERT_RIGHT    = false;
const bool INVERT_THROTTLE = false;
const bool INVERT_TURN     = false;

const uint32_t PWM_FREQ = 20000;     // Hz
const int      PWM_MAX  = 255;

// Dynamic Calibration Boundaries (Expanded on the fly)
float centerUs[3] = {1500.0f, 1500.0f, 1500.0f};
float minUs[3]    = {1000.0f, 1000.0f, 1000.0f};
float maxUs[3]    = {2000.0f, 2000.0f, 2000.0f};

// Stick shaping & driving feel
const float DEADBAND          = 0.05f; // Stick center deadband
const float EXPO              = 0.30f; // 0 = linear, 0.3 = softer near center
const float MAX_SPEED         = 0.80f; // Speed limit (0..1)
const float TURN_GAIN_STILL   = 1.00f; // Pivot strength
const float TURN_GAIN_MOVING  = 0.65f; // Turn strength at full speed
const float MIN_DUTY          = 0.08f; // Skip dead zone where motors only hum
const float ACCEL_STEP        = 0.07f; // Per 20ms cycle
const float DECEL_STEP        = 0.18f;

const uint32_t LOOP_MS  = 20;
const uint32_t PRINT_MS = 100;
// ----------------------------------------

// ---------- PWM capture via interrupts ----------
volatile uint32_t riseTime[3]   = {0};
volatile uint32_t pulseWidth[3] = {0};
volatile uint32_t lastStamp[3]  = {0};
volatile uint32_t pulseCount[3] = {0};

static inline void handleEdge(uint8_t i) {
  uint32_t now = micros();
  if (digitalRead(RX_PINS[i])) {
    riseTime[i] = now;
  } else {
    pulseWidth[i] = now - riseTime[i];
    lastStamp[i] = now;
    pulseCount[i]++;
  }
}
void isr0() { handleEdge(0); }
void isr1() { handleEdge(1); }
void isr2() { handleEdge(2); }

uint16_t readChannel(uint8_t i) {
  noInterrupts();
  uint32_t w = pulseWidth[i];
  interrupts();
  return (uint16_t)w;
}

// ---------- Motor driver ----------
void driveMotor(uint8_t in1, uint8_t in2, float speed, bool invert) {
  if (speed > 1.0f)  speed = 1.0f;
  if (speed < -1.0f) speed = -1.0f;
  if (invert) speed = -speed;

  float a = fabsf(speed);
  int duty = 0;
  if (a > 0.01f) duty = (int)((MIN_DUTY + (1.0f - MIN_DUTY) * a) * PWM_MAX);

  if (speed > 0)      { analogWrite(in1, duty); analogWrite(in2, 0); }
  else if (speed < 0) { analogWrite(in1, 0);    analogWrite(in2, duty); }
  else                { analogWrite(in1, 0);    analogWrite(in2, 0); }
}

void setMotors(float left, float right) {
  driveMotor(LEFT_IN1,  LEFT_IN2,  left,  INVERT_LEFT);
  driveMotor(RIGHT_IN1, RIGHT_IN2, right, INVERT_RIGHT);
}

void stopAll() { setMotors(0, 0); }

// ---------- Dynamic Stick Shaping ----------
void updateSpan(uint8_t i, uint16_t us) {
  if (us < 800 || us > 2200) return; // Ignore glitched spikes
  if (us < minUs[i]) minUs[i] = us;
  if (us > maxUs[i]) maxUs[i] = us;
}

float shape(uint8_t i, uint16_t us) {
  if (us < 800 || us > 2200) return 0.0f; // Treat disconnected/corrupted signal as center
  updateSpan(i, us);

  float c = centerUs[i];
  float v = 0.0f;

  if (us >= c) {
    float span = maxUs[i] - c;
    v = (span > 30.0f) ? ((float)us - c) / span : 0.0f;
  } else {
    float span = c - minUs[i];
    v = (span > 30.0f) ? ((float)us - c) / span : 0.0f;
  }

  if (v > 1.0f)  v = 1.0f;
  if (v < -1.0f) v = -1.0f;

  float a = fabsf(v);
  if (a < DEADBAND) return 0.0f;
  a = (a - DEADBAND) / (1.0f - DEADBAND);
  a = (1.0f - EXPO) * a + EXPO * a * a * a;
  return (v > 0) ? a : -a;
}

float slew(float cur, float target) {
  float d = target - cur;
  bool towardZero = (cur > 0 && d < 0) || (cur < 0 && d > 0);
  float step = towardZero ? DECEL_STEP : ACCEL_STEP;
  if (d >  step) return cur + step;
  if (d < -step) return cur - step;
  return target;
}

// Initial center capture (does not block or lock execution)
void calibrateCenters() {
  uint32_t sum[3] = {0, 0, 0};
  uint16_t cnt[3] = {0, 0, 0};

  Serial.println("Reading initial center baselines...");
  uint32_t t0 = millis();
  while (millis() - t0 < 800) {
    for (uint8_t i = 0; i < 3; i++) {
      uint16_t w = readChannel(i);
      if (w >= 900 && w <= 2100) {
        sum[i] += w;
        cnt[i]++;
      }
    }
    delay(20);
  }

  for (uint8_t i = 0; i < 3; i++) {
    if (cnt[i] >= 10) {
      centerUs[i] = (float)sum[i] / cnt[i];
      minUs[i]    = centerUs[i] - 100.0f;
      maxUs[i]    = centerUs[i] + 100.0f;
      Serial.printf("  CH%u Center: %.0f us\n", i + 1, centerUs[i]);
    } else {
      centerUs[i] = 1500.0f;
      minUs[i]    = 1000.0f;
      maxUs[i]    = 2000.0f;
      Serial.printf("  CH%u Signal weak, defaulting to 1500 us\n", i + 1);
    }
  }
}

// ---------- State & Debug Variables ----------
float    outL = 0, outR = 0;
uint32_t lastLoop  = 0;
uint32_t lastPrint = 0;
uint16_t dbgCh[3]  = {0, 0, 0};
float    dbgThr = 0, dbgTurn = 0;

void printDebug() {
  if (millis() - lastPrint < PRINT_MS) return;
  lastPrint = millis();
  Serial.printf("CH1:%4u CH2:%4u CH3:%4u | thr:%+.2f turn:%+.2f | L:%+.2f R:%+.2f\n",
                dbgCh[0], dbgCh[1], dbgCh[2],
                dbgThr, dbgTurn, outL, outR);
}

// ---------- Setup ----------
void setup() {
  Serial.begin(115200);
  uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 2000) {}

  analogWriteFreq(PWM_FREQ);
  analogWriteRange(PWM_MAX);
  pinMode(LEFT_IN1, OUTPUT);  pinMode(LEFT_IN2, OUTPUT);
  pinMode(RIGHT_IN1, OUTPUT); pinMode(RIGHT_IN2, OUTPUT);
  stopAll();

  for (uint8_t i = 0; i < 3; i++) pinMode(RX_PINS[i], INPUT_PULLDOWN);
  attachInterrupt(digitalPinToInterrupt(RX_PINS[0]), isr0, CHANGE);
  attachInterrupt(digitalPinToInterrupt(RX_PINS[1]), isr1, CHANGE);
  attachInterrupt(digitalPinToInterrupt(RX_PINS[2]), isr2, CHANGE);

  calibrateCenters();

  rp2040.wdt_begin(1000);
  Serial.println("Direct drive ready. Motors active immediately.");
}

// ---------- Main loop ----------
void loop() {
  rp2040.wdt_reset();

  if (millis() - lastLoop < LOOP_MS) return;
  lastLoop = millis();

  uint16_t uTurn  = readChannel(CH_TURN);
  uint16_t uThr   = readChannel(CH_THROTTLE);
  uint16_t uTurn2 = readChannel(CH_TURN2);

  dbgCh[0] = uTurn; dbgCh[1] = uThr; dbgCh[2] = uTurn2;

  // Dynamic input translation without arming gates
  float turn1 = shape(CH_TURN,     uTurn);
  float thr   = shape(CH_THROTTLE, uThr);
  float turn2 = shape(CH_TURN2,    uTurn2);

  if (INVERT_THROTTLE) thr = -thr;
  if (INVERT_TURN) { turn1 = -turn1; turn2 = -turn2; }

  float turn = turn1 + turn2;
  if (turn > 1.0f)  turn = 1.0f;
  if (turn < -1.0f) turn = -1.0f;
  dbgThr = thr; dbgTurn = turn;

  // Single smooth mix
  float gain = TURN_GAIN_STILL + (TURN_GAIN_MOVING - TURN_GAIN_STILL) * fabsf(thr);
  float t = turn * gain;

  float left  = thr + t;
  float right = thr - t;
  float m = fmaxf(1.0f, fmaxf(fabsf(left), fabsf(right)));
  left  = left  / m * MAX_SPEED;
  right = right / m * MAX_SPEED;

  outL = slew(outL, left);
  outR = slew(outR, right);
  setMotors(outL, outR);

  printDebug();
}