// ============================================================
//  Microinjector Firmware  v2.0
//  Hardware: Arduino Nano + ULN2003 + 28BYJ-48 stepper
//  Library:  AccelStepper (4-wire half-step, MotorInterfaceType 4)
//  Serial:   9600 baud, newline line-ending
//
//  Speed model: constant acceleration from start_speed to end_speed
//  across the full move distance.  accel=0 → constant speed at start_speed.
// ============================================================
#include <AccelStepper.h>

// ---- Pin mapping (IN1-IN3-IN2-IN4 for correct 28BYJ-48 step sequence) ----
#define IN1 8
#define IN2 10
#define IN3 9
#define IN4 11

// ---- Motor constants ----
#define MOTOR_INTERFACE_TYPE 4
#define STEPS_PER_REV 2048L
#define ABS_MAX_SPEED 1000.0f
#define ABS_MAX_ACCEL 1000.0f

// ---- Program storage ----
#define MAX_STEPS 5

struct Step {
  bool  forward;      // true = forward, false = backward
  long  distance;     // steps (positive)
  float start_speed;  // steps/s at beginning of move
  float end_speed;    // steps/s at end of move (clamped; distance takes precedence)
  float accel;        // steps/s² (positive = accel, negative = decel, 0 = constant)
};

Step    program[MAX_STEPS];
uint8_t programCount = 0;

// ---- Active-move globals ----
bool  g_moving      = false;
long  g_target_dist = 0;
float g_start_speed = 1.0f;
float g_end_speed   = 1.0f;
float g_accel       = 0.0f;
bool  g_fwd         = true;

// ---- State machine ----
enum State { STATE_IDLE, STATE_MOVING_MANUAL, STATE_MOVING_PROG };
State   state         = STATE_IDLE;
uint8_t progStepIndex = 0;

// ---- AccelStepper instance ----
AccelStepper stepper(MOTOR_INTERFACE_TYPE, IN1, IN2, IN3, IN4);

// ===========================================================
//  Helpers
// ===========================================================
void printDivider() { Serial.println(F("----------------------------")); }

void printMainMenu() {
  printDivider();
  Serial.println(F("  MICROINJECTOR  v2.0"));
  printDivider();
  Serial.println(F("  [M] Manual move"));
  Serial.println(F("  [P] Edit program"));
  Serial.println(F("  [R] Run program"));
  Serial.println(F("  [S] Show program"));
  Serial.println(F("  [C] Clear program"));
  Serial.println(F("  [?] Help"));
  printDivider();
  Serial.print(F("  Steps stored: "));
  Serial.println(programCount);
  printDivider();
  Serial.println(F("Enter command > "));
}

void printHelp() {
  Serial.println(F("Units & limits:"));
  Serial.println(F("  Distance  : steps  (2048 = 1 rev)"));
  Serial.println(F("  Start spd : steps/s  (1 - 1000)  speed at t=0"));
  Serial.println(F("  End spd   : steps/s  (1 - 1000)  target final speed"));
  Serial.println(F("  Accel     : steps/s2 (-1000 to +1000, 0 = constant)"));
  Serial.println(F("  Direction : F = forward, B = backward"));
  Serial.println(F("During a move: type X + Enter to abort."));
}

void printProgram() {
  if (programCount == 0) { Serial.println(F("Program is empty.")); return; }
  Serial.println(F("#  Dir  Dist(steps)  StartSpd  EndSpd  Accel"));
  printDivider();
  for (uint8_t i = 0; i < programCount; i++) {
    Serial.print(i + 1);          Serial.print(F("  "));
    Serial.print(program[i].forward ? 'F' : 'B'); Serial.print(F("    "));
    Serial.print(program[i].distance);            Serial.print(F("         "));
    Serial.print((int)program[i].start_speed);    Serial.print(F("        "));
    Serial.print((int)program[i].end_speed);      Serial.print(F("     "));
    Serial.println((int)program[i].accel);
  }
}

