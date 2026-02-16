# Hapkit Serial Communication System

A lightweight, real-time safe serial protocol for communicating between:

- **Arduino firmware** (running haptic control loop)
- **Python application** (running simulation / game / controller)

Designed for:
- Haptic devices (Hapkit)
- Real-time force control
- Clean separation of control and visualization

---

# System Architecture

Arduino:
- Runs high-frequency control loop (e.g. 1000 Hz)
- Parses commands from Python
- Sends position & velocity at controlled rate
- Supports debug messaging
- Performs handshake on connection

Python:
- Connects and performs handshake
- Sends force / stiffness / damping commands
- Reads device state
- Handles debug messages
- Tracks diagnostics

---

# Communication Protocol

## Handshake

Python sends:
HELLO

Arduino responds:
READY

Connection is considered established only after READY is received.

---

## Command Format (Python → Arduino)

Format:
<COMMAND_TYPE><DELIMITER><VALUE>

Default delimiter:
(space)

Examples:

F 0.25
K 150.0
D 0.05

Command Types:

| Command | Meaning      |
|---------|--------------|
| F       | Force        |
| K       | Stiffness    |
| D       | Damping      |

---

## State Format (Arduino → Python)

Normal state packet:
<POSITION>,<VELOCITY>

Example:
0.523,0.041

Debug message:
DBG:<MESSAGE>

Example:
DBG:Limit reached

---

# Firmware Module (Arduino)

Files:
- serial_communication.h
- serial_communication.cpp

## Features

- Non-blocking serial parsing
- No dynamic memory
- Rate-controlled state transmission
- Handshake support
- Debug toggle
- Safe buffer overflow handling

## Initialization

```cpp
commInit(
    115200,   // baud rate
    100.0f,   // send rate Hz
    true,     // enable debug
    ' '       // delimiter
);
```

## In loop()

```cpp
void loop() {

    commUpdate();

    if (commCommandAvailable()) {
        char type = commGetCommandType();
        float value = commGetCommandValue();

        if (type == 'F') {
            applyForce(value);
        }
    }

    commSendState(position, velocity);
}
```

---

# Python Class: SerialCommunication

File:
serial_communication.py

## Constructor

```python
SerialCommunication(
    port="COM3",
    baudrate=115200,
    timeout=0.001,
    delimiter=' ',
    debug_enabled=False
)
```

## Connect

```python
connected = comm.connect()
```

Performs handshake automatically.

Returns True if successful.

## Close

```python
comm.close()
```

## Send Commands

```python
comm.set_force(0.2)
comm.set_stiffness(150)
comm.set_damping(0.05)
```

Or generic:

```python
comm.send_command('F', 0.25)
```

## Update Loop

Call repeatedly:

```python
comm.update()
```

Updates:

- position
- velocity
- debug messages

## Access State

```python
pos, vel = comm.get_state()
```

## Diagnostics

```python
stats = comm.get_stats()
```

Returns:

{
    "bytes_sent": int,
    "bytes_received": int,
    "packets_received": int
}

---

# Example Test Script (Python)

```python
from serial_communication import SerialCommunication
import time

comm = SerialCommunication(port="COM3", debug_enabled=True)

if not comm.connect():
    print("Connection failed")
    exit()

print("Connected!")

try:
    while True:
        comm.update()

        pos, vel = comm.get_state()
        print(f"Position: {pos:.3f}, Velocity: {vel:.3f}")

        comm.set_force(-0.5 * pos)

        time.sleep(0.01)

except KeyboardInterrupt:
    print("Closing connection")
    comm.close()
```

---

# Design Philosophy

## Real-Time Safety

Arduino:
- No blocking waits
- No dynamic memory
- Fixed-size buffers
- Deterministic execution

Python:
- Non-blocking serial reads
- Separate handshake phase
- Clear state parsing

---

# Recommended Rates

Control loop (Arduino):
1000 Hz

State transmission:
50–200 Hz

Serial baudrate:
115200 or higher

---

# Troubleshooting

## "No module named serial"

Install correct library:

```
pip uninstall serial
pip install pyserial
```

Make sure IDE uses correct virtual environment.

## Handshake Fails

- Ensure baudrate matches
- Wait 2 seconds after opening serial (Arduino reset)
- Verify Arduino prints READY when receiving HELLO

---

# Future Improvements

- Binary protocol (higher performance)
- Packet checksum
- Watchdog timeout for safety
- Automatic reconnection
- Multi-command batching
- Timestamped packets

---

# Summary

You now have:

- Structured serial protocol
- Clean firmware module
- Reusable Python communication class
- Handshake safety
- Rate control
- Debug channel
- Diagnostics tracking

This architecture cleanly separates:

Hardware control (Arduino)
Simulation / UI / AI (Python)

And is robust enough for real haptic applications.
