# Serial Communication Module

## Overview

The `SerialCommunication` class manages low-level serial communication with the Hapkit Arduino firmware. It handles the protocol for sending commands and receiving sensor data, providing a clean interface for applications that need to interact with the hardware.

**Key Responsibility**: This module is **purely a communication layer**. It does not handle user input, display formatting, or business logic—those are the caller's responsibility.

---

## Architecture

### Message Protocol

The module implements a simple text-based protocol:

#### Sending Commands
```
TYPE DELIMITER VALUE\n
```
- **TYPE**: Single character command identifier (e.g., "F", "S")
- **DELIMITER**: Separator character (default: space)
- **VALUE**: Numeric value as a float
- **Example**: `F 0.25\n` sends a force command with value 0.25

#### Receiving Sensor Data
```
POSITION,VELOCITY\n
```
- Two comma-separated floating-point values
- Example: `0.1234,0.5678\n`

#### Receiving Debug Messages
```
DBG:MESSAGE\n
```
- Device-originated debug information
- Extracted and stored in `last_debug_message` property
- Can be displayed by the caller

### Connection Flow

```
1. SerialCommunication() instantiated (no connection yet)
2. connect() called
   ├─ Opens serial port
   ├─ Waits for Arduino reset (2 seconds)
   ├─ Sends "HELLO\n" handshake
   ├─ Waits for "READY" response
   └─ Returns True/False based on success
3. Connection ready for communication
4. close() called to disconnect
```

---

## Class Reference

### Constructor

```python
def __init__(self,
             port: str,
             baudrate: int = 115200,
             timeout: float = 0.001,
             delimiter: str = ' ')
```

**Parameters:**
- **port** (str): Serial port name
  - Windows: `"COM5"`, `"COM6"`, etc.
  - Linux: `"/dev/ttyACM0"`, `"/dev/ttyUSB0"`, etc.
  - macOS: `"/dev/cu.usbmodem*"`
- **baudrate** (int): Communication speed in bits per second
  - Default: 115200 (matches Arduino firmware)
  - Must match firmware setting
- **timeout** (float): Serial read timeout in seconds
  - Default: 0.001 (1 millisecond)
  - Non-blocking reads return immediately if no data
  - Typical range: 0.001 to 0.1
- **delimiter** (str): Command separator character
  - Default: space `' '`
  - Firmware must expect the same delimiter

**Properties Initialized:**
- `connected`: False (no connection on creation)
- `position`: 0.0 (last received position)
- `velocity`: 0.0 (last received velocity)
- `last_debug_message`: "" (latest debug message)
- `bytes_sent`: 0 (diagnostic counter)
- `bytes_received`: 0 (diagnostic counter)
- `packet_count`: 0 (count of position/velocity packets)

---

### Connection Management

#### `connect(handshake_timeout: float = 2.0) -> bool`

Establish connection with the Arduino device.

**Parameters:**
- **handshake_timeout**: Maximum seconds to wait for "READY" response
  - Default: 2.0 seconds
  - Increase if Arduino takes longer to reset

**Returns:**
- `True` if connection successful and handshake completed
- `False` if port error or handshake timeout

**What It Does:**
1. Opens the serial port
2. Waits 2 seconds for Arduino reset/reboot
3. Clears buffer of stray data
4. Sends "HELLO" handshake
5. Waits for "READY" response
6. Sets `connected` property

**Example:**
```python
comm = SerialCommunication(port="COM5")
if comm.connect(handshake_timeout=5.0):
    print("Connected!")
else:
    print("Connection failed")
```

#### `close() -> None`

Close the serial connection and clean up.

**What It Does:**
1. Closes the serial port if open
2. Sets `connected = False`
3. Safe to call even if not connected

**Example:**
```python
if comm.is_connected():
    comm.close()
```

#### `is_connected() -> bool`

Check if currently connected to device.

**Returns:**
- `True` if connected and ready
- `False` if disconnected

---

### Command Sending

#### `send_command(cmd_type: str, value: float) -> None`

Send a command to the Arduino device.

**Parameters:**
- **cmd_type** (str): Command type identifier (e.g., "F", "S", "P")
- **value** (float): Numeric command value

**Behavior:**
- Do nothing if not connected (safe to call)
- Formats as `TYPE DELIMITER VALUE\n`
- Encodes to UTF-8 and writes to serial port
- Updates `bytes_sent` counter

**Exceptions:**
- None raised (fails silently if not connected)

**Example:**
```python
# Send force command with value 0.25
comm.send_command("F", 0.25)

# Send streaming enable command
comm.send_command("S", 1.0)

# Send streaming disable command
comm.send_command("S", 0.0)
```

---

### Data Reception & Updates

#### `update() -> None`

Read and process one incoming message from the device.

**What It Does:**
1. Checks if connected (returns silently if not)
2. Attempts to read one line from serial port
3. Decodes UTF-8 and strips whitespace
4. Routes to appropriate handler:
   - **Debug messages** (start with "DBG:"): Extracts and stores in `last_debug_message`
   - **Sensor data** (contains ","): Parses position and velocity, increments `packet_count`
   - **Invalid data**: Silently ignored

**State Updates:**
- `position`: Updated to latest received position
- `velocity`: Updated to latest received velocity
- `last_debug_message`: Cleared and set to new message (if DBG received)
- `last_update_time`: Updated to current time (sensor data only)
- `packet_count`: Incremented (sensor data only)
- `bytes_received`: Updated with line length

