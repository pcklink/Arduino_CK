// ============================================================
//  Microinjector Firmware
//  Hardware: Arduino Nano + ULN2003 + 28BYJ-48 stepper
//  Library:  AccelStepper (4-wire half-step, MotorInterfaceType 4)
//  Serial:   9600 baud, newline line-ending
// ============================================================
#include <AccelStepper.h>

// ---- Pin mapping (IN1-IN3-IN2-IN4 for correct 28BYJ-48 step sequence) ----
#define IN1 8
#define IN2 10
#define IN3 9
#define IN4 11

// ---- Motor constants ----
#define MOTOR_INTERFACE_TYPE 4 // 4-wire half-step
#define STEPS_PER_REV 2048L    // 28BYJ-48 full revolution
#define ABS_MAX_SPEED 1000.0f
#define ABS_MAX_ACCEL 1000.0f

// ---- Program storage ----
#define MAX_STEPS 5

struct Step {
  bool forward;  // true = forward, false = backward
  long distance; // steps (positive)
  float speed;   // steps/s
  float accel;   // steps/s²
};

Step program[MAX_STEPS];
uint8_t programCount = 0;

// ---- Constant-speed mode flag (set when accel == 0) ----
bool g_const_speed = false;
long g_target_dist = 0;

// ---- State machine ----
enum State {
  STATE_IDLE,          // showing main menu, waiting for command
  STATE_MOVING_MANUAL, // executing a manual move
  STATE_MOVING_PROG,   // executing program step n
};

State state = STATE_IDLE;
uint8_t progStepIndex = 0; // which program step is currently running

// ---- AccelStepper instance ----
AccelStepper stepper(MOTOR_INTERFACE_TYPE, IN1, IN2, IN3, IN4);

// ===========================================================
//  Helpers
// ===========================================================

void printDivider() { Serial.println(F("----------------------------")); }

void printMainMenu() {
  printDivider();
  Serial.println(F("  MICROINJECTOR  v1.0"));
  printDivider();
  Serial.println(F("  [M] Manual move"));
  Serial.println(F("  [P] Edit program"));
  Serial.println(F("  [R] Run program"));
  Serial.println(F("  [S] Show program"));
  Serial.println(F("  [C] Clear program"));
  Serial.println(F("  [?] Help / units"));
  printDivider();
  Serial.print(F("  Steps stored: "));
  Serial.println(programCount);
  printDivider();
  Serial.println(F("Enter command > "));
}

void printHelp() {
  Serial.println(F("Units & limits:"));
  Serial.println(F("  Distance : steps  (2048 = 1 full revolution)"));
  Serial.println(F("  Speed    : steps/s  (1 - 1000)"));
  Serial.println(F("  Accel    : steps/s2  (1 - 1000)"));
  Serial.println(F("  Direction: F = forward, B = backward"));
  Serial.println(F("During a move type X + Enter to abort."));
}

void printProgram() {
  if (programCount == 0) {
    Serial.println(F("Program is empty."));
    return;
  }
  Serial.println(F("#  Dir  Distance(steps)  Speed(sps)  Accel(sps2)"));
  printDivider();
  for (uint8_t i = 0; i < programCount; i++) {
    Serial.print(i + 1);
    Serial.print(F("  "));
    Serial.print(program[i].forward ? 'F' : 'B');
    Serial.print(F("    "));
    Serial.print(program[i].distance);
    Serial.print(F("             "));
    Serial.print((int)program[i].speed);
    Serial.print(F("         "));
    Serial.println((int)program[i].accel);
  }
}

// ---- Blocking prompt: read a trimmed string from serial ----
String promptLine(const char *msg) {
  Serial.print(msg);
  while (!Serial.available()) { /* wait */
  }
  String s = Serial.readStringUntil('\n');
  s.trim();
  return s;
}

