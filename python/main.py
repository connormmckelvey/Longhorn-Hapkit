"""
Simple communication test with Arduino main.cpp

Verify that Python can connect and communicate with the Hapkit Arduino device.
"""

from haplink import Haplink, DataType
import time

# Connect to device
haplink = Haplink('COM5', baudrate=115200)
print("Connecting to Arduino...")
if not haplink.connect():
    print("ERROR: Failed to connect")
    exit(1)

print("✓ Connected!\n")

# Register parameters (must match IDs in Arduino main.cpp)
print("Registering parameters...")
haplink.register_param(0, 'environment', DataType.UINT8)
haplink.register_param(1, 'k_wall', DataType.FLOAT)  # Changed to FLOAT - Arduino double is 4 bytes
haplink.register_param(2, 'K_spring', DataType.FLOAT)  # Changed to FLOAT

# Register telemetry (must match IDs in Arduino main.cpp)
print("Registering telemetry...")
haplink.register_telemetry(0, 'position', DataType.FLOAT)  # Changed to FLOAT - Arduino double is 4 bytes
haplink.register_telemetry(1, 'velocity', DataType.FLOAT)  # Changed to FLOAT
print("✓ Registered\n")

# Test: Read telemetry for 5 seconds
print("Reading telemetry for 5 seconds...")
print("(Debug mode enabled for first few updates)")
print("-" * 60)
print(f"{'Time(s)':>8} | {'Position':>12} | {'Velocity':>12}")
print("-" * 60)

start_time = time.time()
loops = 0
while time.time() - start_time < 5.0:
    # Enable debug for first 3 updates to see what's happening
    debug_enabled = loops < 3
    packets = haplink.update(debug=debug_enabled)
    
    pos = haplink.get_telemetry('position')
    vel = haplink.get_telemetry('velocity')
    elapsed = time.time() - start_time
    
    pos_str = f"{pos:.6f}" if pos is not None else "waiting"
    vel_str = f"{vel:.6f}" if vel is not None else "waiting"
    
    print(f"{elapsed:>8.2f} | {pos_str:>12} | {vel_str:>12} | pkts:{packets}")
    loops += 1
    time.sleep(0.1)

print("-" * 60)
print()

# Test: Change environment parameter
print("Testing parameter write...")
print(f"Setting environment to 0 (VIRTUAL_WALL)...")
haplink.set_param('environment', 0x00)
print(f"✓ Sent\n")

# Read telemetry again for 3 seconds with new environment
print("Reading telemetry with new environment...")
print("-" * 60)
print(f"{'Time(s)':>8} | {'Position':>12} | {'Velocity':>12}")
print("-" * 60)

start_time = time.time()
while time.time() - start_time < 3.0:
    haplink.update()
    
    pos = haplink.get_telemetry('position')
    vel = haplink.get_telemetry('velocity')
    elapsed = time.time() - start_time
    
    pos_str = f"{pos:.6f}" if pos is not None else "waiting"
    vel_str = f"{vel:.6f}" if vel is not None else "waiting"
    
    print(f"{elapsed:>8.2f} | {pos_str:>12} | {vel_str:>12}")
    time.sleep(0.1)

print("-" * 60)
print()

# Show final state
print("Summary:")
print(f"  Position: {haplink.get_telemetry('position')}")
print(f"  Velocity: {haplink.get_telemetry('velocity')}")
print(f"  Environment: {haplink.get_param_value('environment')}")

haplink.disconnect()
print("\n✓ Test complete!")
