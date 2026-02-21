
# Haplink Python Module - Documentation and Examples

A professional Python library for communicating with Hapkit Arduino devices
running the Haplink firmware.

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Core Concepts](#core-concepts)
4. [API Reference](#api-reference)
5. [Examples](#examples)
6. [Best Practices](#best-practices)

---

## Installation

### Requirements
- Python 3.7+
- `pyserial` package

### Setup
```bash
# Install dependencies
pip install pyserial

# The haplink module is included in the python/ directory
```

---

## Quick Start

### Basic Connection and Communication

```python
from haplink import Haplink, DataType

# Create client
haplink = Haplink('/dev/ttyUSB0', baudrate=115200)

# Connect to device
if not haplink.connect():
    print("Failed to connect to device")
    exit(1)

# Register a parameter (device must have same ID registered)
haplink.register_param(1, 'motor_speed', DataType.FLOAT)

# Register telemetry to receive
haplink.register_telemetry(1, 'position', DataType.FLOAT)

# Set parameter
haplink.set_param('motor_speed', 0.75)

# Read telemetry
haplink.update()  # Receive new data from device
position = haplink.get_telemetry('position')
print(f"Position: {position}")

# Cleanup
haplink.disconnect()
```

### Continuous Monitoring Loop

```python
import time
from haplink import Haplink, DataType

haplink = Haplink('COM5')
if not haplink.connect():
    exit(1)

haplink.register_telemetry(1, 'sensor', DataType.FLOAT)
haplink.register_telemetry(2, 'status', DataType.UINT8)

# Main loop
try:
    while True:
        haplink.update()
        
        sensor = haplink.get_telemetry('sensor')
        status = haplink.get_telemetry('status')
        
        print(f"Sensor: {sensor:.2f}, Status: {status}")
        
        time.sleep(0.05)  # 20 Hz update rate
except KeyboardInterrupt:
    print("Exiting...")
finally:
    haplink.disconnect()
```

---

## Core Concepts

### Parameters vs Telemetry

**Parameters** are device variables that the host can write/modify:
- Used for device configuration, setpoints, mode selection
- Write-only from the host perspective
- Registered with `register_param()`

**Telemetry** are device variables that stream to the host:
- Sensor readings, state data, diagnostics
- Read-only from the host perspective
- Registered with `register_telemetry()`

### Data Types

Haplink supports 5 data types:

```python
DataType.UINT8    # 0-255 (1 byte)
DataType.INT16    # -32768 to 32767 (2 bytes)
DataType.INT32    # Large signed integers (4 bytes)
DataType.FLOAT    # 32-bit floating point (4 bytes)
DataType.DOUBLE   # 64-bit floating point (8 bytes)
```

### ⚠️  CRITICAL: Arduino Double is 4 Bytes

On AVR-based Arduino boards (Uno, Mega, Nano), **`double` is only 4 bytes** - identical to `float`. This differs from desktop platforms where `double` is 8 bytes.

**Arduino code must use `HL_FLOAT` for double variables:**

```cpp
// Arduino side
double xh = 0.0;  // Only 4 bytes on AVR
haplink.registerTelemetry(1, &xh, HL_FLOAT);  // ✓ Correct: 4 bytes
haplink.registerTelemetry(1, &xh, HL_DOUBLE); // ✗ Wrong: expects 8 bytes
```

**Python and Arduino must match:**

```python
# Python side - MUST match Arduino registration!
haplink.register_telemetry(1, 'xh', DataType.FLOAT)   # ✓ Correct: matches HL_FLOAT
haplink.register_telemetry(1, 'xh', DataType.DOUBLE)  # ✗ Wrong: mismatched
```

**If you register as DOUBLE on Python but HL_FLOAT on Arduino, you'll receive all zeros.**

### IDs

Each parameter and telemetry variable must have a unique ID (0-255).
**IDs must match between the Arduino sketch and Python code.**

Example Arduino sketch:
```cpp
haplink.begin(Serial);
haplink.registerParam(1, &motor_speed, HL_FLOAT);
haplink.registerTelemetry(1, &sensor_reading, HL_FLOAT);
```

Matching Python code:
```python
haplink.register_param(1, 'motor_speed', DataType.FLOAT)
haplink.register_telemetry(1, 'sensor_reading', DataType.FLOAT)
```

---

## API Reference

### Haplink Class

#### Constructor
```python
Haplink(port, baudrate=115200, timeout=1.0, connection_timeout=2.0)
```
- `port`: Serial port name ('COM5', '/dev/ttyUSB0', etc.)
- `baudrate`: Communication speed (default 115200)
- `timeout`: Read timeout in seconds for individual packets
- `connection_timeout`: Max time to wait for device response during connect

#### Connection Methods

##### `connect() -> bool`
Connect to the device. Opens serial port and waits for a response.
Returns `True` if device detected, `False` if timeout.

```python
if haplink.connect():
    print("Connected!")
else:
    print("Device not responding")
```

##### `disconnect() -> None`
Close the serial connection.

##### `is_connected() -> bool`
Check if currently connected.

#### Registration Methods

##### `register_param(param_id, name, data_type) -> None`
Register a parameter to write to the device.

```python
haplink.register_param(1, 'setpoint', DataType.FLOAT)
haplink.register_param(2, 'mode', DataType.UINT8)
```

Raises `ValueError` if ID already registered or invalid.

##### `register_telemetry(tel_id, name, data_type) -> None`
Register a telemetry variable to receive from the device.

```python
haplink.register_telemetry(1, 'position', DataType.FLOAT)
haplink.register_telemetry(2, 'error', DataType.INT16)
```

Raises `ValueError` if ID already registered or invalid.

#### Communication Methods

##### `set_param(param_name, value) -> None`
Write a parameter value to the device.

```python
haplink.set_param('setpoint', 45.5)
haplink.set_param('mode', 2)
```

Raises `ValueError` if parameter not registered or `HaplinkError` if not connected.

##### `get_telemetry(tel_name) -> any`
Get the last received value for a telemetry variable.

```python
position = haplink.get_telemetry('position')
error = haplink.get_telemetry('error')
```

Returns `None` if no data has been received yet.
Raises `ValueError` if telemetry not registered.

##### `update(debug=False) -> int`
Process incoming packets from the device. Call this regularly to receive new telemetry data.

**Parameters:**
- `debug` (bool, optional): Enable debug output to console. Shows received packet details. Default: False.

**Returns:**
- Number of packets successfully processed

```python
while True:
    # Normal operation
    packets = haplink.update()
    
    # Debug mode: prints packet details
    packets = haplink.update(debug=True)
    
    # Example debug output:
    # [DEBUG] Packet received: type=TELEMETRY, id=0
    # [DEBUG] ID 0: hex=46A7B43E, decoded=0.353
    # [DEBUG] update() processed 2 packets, 0 errors
    
    data = haplink.get_telemetry('sensor')
```

#### Status Methods

##### `get_param_value(param_name) -> any`
Get the last written parameter value (cached locally, not from device).

##### `list_params() -> dict`
Get information about all registered parameters.

```python
{
    'motor_speed': {
        'id': 1,
        'type': 'FLOAT',
        'value': 0.75
    }
}
```

##### `list_telemetry() -> dict`
Get information about all registered telemetry variables with their latest values.

```python
{
    'position': {
        'id': 1,
        'type': 'FLOAT',
        'value': 123.45,
        'last_update': 1645123456.789
    }
}
```

---

## Examples

### Example 1: Motor Speed Control

Control a motor and monitor its speed:

```python
from haplink import Haplink, DataType
import time

haplink = Haplink('COM5')
haplink.connect()

# Register device variables
haplink.register_param(1, 'speed_setpoint', DataType.FLOAT)
haplink.register_telemetry(1, 'actual_speed', DataType.FLOAT)

# Ramp up speed
for speed in [0.1, 0.3, 0.5, 0.7, 1.0]:
    haplink.set_param('speed_setpoint', speed)
    time.sleep(0.5)
    
    for _ in range(10):
        haplink.update()
        actual = haplink.get_telemetry('actual_speed')
        print(f"Target: {speed:.1f}, Actual: {actual:.2f}")
        time.sleep(0.05)

haplink.disconnect()
```

### Example 2: Data Logging

Log telemetry to a file:

```python
from haplink import Haplink, DataType
import time
import csv

haplink = Haplink('COM5')
haplink.connect()

haplink.register_telemetry(1, 'temperature', DataType.FLOAT)
haplink.register_telemetry(2, 'pressure', DataType.FLOAT)

with open('log.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['time', 'temperature', 'pressure'])
    
    start_time = time.time()
    while time.time() - start_time < 60:  # Log for 60 seconds
        haplink.update()
        
        t = time.time() - start_time
        temp = haplink.get_telemetry('temperature')
        press = haplink.get_telemetry('pressure')
        
        writer.writerow([t, temp, press])
        time.sleep(0.1)

haplink.disconnect()
```

### Example 3: Error Handling

Robust error handling and recovery:

```python
from haplink import Haplink, DataType, HaplinkError
import time

def connect_with_retry(port, max_retries=3):
    """Connect with automatic retry."""
    for attempt in range(max_retries):
        haplink = Haplink(port, connection_timeout=5.0)
        try:
            if haplink.connect():
                print(f"Connected on attempt {attempt + 1}")
                return haplink
        except HaplinkError as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            haplink.disconnect()
        time.sleep(1)
    raise RuntimeError("Failed to connect after retries")

try:
    haplink = connect_with_retry('COM5')
    haplink.register_telemetry(1, 'data', DataType.FLOAT)
    
    while True:
        try:
            haplink.update()
            value = haplink.get_telemetry('data')
            print(f"Data: {value}")
        except HaplinkError as e:
            print(f"Communication error: {e}")
            if not haplink.is_connected():
                print("Connection lost, reconnecting...")
                haplink = connect_with_retry('COM5')
        
        time.sleep(0.05)
        
except KeyboardInterrupt:
    print("Shutting down...")
finally:
    haplink.disconnect()
```

---

## Best Practices

### 1. Match Data Types Between Arduino and Python

This is the #1 source of issues. Create a shared constants file:

**Arduino (constants.h):**
```cpp
#define PARAM_SPEED 1
#define TEL_POSITION 1
#define TEL_POSITION_TYPE HL_FLOAT  // ⚠️  double is 4 bytes on AVR!
```

**Python (constants.py):**
```python
PARAM_SPEED = 1
TEL_POSITION = 1
TEL_POSITION_TYPE = DataType.FLOAT  # Must match Arduino!
```

**Usage:**
```cpp
// Arduino
double xh = 0.0;  // Only 4 bytes
haplink.registerTelemetry(TEL_POSITION, &xh, TEL_POSITION_TYPE);
```

```python
# Python
haplink.register_telemetry(TEL_POSITION, 'position', TEL_POSITION_TYPE)
```

### 2. Always Disconnect

Use try/finally to ensure cleanup:

```python
haplink = Haplink('COM5')
try:
    haplink.connect()
    # ... do work
finally:
    haplink.disconnect()
```

Or use context manager pattern (if implemented):

```python
with Haplink('COM5') as haplink:
    # ... work with haplink
    # Automatically disconnects
```

### 3. Call update() Regularly

Telemetry data arrives asynchronously. Call `update()` frequently to keep data fresh:

```python
while True:
    haplink.update()  # Must call this to receive new data
    data = haplink.get_telemetry('sensor')
    # process
    time.sleep(0.01)  # 100 Hz update loop
```

### 4. Use Debug Mode to Verify Communication

When data isn't arriving, use debug mode to diagnose:

```python
# First few calls with debug
for i in range(5):
    packets = haplink.update(debug=True)
    print(f"Received {packets} packets")
    time.sleep(0.1)

# Output tells you:
# - Packet type (TELEMETRY)
# - Packet ID (which variable)
# - Data type code (04=FLOAT, 05=DOUBLE)
# - Raw hex bytes and decoded value
```

### 5. Handle None Values

Telemetry might not have data initially:

```python
position = haplink.get_telemetry('position')
if position is not None:
    print(f"Position: {position}")
else:
    print("No data received yet")
```

### 6. Choose Appropriate Update Rates

Balance responsiveness with CPU usage:

```python
# Fast control loop (1000 Hz)
for i in range(1000):
    haplink.update()
    haplink.set_param('control_input', compute_control())
    time.sleep(0.001)

# Slow monitoring (10 Hz)
while True:
    haplink.update()
    log_data()
    time.sleep(0.1)
```

### 7. Verify Serial Configuration

Ensure Arduino and Python match:

```python
# Arduino side
Serial.begin(115200);
haplink.begin(Serial);

# Python side
haplink = Haplink('COM5', baudrate=115200)
haplink.connect()
```

**Both MUST be 115200 baud by default.**

---

## Limitations & Constraints

- **Max Parameters**: 32 per device (enforced by Arduino firmware)
- **Max Telemetry**: 32 per device (enforced by Arduino firmware)
- **Data Size**: Maximum 8 bytes per packet payload (largest supported type is double)
- **⚠️  Arduino Double Size**: Arduino `double` is only 4 bytes on AVR boards. Always register as `DataType.FLOAT` to match `HL_FLOAT` on Arduino side.
- **Unimplemented Features**: 
  - Parameter read requests (HL_PACKET_PARAM_READ) - device firmware doesn't implement this yet
  - Heartbeat packets (HL_PACKET_HEARTBEAT) - not actively used
- **Read-Only Telemetry**: Python client only receives telemetry FROM device; sending telemetry TO device is not supported
- **IDs must match**: Parameter and telemetry IDs registered in Python MUST match those registered in Arduino sketch exactly, and data types must match exactly

---

## Troubleshooting

### Connection Issues

```python
# Check connection is open
print(f"Connected: {haplink.is_connected()}")

# Test with longer timeout
haplink = Haplink('COM5', connection_timeout=5.0)
if not haplink.connect():
    print("Device not responding")
    print("Check: Arduino is running Haplink firmware")
    print("Check: Correct serial port and baudrate")
```

### Receiving All Zeros (Critical: Data Type Mismatch)

**Symptom**: Data arrives in packets but always shows 0.0

**Cause**: Arduino and Python registered different data types
- Arduino: `HL_FLOAT` (4 bytes)
- Python: `DataType.DOUBLE` (expects 8 bytes)

**Solution**: Ensure they match exactly

```python
# ❌ WRONG - Mismatch will show zeros
# Arduino: haplink.registerTelemetry(1, &xh, HL_FLOAT);
haplink.register_telemetry(1, 'position', DataType.DOUBLE)

# ✓ CORRECT - Both sides use FLOAT
# Arduino: haplink.registerTelemetry(1, &xh, HL_FLOAT);
haplink.register_telemetry(1, 'position', DataType.FLOAT)
```

**Verification Steps:**
1. Use raw serial monitor to inspect packet hex:
   ```
   B1 00 04 46A7B43E  (ID=0, Type=04 FLOAT, Data=46A7B43E)
   ```
2. Check the DataType field (3rd data byte):
   - `04` = FLOAT ✓
   - `05` = DOUBLE ✗
3. Verify Python registration matches:
   ```python
   # If you see 04 in packets, use:
   haplink.register_telemetry(1, 'position', DataType.FLOAT)
   ```

### Missing Telemetry Data

```python
# Verify telemetry is registered
print(haplink.list_telemetry())

# Check for None values (no data received yet)
data = haplink.get_telemetry('sensor')
print(f"Data is None: {data is None}")

# Make sure to call update() regularly
haplink.update()

# Use debug mode to see if packets arriving
haplink.update(debug=True)  # Shows all received packets
```

### Protocol Errors (Checksum Failures)

```python
# Use debug mode to see validation errors
haplink.update(debug=True)

# Example output:
# [DEBUG] ProtocolError: Checksum mismatch: computed 0xA5, received 0xB2
```

**Possible causes:**
- Serial cable noise/corruption
- Baud rate mismatch (Arduino and host must match)
- EMI interference on serial line
- Arduino not running Haplink firmware

**Solutions:**
- Use shielded serial cable
- Move away from high-EMI devices
- Verify baudrate: Arduino = 115200, Python = 115200
- Check Arduino code is compiled with Haplink library

### Protocol Errors

The library handles most protocol errors internally and skips malformed packets. If you see exceptions:
- Verify Arduino is running Haplink firmware
- Check serial connection (loose cable, wrong port)
- Verify baudrate matches both sides (115200 recommended)
- Check for EMI/noise on serial line

---

## Reference

- [Haplink C++ Library Documentation](../lib/haplink/README.md)
- [Serial Communication Protocol](../serial_communication/serial_communication.md)
- [PySerial Documentation](https://pyserial.readthedocs.io/)
"""