String promptLine(const char *msg) {
  Serial.print(msg);
  while (!Serial.available()) {}
  String s = Serial.readStringUntil('\n');
  s.trim();
  return s;
}

float promptFloat(const char *msg, float lo, float hi) {
  while (true) {
    String s = promptLine(msg);
    float v = s.toFloat();
    if (v >= lo && v <= hi) return v;
    Serial.print(F("  ! Out of range (")); Serial.print(lo);
    Serial.print(F(" - ")); Serial.print(hi); Serial.println(F("), try again."));
  }
}

long promptLong(const char *msg, long lo, long hi) {
  while (true) {
    String s = promptLine(msg);
    long v = s.toInt();
    if (v >= lo && v <= hi) return v;
    Serial.print(F("  ! Out of range (")); Serial.print(lo);
    Serial.print(F(" - ")); Serial.print(hi); Serial.println(F("), try again."));
  }
}

bool promptDirection() {
  while (true) {
    String s = promptLine("  Direction (F=forward, B=backward) > ");
    s.toUpperCase();
    if (s == "F") return true;
    if (s == "B") return false;
    Serial.println(F("  ! Enter F or B."));
  }
}

Step promptStep() {
  Step st;
  st.forward     = promptDirection();
  st.distance    = promptLong ("  Distance  (steps, 1-999999) > ", 1, 999999L);
  st.start_speed = promptFloat("  Start spd (steps/s, 1-1000) > ", 1.0f, ABS_MAX_SPEED);
  st.end_speed   = promptFloat("  End spd   (steps/s, 1-1000) > ", 1.0f, ABS_MAX_SPEED);
  st.accel       = promptFloat("  Accel     (steps/s2, -1000 to 1000) > ", -ABS_MAX_ACCEL, ABS_MAX_ACCEL);
  return st;
}

// ---- Start a move — always uses runSpeed() with per-tick speed update ----
void startStep(const Step &st) {
  stepper.setCurrentPosition(0);
  g_target_dist = st.distance;
  g_start_speed = max(1.0f, st.start_speed);
  g_end_speed   = max(1.0f, st.end_speed);
  g_accel       = st.accel;
  g_fwd         = st.forward;
  g_moving      = true;

  float max_v = max(g_start_speed, g_end_speed);
  stepper.setMaxSpeed(max_v);
  stepper.setSpeed(g_fwd ? g_start_speed : -g_start_speed);
}

// ---- Compute instantaneous speed from steps already done ----
float computeSpeed(long steps_done) {
  if (g_accel == 0.0f || g_start_speed == g_end_speed) return g_start_speed;

  float v2 = g_start_speed * g_start_speed + 2.0f * g_accel * (float)steps_done;
  if (v2 < 0.0f) v2 = 0.0f;       // deceleration floored at zero
  float v = sqrtf(v2);

  // Clamp to end_speed so we don't overshoot the target speed
  if (g_accel > 0.0f) v = min(v, g_end_speed);
  else                 v = max(v, g_end_speed);

  return max(v, 1.0f);             // never go below 1 step/s
}

// ===========================================================
//  setup()
// ===========================================================
void setup() {
  Serial.begin(9600);
  stepper.setMaxSpeed(ABS_MAX_SPEED);
  stepper.disableOutputs();
  delay(300);
  printMainMenu();
}

