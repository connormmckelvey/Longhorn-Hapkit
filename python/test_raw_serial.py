"""
Raw serial test - just read bytes to verify Arduino is sending data
"""

import serial
import time

port = 'COM5'
baudrate = 115200

print(f"Opening {port} at {baudrate} baud...")
ser = serial.Serial(port, baudrate, timeout=0.1)
time.sleep(2)  # Wait for Arduino reset
ser.reset_input_buffer()

print("Reading raw bytes for 3 seconds...")
print("Looking for header byte 0xAA (170 decimal)")
print("-" * 60)

start_time = time.time()
bytes_received = 0
header_count = 0
last_20_bytes = []

while time.time() - start_time < 3.0:
    if ser.in_waiting > 0:
        data = ser.read(ser.in_waiting)
        bytes_received += len(data)
        
        for byte in data:
            last_20_bytes.append(byte)
            if len(last_20_bytes) > 20:
                last_20_bytes.pop(0)
            
            if byte == 0xAA:  # Header byte
                header_count += 1
                if header_count <= 5:
                    hex_bytes = ' '.join([f'{b:02X}' for b in last_20_bytes[-13:]])
                    print(f"Header found! Next 12 bytes: {hex_bytes}")
    
    time.sleep(0.01)

print("-" * 60)
print(f"Total bytes received: {bytes_received}")
print(f"Header bytes (0xAA) found: {header_count}")
print(f"Expected: ~2 packets per Arduino loop (13 bytes each)")

if bytes_received == 0:
    print("\n⚠️  ERROR: No data received from Arduino!")
    print("Possible issues:")
    print("  - Arduino not running/not programmed")
    print("  - Wrong COM port")
    print("  - Baud rate mismatch")
elif header_count == 0:
    print("\n⚠️  WARNING: Data received but no headers found!")
    print("Last 20 bytes received:")
    hex_str = ' '.join([f'{b:02X}' for b in last_20_bytes])
    print(f"  {hex_str}")
elif header_count > 0:
    print(f"\n✓ Headers found! Arduino is sending packets.")
    packets_expected = (bytes_received / 13)
    print(f"  Approximate packets: {packets_expected:.0f}")

ser.close()
