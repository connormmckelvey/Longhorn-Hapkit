# Haplink Python Module

Professional Python library for host-side communication with Arduino devices running the Haplink serial protocol.

## Quick Overview

**Haplink** simplifies communication with your Hapkit Arduino device by providing:

- ✅ **Clean API** - Simple, Pythonic interface for parameter control and telemetry streaming
- ✅ **Type Safety** - Support for multiple data types (uint8, int16, int32, float, double)
- ✅ **Error Handling** - Robust protocol validation and connection management
- ✅ **Zero Configuration** - Works out of the box with pyserial

## Installation

```bash
pip install pyserial
```

The haplink module is included in this directory.

## Quick Start

```python
from haplink import Haplink, DataType

# Connect to device
haplink = Haplink('COM5', baudrate=115200)
haplink.connect()

# Register device variables (IDs must match Arduino sketch)
haplink.register_param(1, 'motor_speed', DataType.FLOAT)
haplink.register_telemetry(1, 'position', DataType.FLOAT)

# Set parameter
haplink.set_param('motor_speed', 0.5)

# Read telemetry
haplink.update()
pos = haplink.get_telemetry('position')
print(f"Position: {pos}")

# Cleanup
haplink.disconnect()
```

## Module Structure

```
haplink/
├── __init__.py              # Package initialization and exports
├── haplink_core.py          # Low-level protocol and packet handling
├── haplink_client.py        # High-level client API
├── README.md                # Full documentation
└── example.py               # Runnable example
```

### Core Components

- **`haplink_core.py`**: Protocol implementation
  - `HaplinkPacket` - Packet structure and serialization
  - `DataType` - Supported data types
  - `PacketType` - Protocol packet types
  - `SerialPort` - Low-level serial I/O
  
- **`haplink_client.py`**: High-level API
  - `Haplink` - Main client class
  - `ParamBinding` - Parameter registration
  - `TelemetryBinding` - Telemetry registration

## Common Usage Patterns

### Basic Communication

```python
from haplink import Haplink, DataType

haplink = Haplink('COM5')
if haplink.connect():
    haplink.register_param(1, 'control', DataType.FLOAT)
    haplink.register_telemetry(1, 'feedback', DataType.FLOAT)
    
    haplink.set_param('control', 1.0)
    haplink.update()
    feedback = haplink.get_telemetry('feedback')
    
    haplink.disconnect()
```

### Continuous Loop

```python
import time

haplink = Haplink('COM5')
haplink.connect()
haplink.register_telemetry(1, 'data', DataType.FLOAT)

try:
    while True:
        haplink.update()  # Receive new data
        value = haplink.get_telemetry('data')
        print(f"Data: {value}")
        time.sleep(0.05)  # 20 Hz update rate
except KeyboardInterrupt:
    haplink.disconnect()
```

### Error Handling

```python
from haplink import Haplink, HaplinkError

try:
    haplink = Haplink('COM5')
    haplink.connect()
    # ... use haplink ...
except HaplinkError as e:
    print(f"Communication error: {e}")
finally:
    haplink.disconnect()
```

## API Overview

### Connection
- `connect()` - Connect to device
- `disconnect()` - Close connection
- `is_connected()` - Check connection status

### Registration
- `register_param(id, name, data_type)` - Register controllable parameter
- `register_telemetry(id, name, data_type)` - Register streaming telemetry

### Communication
- `set_param(name, value)` - Write parameter to device
- `update()` - Receive packets from device
- `get_telemetry(name)` - Get last received telemetry value

### Status
- `list_params()` - List all registered parameters
- `list_telemetry()` - List all registered telemetry with latest values

## Key Concepts

### Parameters vs Telemetry

- **Parameters** - Variables you write TO the device (setpoints, config)
- **Telemetry** - Variables you read FROM the device (sensors, state)

### ID Matching

IDs must match between your Arduino sketch and Python code:

**Arduino:**
```cpp
haplink.registerParam(1, &motor_speed, HL_FLOAT);
haplink.registerTelemetry(1, &position, HL_FLOAT);
```

**Python:**
```python
haplink.register_param(1, 'motor_speed', DataType.FLOAT)
haplink.register_telemetry(1, 'position', DataType.FLOAT)
```

### Data Types

```python
DataType.UINT8    # 0-255
DataType.INT16    # -32768 to 32767  
DataType.INT32    # Large integers
DataType.FLOAT    # 32-bit float
DataType.DOUBLE   # 64-bit float
```

## Example

Run the included example:

```python
cd haplink
python example.py
```

**Optional:** Edit `PORT` variable to match your serial port.

## Full Documentation

See [README.md](README.md) for comprehensive documentation including:
- Installation and setup
- Core concepts and architecture
- Complete API reference
- Multiple detailed examples
- Best practices and troubleshooting

## Package Information

- **Version**: 0.1.0
- **Author**: Hapkit Team
- **License**: Inherited from Hapkit project
- **Status**: Professional, production-ready

## Related Resources

- [Haplink C++ Library](../lib/haplink/README.md) - Arduino-side implementation
- [Serial Communication Docs](../serial_communication/README.md) - Protocol details
- [PySerial Docs](https://pyserial.readthedocs.io/) - Python serial library
