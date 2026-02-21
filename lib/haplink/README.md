# Haplink - Serial Communication Protocol Library

A lightweight, packet-based serial communication library for Arduino that enables bidirectional data exchange between an Arduino microcontroller and a host device (PC, Raspberry Pi, etc.). Haplink provides a robust protocol for reading/writing parameters and streaming telemetry data.

## Overview

Haplink simplifies serial communication by abstracting the complexity of packet handling, data serialization, and connection state management. It uses a fixed-packet format with checksums for error detection and supports up to 32 parameters and 32 telemetry variables.

## Features

- **Parameter Management**: Register variables as parameters that can be read or written via serial commands
- **Telemetry Streaming**: Stream variable data to a host device in real-time
- **Packet-Based Protocol**: Structured binary packets with error checking via XOR checksums
- **Type Support**: Handle multiple data types (uint8, int16, int32, float, double)
- **Connection Monitoring**: Track connection state with configurable timeout
- **Thread-Safe Operations**: Interrupt-safe reads/writes using `noInterrupts()` / `interrupts()`
- **Flexible Serial Interface**: Works with any Stream-based serial port (Serial, Serial1, SoftwareSerial, etc.)

## Architecture

### Packet Structure

All packets are fixed 13 bytes:

```
[Header(1)] [PacketType(1)] [ID(1)] [DataType(1)] [Data(8)] [Checksum(1)]
```

- **Header**: Start byte (0xAA) to mark packet beginning
- **PacketType**: Specifies what kind of packet (parameter write, parameter read, telemetry, or heartbeat)
- **ID**: Identifies which parameter or telemetry variable (0-255)
- **DataType**: Specifies how to interpret the data field (uint8, int16, int32, float, double)
- **Data**: 8-byte payload (sized according to DataType)
- **Checksum**: XOR checksum for error detection

### Packet Types

| Type | Value | Direction | Description |
|------|-------|-----------|-------------|
| `HL_PACKET_PARAM_WRITE` | 0xA1 | Host → Device | Set a parameter value |
| `HL_PACKET_PARAM_READ` | 0xA2 | Host → Device | Request parameter value (not yet implemented) |
| `HL_PACKET_TELEMETRY` | 0xB1 | Device → Host | Send telemetry data to host |
| `HL_PACKET_HEARTBEAT` | 0xC1 | Either | Keep-alive packet |

## Data Types

```cpp
enum HL_DataType : uint8_t {
    HL_UINT8  = 1,  // 1 byte (0-255)
    HL_INT16  = 2,  // 2 bytes (-32768 to 32767)
    HL_INT32  = 3,  // 4 bytes
    HL_FLOAT  = 4,  // 4 bytes (32-bit floating point)
    HL_DOUBLE = 5   // ON AVR ARDUINO: ONLY 4 BYTES! (same as FLOAT)
};
```

### CRITICAL: Arduino Double is 4 Bytes

On AVR-based Arduino boards (Uno, Mega, Nano), **`double` is only 4 bytes** - it's identical to `float`. This is different from desktop platforms where `double` is 8 bytes.

**Always use `HL_FLOAT` for Arduino double variables:**

```cpp
// WRONG - Will send 4-byte data but marked as 8-byte
double my_value = 0.0;
haplink.registerTelemetry(1, &my_value, HL_DOUBLE);

// CORRECT - 4-byte float registered as 4-byte
double my_value = 0.0;
haplink.registerTelemetry(1, &my_value, HL_FLOAT);
```

**Both Arduino and Python must agree on the type:**
- Arduino: `HL_FLOAT` (4 bytes)
- Python: `DataType.FLOAT` (4 bytes)

## Usage

### Basic Setup

```cpp
#include <haplink.h>

Haplink haplink;

void setup() {
  Serial.begin(115200);
  
  // Initialize Haplink (1000ms connection timeout)
  haplink.begin(Serial, 1000);
}

void loop() {
  // Process incoming serial data
  haplink.update();
}
```

