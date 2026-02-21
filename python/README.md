# Hapkit Serial Communication Interface

## Overview

`main.py` provides an **interactive command-line controller** for communicating with the Hapkit Arduino device. It wraps the low-level `SerialCommunication` module with a user-friendly interface for sending commands and monitoring device state in real-time.

**Key Responsibility**: This is the **application logic and UI layer**. It handles:
- User input and command parsing
- Display formatting and status updates
- Background data reception
- Error messaging and feedback

---

## Quick Start

### Prerequisites
- Python 3.7+
- `pyserial` package: `pip install pyserial`
- Arduino with Hapkit firmware running

### Running the Controller

```bash
# Navigate to the python directory
cd python

# Run the controller
python main.py
```

You should see:
```
╔════════════════════════════════════════════════════════════════╗
║         HAPKIT SERIAL COMMUNICATION INTERFACE v1.0             ║
╚════════════════════════════════════════════════════════════════╝

Configuration:
  Port:     COM5
  Baudrate: 115200

Connecting to COM5 at 115200 baud...
✓ Connected and ready!
```

### Configuration

Edit the `PORT` variable in the `main()` function (line ~208):

```python
PORT = "COM5"  # Change to your Arduino port
```

Common port values:
- **Windows**: `COM3`, `COM4`, `COM5`, `COM6`, etc.
- **Linux**: `/dev/ttyACM0`, `/dev/ttyUSB0`
- **macOS**: `/dev/cu.usbmodem*`

Find your port:
- **Windows**: Device Manager → Ports (COM & LPT)
- **Linux**: `ls /dev/tty*` or `dmesg | grep tty`
- **macOS**: `ls /dev/cu.*`

---

## Architecture

### Class Hierarchy

```
HapkitController
├── self.comm: SerialCommunication
│   └── Handles low-level protocol
├── self.running: bool
│   └── Controls loop execution
└── self.receive_thread: Thread
    └── Background data reception
```

### Execution Flow

```
main()
├─ Parse configuration
├─ Create HapkitController
└─ controller.run()
   ├─ connect()
   │  └─ Handshake with Arduino
   ├─ start_receive_loop()
   │  └─ Launch background thread
   └─ interactive_loop()
      ├─ Display status
      ├─ Prompt for user input
      └─ Process commands/system commands
         └─ Send to device or display
```

### Threading Model

```
Main Thread                          Background Thread
─────────────────────────────────    ──────────────────
interactive_loop()                   _receive_loop()
  ├─ Display status                    └─ while running:
  ├─ Prompt input        ──────────→       ├─ comm.update()
  └─ Parse/send commands                  ├─ Check debug messages
                                          └─ Sleep briefly
```

**Key Design**:
- User input blocks in main thread (waits for prompt)
- Background thread continuously reads device data
- Both threads use shared state: `comm` object
- Simple synchronization: only main thread writes commands

---

## Class Reference

### HapkitController

#### Constructor

```python
def __init__(self, port: str = "COM6", baudrate: int = 115200)
```

**Parameters:**
- **port**: Serial port name (default: "COM6")
- **baudrate**: Communication speed (default: 115200)

**What It Does:**
1. Creates a `SerialCommunication` instance
2. Initializes thread and running flag
3. Does NOT connect immediately

**Example:**
```python
controller = HapkitController(port="COM5", baudrate=115200)
```

---

#### `connect() -> bool`

Establish connection to the Arduino.

**Returns:**
- `True` if connected successfully
- `False` if connection failed

**Output:**
- Prints connection status messages
- Shows the port and baud rate being used

**Example:**
```python
if controller.connect():
    print("Ready to send commands")
else:
    print("Could not connect")
    exit(1)
```

---

#### `start_receive_loop() -> None`

Launch the background data reception thread.

**What It Does:**
1. Sets `running = True`
2. Creates a daemon thread
3. Starts the thread (runs in background)
4. Returns immediately

**Thread Behavior:**
- Calls `comm.update()` continuously
- Checks for debug messages and prints them
- Sleeps briefly to prevent busy-waiting
- Continues until `running = False`

