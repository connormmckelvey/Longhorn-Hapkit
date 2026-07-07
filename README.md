# Haptic Robotics Education Ecosystem
Designed for Dr. Fey's HERO (Haptics and Medical Robotics) Lab at Texas Robotics (The University of Texas at Austin).

This ecosystem provides an interactive learning platform for studying 1-Degree-of-Freedom (1DOF) and 2-Degree-of-Freedom (2DOF) haptic devices. It bridges high-frequency real-time microcontroller control loops (Arduino) with interactive visual simulations (Python) using a robust, low-latency communication protocol.

---

## System Architecture

The ecosystem splits haptic rendering and visualization into two decoupled layers:

```
┌─────────────────────────────────┐
│     Microcontroller (1 kHz)     │  ◄── Encoders & Motor Output (Hapkit)
│  (Real-Time Force/Control Loop) │
└────────────────┬────────────────┘
                 │
                 │  Haplink (Serial Protocol @ 115200 Baud)
                 ▼
┌─────────────────────────────────┐
│        Python Application       │  ◄── User Interface / Visual Physics Engine
│     (Tkinter / Pygame / CLI)    │
└─────────────────────────────────┘
```

1. **Hardware & Firmware (Arduino Uno / ATmega328P)**:
   - Runs a deterministic control loop at 1 kHz to read encoders, calculate device kinematics, apply haptic force effects, and drive motors via PWM.
   - Utilizes Haplink (available at https://github.com/connormmckelvey/haplink) to communicate parameters and telemetry with the host PC.
2. **Communication (Haplink)**:
   - A packet-based binary/text serial protocol designed to share variables (parameters and telemetry) between the microchip and the PC without blocking the real-time haptic loop. Learn more at https://github.com/connormmckelvey/haplink.
3. **Application & Physics (Python)**:
   - Connects to the haptic device, reads position/velocity telemetry, updates graphical environments in real time, and sends force command variables (like road curvature slope or obstacle bounds) back to the device.

---

## Project Directory Structure

```
├── .pio/                       # PlatformIO build artifacts (compiled firmware)
├── .venv/                      # Python virtual environment containing dependencies
├── lib/
│   └── serial_communication/   # Core serial communication docs and libraries
├── python/                     # Python visual simulations and connector tools
│   ├── main.py                 # Multi-threaded interactive CLI mode selector
│   ├── car-game.py             # Pygame driving game with steering feedback
│   ├── rect_editor_2dof.py     # GUI editor to modify and send 2DOF haptic obstacles
│   ├── bump_changer.py         # Script to test and modify dynamic haptic bumps
│   └── test_raw_serial.py      # Basic script to test connection and raw inputs
├── src/
│   ├── main.cpp                # 1DOF firmware source (Hapkit haptic effects & game)
│   └── main2DOF.cpp            # 2DOF firmware source (forward/inverse kinematics & workspace)
├── platformio.ini              # PlatformIO project configuration file
└── README.md                   # This project manual
```

---

## Setup & Installation

### 1. Python Environment Setup
Activate the pre-configured Python virtual environment (`.venv`) and ensure your dependencies are installed.

**For Windows (PowerShell):**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.venv\Scripts\Activate.ps1
```

**Install Pygame and Tkinter dependencies (if not already installed):**
```bash
pip install pygame pyserial haplink
```

### 2. Firmware Compilation & Upload
The ecosystem compiles either the 1DOF or 2DOF firmware to the Arduino board. You can select which firmware to compile inside the platformio.ini file by commenting/uncommenting the corresponding build_src_filter line.

Open [platformio.ini](file:///C:/Users/conno/OneDrive/Documents/PlatformIO/Projects/Hapkit%20Arduino/platformio.ini) and modify:

```ini
; --- Haptic Device Configuration (Toggle build between 1DOF and 2DOF) ---
; Compile 1DOF (src/main.cpp)
build_src_filter = +<*> -<main2DOF.cpp>

; Compile 2DOF (src/main2DOF.cpp)
; build_src_filter = +<*> -<main.cpp>
```

#### Upload via PlatformIO CLI:
```bash
# Upload to the connected microcontroller
pio run --target upload
```

---

## How to Run

### Interactive CLI Connector (main.py)
Run the interactive CLI to test telemetry and switch between haptic modes manually.
```bash
python python/main.py [PORT]
# Example: python python/main.py COM5
```
Once connected, you can input a mode name (e.g., CAR_GAME or BOX_OBSTACLE) or number, or press Enter to read the current telemetry coordinates.

---

### 1DOF Haptic Steering Game (car-game.py)
A classic arcade-style perspective driving simulator.
1. Flash the 1DOF firmware ([src/main.cpp](file:///C:/Users/conno/OneDrive/Documents/PlatformIO/Projects/Hapkit%20Arduino/src/main.cpp)) to your Hapkit.
2. Run the game:
   ```bash
   python python/car-game.py
   ```
3. **Steering Feel Features**:
   - **Power Steering**: Stiffens self-centering force as speed increases.
   - **Road Curves**: Pulls the wheel in the direction of upcoming curves.
   - **Rumble Strips**: Buzzes the motor at 20-30 Hz when crossing lane boundaries.
   - **Off-road Damping**: Adds heavy damping to simulate dirt.
   - **Collision Jolt**: Delivers a physical impact impulse if you crash.

---

### 2DOF Workspace Obstacle Editor (rect_editor_2dof.py)
A graphical tool to draw rectangular boxes on screen and physically feel them through the 2DOF Hapkit.
1. Flash the 2DOF firmware ([src/main2DOF.cpp](file:///C:/Users/conno/OneDrive/Documents/PlatformIO/Projects/Hapkit%20Arduino/src/main2DOF.cpp)) to your Hapkit.
2. Run the editor:
   ```bash
   python python/rect_editor_2dof.py
   ```
3. Draw a box on the Tkinter canvas. The box coordinates will be uploaded in real-time to the Hapkit via Haplink. When moving the 2DOF end-effector, the motors will render rigid wall forces around the box boundaries.

---

## Supported Haptic Modes

### 1-Degree-of-Freedom Firmware ([src/main.cpp](file:///C:/Users/conno/OneDrive/Documents/PlatformIO/Projects/Hapkit%20Arduino/src/main.cpp))
*   `0: ZERO` - Neutral state with zero motor torque.
*   `1: SPRING` - Hooke's Law self-centering spring (F = -kx).
*   `2: DAMPER` - Viscous damping opposing velocity (F = -bv).
*   `3: SPRING_DAMPER` - Coupled spring and viscous damper.
*   `4: WALL` - Virtual rigid boundary with high stiffness.
*   `5: BUMP_VALLEY` - Textural detents (force valleys and hills).
*   `6: TEXTURE` - Dynamic friction / sand textures.
*   `7: CAR_GAME` - Specialized mode controlled by car-game.py.

### 2-Degree-of-Freedom Firmware ([src/main2DOF.cpp](file:///C:/Users/conno/OneDrive/Documents/PlatformIO/Projects/Hapkit%20Arduino/src/main2DOF.cpp))
*   `0: ZERO` - Neutral state.
*   `1: JOYSTICK` - 2D centering spring pulling the end-effector to the origin.
*   `2: GRID` - Grid of magnetic-like detent coordinates.
*   `3: CIRCLES` - 2D circular boundary wells.
*   `4: HARP` - 1D virtual strings to pluck in the 2D workspace.
*   `5: DAMP` - Omnidirectional 2D viscous damping.
*   `6: WALL` - Boundary walls restricting motion.
*   `7: JOYSTICK_DAMPED` - Coupled 2D centering spring and damping.
*   `8: BOX_OBSTACLE` - Rectangular box environment configured via rect_editor_2dof.py.

---

## Real-Time & Safety Guidelines

1. **Keep the Haptic Loop Deterministic**:
   - The Arduino Interrupt Service Routine (ISR) runs at 1 kHz. Never perform blocking actions (like delay(), standard Serial.print(), or Serial.read()) inside the ISR.
2. **Avoid raw Serial.print()**:
   - Haplink uses the hardware serial port for binary packet transfers. Printing custom debug strings to Serial will corrupt the packet stream. Instead, use the registered variables or Haplink's built-in telemetry registers to send diagnostic values to your Python scripts.
3. **Motor Voltage Limits**:
   - Ensure the external power supply voltage matches the motor specs to avoid overheating or driver board failures during high-stiffness rendering (e.g., WALL modes).