### Registering Parameters

Register variables that can be controlled from the host device:

```cpp
float motor_speed = 0.0;
int16_t position = 0;

void setup() {
  Serial.begin(115200);
  haplink.begin(Serial);
  
  // Register parameters (ID, address, data type)
  // Remember: Arduino double is only 4 bytes - use HL_FLOAT!
  haplink.registerParam(1, &motor_speed, HL_FLOAT);  // 4-byte float
  haplink.registerParam(2, &position, HL_INT16);     // 2-byte int
}

void loop() {
  haplink.update();
  
  // motor_speed and position can now be modified via serial commands
  Serial.print("Motor speed: ");
  Serial.println(motor_speed);
}
```

### Registering Telemetry

Register variables to stream their values to the host device:

```cpp
float sensor_reading = 0.0;    // Note: double is 4 bytes on Arduino
uint8_t system_status = 0;

void setup() {
  Serial.begin(115200);
  haplink.begin(Serial);
  
  // Register telemetry (ID, address, data type)
  // Remember: Arduino double is only 4 bytes - use HL_FLOAT!
  haplink.registerTelemetry(1, &sensor_reading, HL_FLOAT);   // 4-byte float
  haplink.registerTelemetry(2, &system_status, HL_UINT8);    // 1-byte uint
}

void loop() {
  haplink.update();
  
  // Update sensor data
  sensor_reading = analogRead(A0) / 1024.0 * 5.0;
  
  // Send individual telemetry
  haplink.sendTelemetry(1);
  
  // Or send all telemetry at once
  haplink.sendAllTelemetry();
  
  delay(100);
}
```

### Checking Connection Status

```cpp
void loop() {
  haplink.update();
  
  if (haplink.connectionAlive()) {
    // Host is actively communicating
    digitalWrite(LED_PIN, HIGH);
  } else {
    // Connection timed out
    digitalWrite(LED_PIN, LOW);
  }
}
```

## API Reference

### Constructor
```cpp
Haplink();
```
Creates a new Haplink instance.

### `begin(Stream &serialPort, uint32_t connectionTimeoutMs = 1000)`
Initialize Haplink with a serial port and optional timeout.
- **Parameters**:
  - `serialPort`: Serial stream to use (Serial, Serial1, SoftwareSerial, etc.)
  - `connectionTimeoutMs`: Considers connection dead if no packets received for this duration (default: 1000ms)
- **Returns**: void

### `registerParam(uint8_t id, void* address, HL_DataType type)`
Register a variable as a parameter (readable/writable from host).
- **Parameters**:
  - `id`: Unique identifier for this parameter (0-255)
  - `address`: Pointer to the variable in memory
  - `type`: Data type of the variable
- **Returns**: `true` if successful, `false` if parameter registry is full (max 32)

### `registerTelemetry(uint8_t id, void* address, HL_DataType type)`
Register a variable for telemetry streaming.
- **Parameters**:
  - `id`: Unique identifier for this telemetry variable (0-255)
  - `address`: Pointer to the variable in memory
  - `type`: Data type of the variable
- **Returns**: `true` if successful, `false` if telemetry registry is full (max 32)

### `update()`
Process incoming serial data. Call this frequently in your main loop.
- **Parameters**: none
- **Returns**: void

### `sendTelemetry(uint8_t id)`
Send a single telemetry variable to the host.
- **Parameters**: `id` of the telemetry variable to send
- **Returns**: `true` if sent successfully, `false` if ID not found

### `sendAllTelemetry()`
Send all registered telemetry variables to the host.
- **Parameters**: none
- **Returns**: void

### `connectionAlive()`
Check if the host connection is still active.
- **Parameters**: none
- **Returns**: `true` if last packet received within timeout window, `false` otherwise

## Limitations & Constraints