**Example:**
```python
controller.start_receive_loop()
# Background thread now reading data
time.sleep(1)
# Main thread can do other things
```

---

#### `_receive_loop() -> None`

Background thread function (internal, called by `start_receive_loop()`).

**What It Does:**
```python
while running:
    # Read one message from device
    self.comm.update()
    
    # Check if device sent debug message
    if self.comm.last_debug_message:
        print(f"  [DEBUG] {self.comm.last_debug_message}")
        self.comm.last_debug_message = ""
    
    # Sleep briefly
    if self.comm.packet_count > 0:
        time.sleep(0.05)  # Has data: ~20 Hz display
    else:
        time.sleep(0.001)  # No data: busy-wait briefly
```

**Key Points:**
- Runs continuously in background thread
- Only prints debug messages (no sensor data)
- Adaptive sleep: shorter when idle, longer when active
- Clears debug message after printing (prevent duplicates)

**Sleep Strategy:**
- **With data**: 50ms sleep → ~20 updates/sec display
- **No data**: 1ms sleep → responsive to new data

---

#### `display_status() -> None`

Print current position and velocity to console.

**Output Format:**
```
  Position:  0.1234 m  |  Velocity:  0.5678 m/s
```

**What It Does:**
1. Gets latest state from `comm`
2. Formats with 4 decimal places (0.0000 format)
3. Uses fixed-width alignment

**Example:**
```python
controller.display_status()
# Output: "  Position:  0.1234 m  |  Velocity:  0.5678 m/s"
```

---

#### `send_command(cmd_type: str, value: float) -> None`

Send a command to the Arduino and display confirmation.

**Parameters:**
- **cmd_type**: Command identifier (e.g., "F", "S")
- **value**: Numeric command value

**Output:**
```
  → Sent: F 0.25
```

**What It Does:**
1. Calls `comm.send_command()`
2. Prints confirmation with arrow symbol

**Example:**
```python
controller.send_command("F", 0.5)  # Send force
controller.send_command("S", 1.0)  # Enable streaming
```

---

#### `show_help() -> None`

Display command reference to the user.

**Output:**
```
╔════════════════════════════════════════════════════════════════╗
║              HAPKIT COMMAND REFERENCE                          ║
╚════════════════════════════════════════════════════════════════╝

COMMAND FORMAT: TYPE VALUE
  Example: F 0.25
  
CONTROL COMMANDS:
  S 0        Disable data streaming
  S 1        Enable data streaming
  
SYSTEM COMMANDS:
  help       Show this help message
  status     Display current position and velocity
  stats      Show communication statistics
  clear      Clear screen
  quit/exit  Disconnect and exit
```

**Invoked By:**
- User typing "help"
- Part of startup banner

---

#### `show_stats() -> None`

Display communication statistics.

**Output:**
```
  ╔═══════════════════════════════════╗
  ║   COMMUNICATION STATISTICS        ║
  ╠═══════════════════════════════════╣
  ║ Bytes Sent:              1234 B   ║
  ║ Bytes Received:          5678 B   ║
  ║ Packets Received:          120    ║
  ║ Connected:               True     ║
  ╚═══════════════════════════════════╝
```

**What It Does:**
1. Gets stats from `comm.get_stats()`
2. Gets connection status
3. Formats and displays in a table

**Useful For:**
- Monitoring data flow
- Debugging connection issues
- Verifying device is sending packets

**Invoked By:**
- User typing "stats"

---

#### `interactive_loop() -> None`

Main user interaction loop (runs after connection).

**What It Does:**
```
while running:
    └─ display_status()           ← Show current state
    └─ input("> ")                ← Wait for user command
    └─ Parse and process command
        ├─ System commands (quit, help, stats, etc.)
        ├─ Stream control (stream on/off)
        └─ Raw commands (TYPE VALUE format)
```

**Features:**
- Displays status before each prompt
- Handles empty input (ignored)
- Case-insensitive command parsing
- Comprehensive error messages
- Catches KeyboardInterrupt (Ctrl+C) gracefully

**Command Categories:**
1. **System Commands**: Built-in, case-insensitive
2. **Utility Commands**: Special shortcuts (stream on/off)
3. **Raw Commands**: User format (TYPE VALUE)

