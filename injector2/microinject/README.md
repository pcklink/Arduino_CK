# Microinjector — Arduino Firmware

> **Hardware:** Arduino Nano · ULN2003 driver board · 28BYJ-48 stepper motor  
> **Library:** [AccelStepper](https://www.airspayce.com/mikem/arduino/AccelStepper/)  
> **Interface:** Serial Monitor (9600 baud, **Newline** line ending)

---

## Overview

`microinject.ino` turns an Arduino Nano into a stepper-motor controller for a microinjector built around a lead-screw drive. It provides two modes of operation:

| Mode            | Description                                                                            |
| --------------- | -------------------------------------------------------------------------------------- |
| **Manual move** | Enter direction, distance, speed, and acceleration on demand — motor moves immediately |
| **Program**     | Store up to 5 sequential steps and run them all at once with a single command          |

All interaction is through the Arduino IDE's **Serial Monitor**. A graphical UI is planned for a future version.

---

## Hardware Wiring

| ULN2003 pin | Arduino Nano pin |
| ----------- | ---------------- |
| IN1         | D8               |
| IN2         | D10              |
| IN3         | D9               |
| IN4         | D11              |
| VCC         | 5 V              |
| GND         | GND              |

> The pin order IN1-IN3-IN2-IN4 → D8, D9, D10, D11 is intentional — it produces the correct half-step sequence for the 28BYJ-48.

---

## Upload Instructions

1. Install the **AccelStepper** library via *Sketch → Include Library → Manage Libraries*, search for **AccelStepper** by Mike McCauley.
2. Open `microinject/microinject.ino` in the Arduino IDE.
3. **Tools → Board** → *Arduino Nano*
4. **Tools → Processor** → *ATmega328P (Old Bootloader)* *(try this if upload fails)*
5. **Tools → Port** → select your board's port
6. Click **Upload**
7. Open **Tools → Serial Monitor**, set baud to **9600** and line ending to **Newline**
8. The main menu appears automatically on reset.

---

## Main Menu

```
----------------------------
  MICROINJECTOR  v1.0
----------------------------
  [M] Manual move
  [P] Edit program
  [R] Run program
  [S] Show program
  [C] Clear program
  [?] Help / units
----------------------------
  Steps stored: 0
----------------------------
Enter command >
```

Type the letter and press **Enter**.

---

## Commands

### `M` — Manual Move

Prompts for four parameters, then moves the motor immediately:

```
--- Manual Move ---
  Direction (F=forward, B=backward) > F
  Distance  (steps, 1 - 999999) > 2048
  Speed     (steps/s, 1 - 1000) > 300
  Accel     (steps/s2, 1 - 1000) > 100
Starting move... (type X + Enter to abort)

[DONE] Move complete.
```

**2048 steps = exactly one full revolution** of the 28BYJ-48.

---

### `P` — Edit Program

Opens the program editor. Up to **5 steps** can be stored.

```
[A] Add step  [D n] Delete step  [Q] Back
> A

--- New Step 1 ---
  Direction > F
  Distance  > 1024
  Speed     > 200
  Accel     > 80
Step added.
```

| Editor command | Action                                         |
| -------------- | ---------------------------------------------- |
| `A`            | Add a new step (prompts for all parameters)    |
| `D 2`          | Delete step number 2; remaining steps shift up |
| `Q`            | Return to main menu                            |

---

### `R` — Run Program

Executes all stored steps in order, printing progress as each step starts:

```
--- Running Program (3 step(s)) --- type X + Enter to abort ---
[STEP 1/3] Starting...

[STEP 2/3] Starting...

[STEP 3/3] Starting...

[DONE] Program complete.
```

---

### `S` — Show Program

Prints the stored steps as a table:

```
#  Dir  Distance(steps)  Speed(sps)  Accel(sps2)
----------------------------
1  F    1024             200         80
2  B    512              150         60
3  F    2048             500         200
```

---

### `C` — Clear Program

Deletes all stored steps immediately.

---

### `?` — Help

Prints unit and limit information:

```
Units & limits:
  Distance : steps  (2048 = 1 full revolution)
  Speed    : steps/s  (1 - 1000)
  Accel    : steps/s2  (1 - 1000)
  Direction: F = forward, B = backward
During a move type X + Enter to abort.
```

---

### `X` — Abort (during a move)

Type `X` and press **Enter** while the motor is running. The motor decelerates smoothly to a stop rather than halting abruptly.

---

## Unit Reference

| Parameter    | Range             | Notes                        |
| ------------ | ----------------- | ---------------------------- |
| Distance     | 1 – 999 999 steps | 2048 steps = 1 revolution    |
| Speed        | 1 – 1000 steps/s  | Higher values may miss steps |
| Acceleration | 1 – 1000 steps/s² | Low values = gentle ramp     |
| Direction    | F / B             | Forward / Backward           |

---

## Lead-Screw Conversion

Once you know your lead-screw pitch (mm per revolution), convert physical distances to steps:

```
steps = (distance_mm / pitch_mm) × 2048
```

**Example** — 2 mm/rev lead screw, inject 0.5 mm:
```
steps = (0.5 / 2.0) × 2048 = 512 steps
```

---

## Power Management

The firmware calls `disableOutputs()` when the motor is idle, cutting current to all four coils. This prevents heat build-up in the motor and driver — important for a continuously powered injector benchtop setup.

---

## File Structure

```
injector2/
├── accelstepper/
│   └── accelstepper.ino   ← original simple demo (bounce back and forth)
└── microinject/
    ├── microinject.ino    ← this firmware
    └── README.md          ← this file
```

---

## Future Work

- Graphical UI (Python/Qt or web-based) communicating over the same serial commands
- Physical unit entry (mm) with automatic step conversion
- Persistent program storage in EEPROM (survives power-off)
- Flow-rate display based on lead-screw pitch and syringe diameter