// ---- Prompt a float, re-ask until valid & in range ----
float promptFloat(const char *msg, float minVal, float maxVal) {
  float val;
  while (true) {
    String s = promptLine(msg);
    val = s.toFloat();
    if (val >= minVal && val <= maxVal)
      return val;
    Serial.print(F("  ! Out of range ("));
    Serial.print(minVal);
    Serial.print(F(" - "));
    Serial.print(maxVal);
    Serial.println(F("), try again."));
  }
}

// ---- Prompt a long integer ----
long promptLong(const char *msg, long minVal, long maxVal) {
  long val;
  while (true) {
    String s = promptLine(msg);
    val = s.toInt();
    if (val >= minVal && val <= maxVal)
      return val;
    Serial.print(F("  ! Out of range ("));
    Serial.print(minVal);
    Serial.print(F(" - "));
    Serial.print(maxVal);
    Serial.println(F("), try again."));
  }
}

// ---- Prompt direction (F/B), return true = forward ----
bool promptDirection() {
  while (true) {
    String s = promptLine("  Direction (F=forward, B=backward) > ");
    s.toUpperCase();
    if (s == "F")
      return true;
    if (s == "B")
      return false;
    Serial.println(F("  ! Enter F or B."));
  }
}

// ---- Collect all move parameters into a Step struct ----
Step promptStep() {
  Step st;
  st.forward = promptDirection();
  st.distance = promptLong("  Distance  (steps, 1 - 999999) > ", 1, 999999L);
  st.speed =
      promptFloat("  Speed     (steps/s, 1 - 1000) > ", 1.0f, ABS_MAX_SPEED);
  st.accel =
      promptFloat("  Accel     (steps/s2, 0 - 1000) > ", 0.0f, ABS_MAX_ACCEL);
  return st;
}

// ---- Apply AccelStepper settings and kick off a move ----
void startStep(const Step &st) {
  stepper.setCurrentPosition(0);
  if (st.accel == 0) {
    // Constant speed — use runSpeed(), no ramp
    g_const_speed = true;
    g_target_dist = st.distance;
    float spd = st.forward ? (float)st.speed : -(float)st.speed;
    stepper.setMaxSpeed(abs(spd));
    stepper.setSpeed(spd);
  } else {
    g_const_speed = false;
    long target = st.forward ? st.distance : -st.distance;
    stepper.setMaxSpeed(st.speed);
    stepper.setAcceleration(st.accel);
    stepper.moveTo(target);
  }
}

// ===========================================================
//  setup()
// ===========================================================
void setup() {
  Serial.begin(9600);
  stepper.setMaxSpeed(ABS_MAX_SPEED);
  stepper.setAcceleration(50.0f);
  stepper.disableOutputs(); // power off coils until a move begins
  delay(300);
  printMainMenu();
}