---

#### `disconnect() -> None`

Close connection and clean up threads.

**What It Does:**
1. Sets `running = False`
2. Waits for receive thread to exit (1 second timeout)
3. Closes serial connection
4. Prints disconnect message

**Exit Conditions:**
- User types "quit" or "exit"
- User presses Ctrl+C
- An uncaught exception occurs

**Example:**
```python
controller.disconnect()
# All resources cleaned up, safe to exit
```

---

#### `run() -> bool`

Execute the complete controller lifecycle.

**What It Does:**
```
1. connect()
   └─ Try handshake, return False if fails
2. start_receive_loop()
   └─ Launch background thread
3. interactive_loop()
   └─ User interaction until quit
```

**Returns:**
- `True` if completed successfully
- `False` if connection failed

**Example:**
```python
controller = HapkitController(port="COM5")
if controller.run():
    print("Session ended normally")
    exit(0)
else:
    print("Could not start session")
    exit(1)
```

---

## Command Format Reference

### System Commands

| Command | Effect |
|---------|--------|
| `help` | Display command reference |
| `status` | Show current position/velocity |
| `stats` | Show communication statistics |
| `clear` | Clear the terminal screen |
| `quit`, `exit` | Disconnect and exit |

### Utility Shortcuts

| Command | Equivalent | Purpose |
|---------|-----------|---------|
| `stream on` | `S 1` | Enable data streaming |
| `stream off` | `S 0` | Disable data streaming |

### Raw Commands

**Format:** `TYPE VALUE`

| Type | Value Range | Example | Purpose |
|------|-------------|---------|---------|
| `F` | 0.0 to 1.0 | `F 0.25` | Set force magnitude |
| `S` | 0 or 1 | `S 1` | Enable/disable streaming |
| Custom | Device-specific | `X 0.5` | Device-defined commands |

**Notes:**
- Type is case-insensitive (converted to uppercase)
- Value must be a valid number (int or float)
- Extra spaces are automatically trimmed

---

## Typical Usage Session

### Example 1: Basic Monitoring

```
> help
[Shows command reference]

> stream on
  → Sent: S 1
  Position:  0.0000 m  |  Velocity:  0.0000 m/s
  Position:  0.0012 m  |  Velocity:  0.0034 m/s
  Position:  0.0024 m  |  Velocity:  0.0067 m/s

> stats
  [Shows communication statistics]

> stream off
  → Sent: S 0

> quit
Disconnecting...
✓ Disconnected
```

### Example 2: Sending Commands

```
> S 1
  → Sent: S 1

> F 0.5
  → Sent: F 0.5

> status
  Position:  0.0567 m  |  Velocity:  0.1234 m/s

> quit
```

### Example 3: Error Handling

```
> F abc
  ❌ Invalid value: 'abc' is not a number

> F
  ❌ Invalid format. Use: TYPE VALUE (e.g., 'F 0.25')
     Or type 'help' for more information

> F 0.5 extra
  ❌ Invalid format. Use: TYPE VALUE (e.g., 'F 0.25')
     Or type 'help' for more information
```

---

## Input Validation

The controller validates all user input:

| Input | Validation | Result |
|-------|-----------|--------|
| Empty line | Accepted | Ignored, prompt again |
| `help` | System command | Display help |
| `F 0.5` | Valid format | Send command |
| `F abc` | Invalid value | Error: not a number |
| `F` | Too few parts | Error: invalid format |
| `F 0.5 0.3` | Too many parts | Error: invalid format |

---

## Threading & Synchronization

### Design Philosophy

**Simple, non-blocking architecture:**
- Main thread handles user input (blocking)
- Background thread handles device input (non-blocking)
- Minimal shared state
- No complex locking

### Shared State

| Variable | Who Reads | Who Writes | Safety |
|----------|-----------|-----------|--------|
| `comm.position` | Main/Background | Background | Occasional stale reads OK |
| `comm.velocity` | Main/Background | Background | Occasional stale reads OK |
| `comm.last_debug_message` | Background | Background | Single writer |
| `running` | Background | Main thread | Atomic boolean |