// ===========================================================
//  loop()
// ===========================================================
void loop() {

  // ---- Service stepper motion every loop ----
  if (g_moving) {
    long steps_done = abs(stepper.currentPosition());
    float v = computeSpeed(steps_done);
    stepper.setMaxSpeed(v);
    stepper.setSpeed(g_fwd ? v : -v);
    stepper.runSpeed();
  }

  // ---- While moving: check completion or abort ----
  if (state == STATE_MOVING_MANUAL || state == STATE_MOVING_PROG) {

    bool done = (abs(stepper.currentPosition()) >= g_target_dist);

    if (done) {
      g_moving = false;
      stepper.disableOutputs();

      if (state == STATE_MOVING_MANUAL) {
        Serial.println(F("\n[DONE] Move complete."));
        state = STATE_IDLE;
        printMainMenu();

      } else {
        progStepIndex++;
        if (progStepIndex < programCount) {
          Serial.print(F("\n[STEP ")); Serial.print(progStepIndex + 1);
          Serial.print('/'); Serial.print(programCount);
          Serial.println(F("] Starting..."));
          stepper.enableOutputs();
          startStep(program[progStepIndex]);
        } else {
          Serial.println(F("\n[DONE] Program complete."));
          state = STATE_IDLE;
          printMainMenu();
        }
      }
      return;
    }

    // Abort?
    if (Serial.available()) {
      String s = Serial.readStringUntil('\n');
      s.trim(); s.toUpperCase();
      if (s == "X") {
        stepper.setSpeed(0);
        g_moving = false;
        stepper.disableOutputs();
        Serial.println(F("\n[ABORTED] Motor stopped."));
        state = STATE_IDLE;
        printMainMenu();
      }
    }
    return;
  }

  // ---- STATE_IDLE: process commands ----
  if (!Serial.available()) return;
  String cmd = Serial.readStringUntil('\n');
  cmd.trim(); cmd.toUpperCase();
  if (cmd.length() == 0) { printMainMenu(); return; }

  char ch = cmd.charAt(0);
  switch (ch) {

  case 'M': {
    Serial.println(F("\n--- Manual Move ---"));
    Step st = promptStep();
    Serial.println(F("Starting move... (type X + Enter to abort)"));
    stepper.enableOutputs();
    startStep(st);
    state = STATE_MOVING_MANUAL;
    break;
  }

  case 'P': {
    Serial.println(F("\n--- Program Editor ---"));
    bool editing = true;
    while (editing) {
      printProgram();
      Serial.println(F("\n[A] Add step  [D n] Delete step  [Q] Back"));
      Serial.print(F("> "));
      while (!Serial.available()) {}
      String s = Serial.readStringUntil('\n');
      s.trim();
      if (s.length() == 0) continue;
      char ec = toupper(s.charAt(0));

      if (ec == 'Q') {
        editing = false;
      } else if (ec == 'A') {
        if (programCount >= MAX_STEPS) {
          Serial.println(F("! Program full (max 5 steps)."));
        } else {
          Serial.print(F("\n--- New Step ")); Serial.print(programCount + 1); Serial.println(F(" ---"));
          program[programCount] = promptStep();
          programCount++;
          Serial.println(F("Step added."));
        }
      } else if (ec == 'D') {
        if (s.length() < 3) { Serial.println(F("! Usage: D <n>")); continue; }
        int idx = s.substring(2).toInt() - 1;
        if (idx < 0 || idx >= (int)programCount) {
          Serial.println(F("! Invalid step number."));
        } else {
          for (uint8_t i = idx; i < programCount - 1; i++) program[i] = program[i + 1];
          programCount--;
          Serial.println(F("Step deleted."));
        }
      } else {
        Serial.println(F("! Use A, D <n>, or Q."));
      }
    }
    printMainMenu();
    break;
  }

  case 'R': {
    if (programCount == 0) { Serial.println(F("! Program empty.")); printMainMenu(); break; }
    progStepIndex = 0;
    Serial.print(F("\n--- Running Program (")); Serial.print(programCount);
    Serial.println(F(" step(s)) --- type X + Enter to abort ---"));
    Serial.print(F("[STEP 1/")); Serial.print(programCount); Serial.println(F("] Starting..."));
    stepper.enableOutputs();
    startStep(program[0]);
    state = STATE_MOVING_PROG;
    break;
  }

  case 'S': {
    Serial.println(F("\n--- Current Program ---"));
    printProgram();
    printMainMenu();
    break;
  }

  case 'C': {
    programCount = 0;
    Serial.println(F("Program cleared."));
    printMainMenu();
    break;
  }

  case '?': {
    Serial.println();
    printHelp();
    printMainMenu();
    break;
  }

  default: {
    Serial.print(F("! Unknown command: ")); Serial.println(cmd);
    printMainMenu();
    break;
  }
  }
}