// ===========================================================
//  loop()
// ===========================================================
void loop() {

  // ---- Always service stepper motion ----
  if (g_const_speed) {
    stepper.runSpeed();
  } else {
    stepper.run();
  }

  // ---- While moving: check for completion or abort ----
  if (state == STATE_MOVING_MANUAL || state == STATE_MOVING_PROG) {

    // Move finished?
    bool done = g_const_speed
                    ? (abs(stepper.currentPosition()) >= g_target_dist)
                    : (stepper.distanceToGo() == 0);

    if (done) {
      stepper.disableOutputs(); // cut coil current when done
      g_const_speed = false;

      if (state == STATE_MOVING_MANUAL) {
        Serial.println(F("\n[DONE] Move complete."));
        state = STATE_IDLE;
        printMainMenu();

      } else {
        // Program step done — advance to next
        progStepIndex++;
        if (progStepIndex < programCount) {
          Serial.print(F("\n[STEP "));
          Serial.print(progStepIndex + 1);
          Serial.print('/');
          Serial.print(programCount);
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

    // Abort requested?
    if (Serial.available()) {
      String s = Serial.readStringUntil('\n');
      s.trim();
      s.toUpperCase();
      if (s == "X") {
        if (g_const_speed) {
          stepper.setSpeed(0); // immediate stop — no ramp in const-speed mode
          g_const_speed = false;
        } else {
          stepper.stop(); // ramp down to stop
          while (stepper.distanceToGo() != 0)
            stepper.run();
        }
        stepper.disableOutputs();
        Serial.println(F("\n[ABORTED] Motor stopped."));
        state = STATE_IDLE;
        printMainMenu();
      }
    }
    return; // skip menu processing while moving
  }

  // ---- STATE_IDLE: process serial commands ----
  if (!Serial.available())
    return;

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  cmd.toUpperCase();
  if (cmd.length() == 0) {
    printMainMenu();
    return;
  }

  char ch = cmd.charAt(0);

  switch (ch) {

  // ---- Manual move ----------------------------------------
  case 'M': {
    Serial.println(F("\n--- Manual Move ---"));
    Step st = promptStep();
    Serial.println(F("Starting move... (type X + Enter to abort)"));
    stepper.enableOutputs();
    startStep(st);
    state = STATE_MOVING_MANUAL;
    break;
  }

  // ---- Edit program ---------------------------------------
  case 'P': {
    Serial.println(F("\n--- Program Editor ---"));
    bool editing = true;
    while (editing) {
      printProgram();
      Serial.println(F("\n[A] Add step  [D n] Delete step  [Q] Back"));
      Serial.print(F("> "));
      while (!Serial.available()) {
      }
      String s = Serial.readStringUntil('\n');
      s.trim();
      if (s.length() == 0)
        continue;

      char ec = toupper(s.charAt(0));
      if (ec == 'Q') {
        editing = false;

      } else if (ec == 'A') {
        if (programCount >= MAX_STEPS) {
          Serial.println(
              F("! Program full (max 5 steps). Delete a step first."));
        } else {
          Serial.print(F("\n--- New Step "));
          Serial.print(programCount + 1);
          Serial.println(F(" ---"));
          program[programCount] = promptStep();
          programCount++;
          Serial.println(F("Step added."));
        }

      } else if (ec == 'D') {
        // Expect "D n" where n is 1-based step number
        if (s.length() < 3) {
          Serial.println(F("! Usage: D <step_number>  e.g. D 2"));
          continue;
        }
        int idx = s.substring(2).toInt() - 1; // convert to 0-based
        if (idx < 0 || idx >= (int)programCount) {
          Serial.println(F("! Invalid step number."));
        } else {
          for (uint8_t i = idx; i < programCount - 1; i++) {
            program[i] = program[i + 1]; // shift steps down
          }
          programCount--;
          Serial.println(F("Step deleted."));
        }

      } else {
        Serial.println(F("! Unknown command. Use A, D <n>, or Q."));
      }
    }
    printMainMenu();
    break;
  }

  // ---- Run program ----------------------------------------
  case 'R': {
    if (programCount == 0) {
      Serial.println(F("! Program is empty. Use [P] to add steps."));
      printMainMenu();
      break;
    }
    progStepIndex = 0;
    Serial.print(F("\n--- Running Program ("));
    Serial.print(programCount);
    Serial.println(F(" step(s)) --- type X + Enter to abort ---"));
    Serial.print(F("[STEP 1/"));
    Serial.print(programCount);
    Serial.println(F("] Starting..."));
    stepper.enableOutputs();
    startStep(program[0]);
    state = STATE_MOVING_PROG;
    break;
  }

  // ---- Show program ---------------------------------------
  case 'S': {
    Serial.println(F("\n--- Current Program ---"));
    printProgram();
    printMainMenu();
    break;
  }

  // ---- Clear program --------------------------------------
  case 'C': {
    programCount = 0;
    Serial.println(F("Program cleared."));
    printMainMenu();
    break;
  }

  // ---- Help -----------------------------------------------
  case '?': {
    Serial.println();
    printHelp();
    printMainMenu();
    break;
  }

  default: {
    Serial.print(F("! Unknown command: "));
    Serial.println(cmd);
    printMainMenu();
    break;
  }
  }
}