### Thread Safety Notes

- Position/velocity read in main thread may be 0-50ms stale
- Debug messages processed by background thread
- Commands sent from main thread only
- No complex synchronization needed

---

## Exit Scenarios

### Normal Exit (quit/exit command)
```
> quit
Disconnecting...
✓ Disconnected
[Program exits with code 0]
```

### Abnormal Exit (Ctrl+C)
```
^C
Interrupt received. Disconnecting...
✓ Disconnected
[Program exits with code 1]
```

### Connection Failure
```
Connecting to COM5 at 115200 baud...
❌ Connection failed! Check port and Arduino connection.
[Program exits immediately with code 1]
```

### Unhandled Exception
```
❌ Error: [exception details]
Interrupt received. Disconnecting...
✓ Disconnected
```

---

## Troubleshooting

### Problem: "Connection failed"

**Cause**: Cannot establish handshake with Arduino

**Solutions:**
1. Check port number: verify in Device Manager
2. Check Arduino is powered and USB connected
3. Verify Arduino has Hapkit firmware uploaded
4. Try different handshake_timeout in configuration
5. Check USB cable quality

### Problem: No data appearing

**Cause**: Streaming is disabled or not started

**Solutions:**
1. Type `stream on` to enable
2. Type `status` to verify device is responsive
3. Type `stats` to check if packets are being received

### Problem: Garbled/weird characters in output

**Cause**: Wrong baud rate or corrupted data

**Solutions:**
1. Verify baud rate matches Arduino (default 115200)
2. Check USB cable quality
3. Try shorter cable
4. Restart Arduino and application

### Problem: Application hangs on input prompt

**Cause**: Normal—application waits for user input

**Solution**: This is by design. Type a command or "quit" to proceed.

---

## Performance Characteristics

### CPU Usage
- **Idle** (no input, no data): ~1% (background thread sleeps)
- **Streaming** (active data): ~2-3% (periodic sleep)
- **User input**: >50% momentarily (processing input)

### Memory
- **Base**: ~10-20 MB (Python + libraries)
- **Streaming**: No growth (doesn't queue messages)

### Latency
- **Command to send**: <1ms after user types (if on input prompt)
- **Device data to display**: 1-50ms (depends on background thread sleep rate)
- **Display refresh**: ~20 Hz (50ms sleep rate)

---

## Integration with SerialCommunication Module

`HapkitController` wraps `SerialCommunication`:

```python
# Low-level (in SerialCommunication):
self.comm.send_command("F", 0.5)
self.comm.update()

# High-level (in HapkitController):
self.send_command("F", 0.5)           # ← Wraps and prints
self._receive_loop() calls update()   # ← Wraps and prints debug
```

**Key Separation:**
- `SerialCommunication`: Raw protocol, no I/O
- `HapkitController`: User interface, display formatting

---

## API Summary

| Method | Purpose |
|--------|---------|
| `__init__()` | Create controller |
| `connect()` | Connect to device |
| `start_receive_loop()` | Launch background thread |
| `display_status()` | Print current state |
| `send_command()` | Send command and show confirmation |
| `show_help()` | Display command reference |
| `show_stats()` | Display statistics |
| `interactive_loop()` | Main user input loop |
| `disconnect()` | Close connection and stop threads |
| `run()` | Execute complete session |

---

## Example: Extend with Custom Commands

If you want to add a custom command:

```python
# In interactive_loop(), after "stream off" check:

elif user_input.lower() == "reset":
    self.send_command("R", 0.0)  # Reset command

elif user_input.lower() == "calibrate":
    self.send_command("C", 1.0)  # Calibrate command
```

Then use from CLI:
```
> reset
  → Sent: R 0.0

> calibrate
  → Sent: C 1.0
```

---

## Summary

`main.py` provides:
- ✓ Interactive command-line interface
- ✓ Real-time status monitoring
- ✓ Background data reception
- ✓ Comprehensive error handling
- ✓ User-friendly command format
- ✓ Clean separation from low-level protocol

For lower-level control or scripting, use `SerialCommunication` directly.
