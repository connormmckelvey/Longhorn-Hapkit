from haplink import Haplink, DataType


PORT = "COM5"
BAUDRATE = 115200

# Must match the enum values in src/main.cpp
ENV_BUMPS = 3


haplink = Haplink(PORT, baudrate=BAUDRATE)
print(f"Connecting to Arduino on {PORT} @ {BAUDRATE}...")
if not haplink.connect():
    raise SystemExit("ERROR: Failed to connect (check port/baud/Arduino).")

# Register parameters (IDs must match src/main.cpp)
haplink.register_param(0, 'environment', DataType.UINT8)
haplink.register_param(3, 'bumpSpacing_m', DataType.FLOAT)

# Ensure we're in the bumps environment
haplink.set_param('environment', ENV_BUMPS)
print(f"Set environment -> {ENV_BUMPS} (BUMPS)")

try:
    while True:
        haplink.update()

        bumpspace = float(input("Enter new bump spacing (m): "))
        haplink.set_param('bumpSpacing_m', bumpspace)


        haplink.update()
        print("Updated bump parameters.\n")

except KeyboardInterrupt:
    print("\nExiting...")
finally:
    haplink.disconnect()
    