**Important Notes:**
- **Non-blocking**: Returns immediately if no data available
- **Single message**: Processes one message per call
- **Robust**: Silently handles malformed UTF-8 and parsing errors
- **No printing**: Does not print debug messages (caller's responsibility)

**Typical Usage Pattern:**
```python
# Call repeatedly in a loop or background thread
while running:
    comm.update()
    
    # Check for new debug message
    if comm.last_debug_message:
        print(f"Debug: {comm.last_debug_message}")
        comm.last_debug_message = ""  # Clear it
    
    # Use current state
    pos, vel = comm.get_state()
    print(f"Position: {pos}, Velocity: {vel}")
    
    time.sleep(0.01)  # 100 Hz update rate
```

---

### State Access

#### `get_state() -> tuple`

Get the latest position and velocity readings.

**Returns:**
- Tuple: `(position: float, velocity: float)`
- Values are in units defined by firmware (typically meters and m/s)

**Example:**
```python
position, velocity = comm.get_state()
print(f"Pos: {position:.4f} m, Vel: {velocity:.4f} m/s")
```

#### `get_stats() -> dict`

Get communication statistics.

**Returns:**
- Dictionary with keys:
  - `"bytes_sent"`: Total bytes transmitted to device
  - `"bytes_received"`: Total bytes received from device
  - `"packets_received"`: Count of successful position/velocity packets

**Example:**
```python
stats = comm.get_stats()
print(f"Sent: {stats['bytes_sent']} bytes")
print(f"Received: {stats['bytes_received']} bytes")
print(f"Packets: {stats['packets_received']}")
```

---

## Usage Patterns

### Basic Usage

```python
from serial_communication import SerialCommunication

# Create instance (no connection yet)
comm = SerialCommunication(port="COM5", baudrate=115200)

# Connect
if not comm.connect(handshake_timeout=5.0):
    print("Failed to connect")
    exit(1)

# Send commands
comm.send_command("F", 0.5)  # Send force

# Receive data
comm.update()
pos, vel = comm.get_state()
print(f"Position: {pos}, Velocity: {vel}")

# Check for debug messages
if comm.last_debug_message:
    print(f"Arduino says: {comm.last_debug_message}")
    comm.last_debug_message = ""

# Disconnect
comm.close()
```

### Background Thread Pattern

```python
import threading
import time

comm = SerialCommunication(port="COM5")
comm.connect()

running = True

def receive_thread():
    while running:
        comm.update()
        
        # Check for debug messages
        if comm.last_debug_message:
            print(f"[DEBUG] {comm.last_debug_message}")
            comm.last_debug_message = ""
        
        time.sleep(0.01)  # 100 Hz update rate

# Start background thread
thread = threading.Thread(target=receive_thread, daemon=True)
thread.start()

# Main thread can send commands
comm.send_command("S", 1.0)  # Enable streaming
time.sleep(1)

# Check state from main thread
pos, vel = comm.get_state()
print(f"Current position: {pos}")

running = False
thread.join()
comm.close()
```

---

## Error Handling

### Connection Errors

The module handles these gracefully:

| Error | Handling |
|-------|----------|
| Invalid port | Caught, printed to console, returns `False` |
| Port already open | Serial exception caught, returns `False` |
| Handshake timeout | Connection closed, returns `False` |
| Read errors | Invalid data silently ignored |
| UTF-8 decode errors | Line skipped, continues polling |

### Silent Failures

These conditions fail silently (by design):

- Calling `send_command()` when disconnected
- Receiving malformed sensor data
- Receiving invalid UTF-8
- Receiving unknown message format

---

## Firmware Compatibility

This module expects the Arduino firmware to:

1. **Handshake Protocol**:
   - Wait for "HELLO" on startup
   - Respond with "READY" when ready

2. **Command Parsing**:
   - Accept commands as `TYPE DELIMITER VALUE`
   - Default delimiter is space

3. **Data Transmission**:
   - Send position/velocity as `POSITION,VELOCITY`
   - Send debug messages as `DBG:MESSAGE`
   - All messages terminated with `\n`

4. **Timing**:
   - Allow 2+ seconds for reset after serial port open
   - Respond to handshake within handshake_timeout

---

## Performance Considerations

### Update Rate
- `update()` is non-blocking (uses timeouts, not blocking reads)
- Can be called frequently without hanging
- Recommended rate: 100-1000 Hz depending on I/O

### Memory
- Minimal per-packet overhead
- Strings decoded and discarded after processing
- No circular buffers or queue
- Static memory usage regardless of data flow

### Thread Safety
- **Not thread-safe**
- Design assumes single reader/writer
- If using background thread + main thread, caller must synchronize access to `position`/`velocity`

---

## Troubleshooting

### Cannot Connect
```
Connection error: SerialException...
```
- Check port name (COM5, COM6, etc. on Windows)
- Ensure Arduino is plugged in
- Check if another program has the port open
- Try different handshake_timeout value

### No Data Received
- Verify streaming is enabled in firmware
- Check baud rate matches (default 115200)
- Verify `update()` is being called in a loop
- Check `packet_count` increasing with `get_stats()`

### Debug Messages Not Appearing
- Messages are stored in `last_debug_message`
- Caller must check and print them
- Module does not auto-print debug messages

### Garbled Data
- Check baud rate (must match firmware)
- Verify serial cable is good quality
- Reduce USB cable length if possible

---

## API Summary

| Method | Purpose | Returns |
|--------|---------|---------|
| `connect()` | Establish connection | bool |
| `close()` | Disconnect | None |
| `send_command()` | Send command to device | None |
| `update()` | Receive and process one message | None |
| `get_state()` | Get position/velocity | tuple |
| `get_stats()` | Get diagnostics | dict |
| `is_connected()` | Check connection status | bool |