- **Max Parameters**: 32 (dictated by 8-bit ID field)
- **Max Telemetry**: 32 (dictated by 8-bit ID field)
- **Data Size**: Maximum 8 bytes per packet (largest supported type is double)
- **Arduino Double Size**: On AVR boards, `double` is only 4 bytes (same as `float`). Always register double variables as `HL_FLOAT`.
- **Unimplemented Features**: 
  - Parameter read requests (HL_PACKET_PARAM_READ) - not yet implemented
  - Heartbeat handling - defined but not actively used
- **Thread Safety**: Parameter writes and telemetry reads use interrupt disabling, safe for simple interrupt scenarios

## Implementation Notes

### Checksum Algorithm
Uses XOR checksum across packet type, ID, data type, and all data bytes:
```cpp
sum ^= packetType ^ id ^ dataType;
for (each byte in data)
    sum ^= byte;
return sum;
```

### Safe Memory Operations
All parameter writes and telemetry reads use `safeWrite()` and `safeRead()` which disable interrupts during memory copy to prevent inconsistent state:

```cpp
void safeWrite(void* dest, const uint8_t* src, uint8_t size) {
  noInterrupts();
  memcpy(dest, src, size);
  interrupts();
}
```

This is critical for multi-byte types that might be accessed by interrupt handlers.

## Debugging

### Transmitting All Zeros

**Symptom**: Host receives packets with all zero data bytes, but variables have actual values.

**Cause**: Mismatch between registered data type and actual variable size.

**Solution**: 
1. Verify `HL_FLOAT` is used for all Arduino `double` variables (not `HL_DOUBLE`)
2. Check data type matches variable size:
   ```cpp
   double value = 1.5;        // 4 bytes on Arduino
   haplink.registerTelemetry(1, &value, HL_FLOAT);  // ✓ Correct
   haplink.registerTelemetry(1, &value, HL_DOUBLE); // ✗ Wrong - expects 8 bytes
   ```

### Verifying Packets Are Sent

Use a raw serial monitor to inspect packet structure:

```
Expected packet format:
[AA] [B1] [ID] [04] [data...] [checksum]
  ↑    ↑    ↑    ↑
  |    |    |    +-- Data type code (04 = FLOAT)
  |    |    +-------- Telemetry ID
  |    +------------- Packet type (B1 = TELEMETRY)
  +------------------ Header (AA)
```

If data bytes are all 00, check the data type registration.

### Connection Timeout

If `connectionAlive()` returns false:
1. Verify host is calling `haplink.update()` regularly
2. Check serial connection (baud rate, cable)
3. Increase timeout if needed:
   ```cpp
   haplink.begin(Serial, 5000);  // 5 second timeout
   ```

## Example Application

```cpp
#include <haplink.h>

Haplink haplink;

// Variables
float setpoint = 0.0;      // Parameter: settable from host
int16_t error = 0;         // Parameter: settable from host
float output = 0.0;        // Telemetry: streamed to host
float sensor = 0.0;        // Telemetry: streamed to host

void setup() {
  Serial.begin(115200);
  haplink.begin(Serial, 2000);  // 2 second timeout
  
  // Register parameters (host can write these)
  haplink.registerParam(1, &setpoint, HL_FLOAT);
  haplink.registerParam(2, &error, HL_INT16);
  
  // Register telemetry (host can read these)
  haplink.registerTelemetry(1, &output, HL_FLOAT);
  haplink.registerTelemetry(2, &sensor, HL_FLOAT);
}

void loop() {
  haplink.update();
  
  // Read sensor
  sensor = analogRead(A0) / 1024.0 * 5.0;
  
  // Simple control loop
  error = (setpoint - sensor) * 100;
  output = constrain(error * 0.1, -255, 255);
  
  // Send telemetry at 10Hz
  static unsigned long lastSend = 0;
  if (millis() - lastSend > 100) {
    haplink.sendAllTelemetry();
    lastSend = millis();
  }
  
  // Set PWM based on output
  analogWrite(9, abs(output));
}
```

## See Also

- [Serial Communication Documentation](../serial_communication/serial_communication.md)
- PlatformIO Documentation
- Arduino Stream Class Reference
