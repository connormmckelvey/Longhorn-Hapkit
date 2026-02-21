
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
DataType.UINT8    # 0-255
DataType.INT16    # -32768 to 32767
DataType.INT32    # Large signed integers
DataType.FLOAT    # 32-bit floating point
DataType.DOUBLE   # 64-bit floating point
```

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

##### `update() -> None`
Process incoming packets from the device. Call this regularly to receive new telemetry data.

```python
while True:
    haplink.update()
    data = haplink.get_telemetry('sensor')
    # process data
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

### 1. Always Disconnect

Use try/finally to ensure cleanup:

```python
haplink = Haplink('COM5')
try:
    haplink.connect()
    # ... do work
finally:
    haplink.disconnect()
```

Or use `with` statement (if implemented):

```python
with Haplink('COM5') as haplink:
    # ... work with haplink
    # Automatically disconnects
```

### 2. Call update() Regularly

Telemetry data arrives asynchronously. Call `update()` frequently to keep data fresh:

```python
while True:
    haplink.update()  # Must call this to receive new data
    data = haplink.get_telemetry('sensor')
    # process
    time.sleep(0.01)  # 100 Hz
```

### 3. Match IDs Between Arduino and Python

ID mismatches will prevent communication. Create a shared constants file:

**constants.h** (Arduino):
```cpp
#define PARAM_SPEED 1
#define TEL_POSITION 1
```

**constants.py** (Python):
```python
PARAM_SPEED = 1
TEL_POSITION = 1
```

### 4. Use Descriptive Names

Register with clear, descriptive names for easier debugging:

```python
# Good
haplink.register_param(1, 'motor_speed_setpoint', DataType.FLOAT)

# Less clear
haplink.register_param(1, 'sp', DataType.FLOAT)
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

---

## Limitations & Constraints

- **Max Parameters**: 32 per device (enforced by Arduino firmware)
- **Max Telemetry**: 32 per device (enforced by Arduino firmware)
- **Data Size**: Maximum 8 bytes per packet payload (largest supported type is double)
- **Unimplemented Features**: 
  - Parameter read requests (HL_PACKET_PARAM_READ) - device firmware doesn't implement this yet
  - Heartbeat packets (HL_PACKET_HEARTBEAT) - not actively used
- **Read-Only Telemetry**: Python client only receives telemetry FROM device; sending telemetry TO device is not supported
- **IDs must match**: Parameter and telemetry IDs registered in Python MUST match those registered in Arduino sketch exactly

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

### Missing Telemetry Data

```python
# Verify telemetry is registered
print(haplink.list_telemetry())

# Check for None values
data = haplink.get_telemetry('sensor')
print(f"Data is None: {data is None}")

# Make sure to call update()
haplink.update()
```

### Protocol Errors

The library handles most protocol errors internally. If you see exceptions:
- Verify Arduino is running Haplink firmware
- Check serial connection (loose cable, wrong port)
- Verify baudrate matches both sides
- Check for EMI/noise on serial line

---

## Reference

- [Haplink C++ Library Documentation](../lib/haplink/README.md)
- [Serial Communication Protocol](../serial_communication/serial_communication.md)
- [PySerial Documentation](https://pyserial.readthedocs.io/)
"""
