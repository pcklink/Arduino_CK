# Microinjector GUI

A cross-platform desktop GUI (**macOS · Linux · Windows**) for the `microinject.ino` Arduino firmware. Replaces the Serial Monitor with a polished control panel.

---

## Requirements

- Python 3.10 or newer
- `pip install PyQt6 pyserial`

Or install from the requirements file:

```bash
cd microinject/gui
pip install -r requirements.txt
```

---

## Running

```bash
python microinject_gui.py
```

---

## Features

| Panel           | What it does                                                |
| --------------- | ----------------------------------------------------------- |
| **Manual Move** | Set direction, distance, speed, acceleration — click Move   |
| **Program**     | Add / delete up to 5 sequential steps, then Run all at once |
| **Serial Log**  | Live scrolling view of every message from the Arduino       |
| **ABORT**       | Immediately sends `X` to gracefully decelerate the motor    |

### Connection
1. Select the Arduino's COM/tty port from the dropdown and click **Refresh** if it does not appear.
2. Leave baud at **9600** (must match the firmware).
3. Click **Connect** — the Serial Log shows the firmware menu once the Arduino resets.

### Manual Move
Fill in the four parameters and click **Move Motor**. The GUI automatically replies to each firmware prompt — no manual typing needed.

### Program Editor
- **Add Step** opens a dialog; the step is sent to the firmware immediately after.
- **Delete Step** removes the selected table row from both the GUI and the firmware.
- **Clear All** wipes the entire program (`C` command).
- **Run Program** executes all steps in sequence (`R` command).

### ABORT
Active (red glow) only while the motor is running. Sends `X\n` — the firmware ramps the motor to a smooth stop.

---

## Notes

- **2048 steps = 1 full revolution** of the 28BYJ-48 motor.
- Speed and acceleration range: **1 – 1000 steps/s** and **steps/s²**.
- The GUI mirrors firmware state via log parsing; if the Arduino is reset mid-session, click **Disconnect → Connect** to re-sync.

---

## File structure

```
microinject/
├── microinject.ino
├── README.md
└── gui/
    ├── microinject_gui.py   ← this app
    ├── requirements.txt
    └── README_GUI.md        ← this file
```
