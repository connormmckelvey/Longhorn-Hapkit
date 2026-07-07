import serial.tools.list_ports
from haplink import Haplink, DataType

# Auto-detect serial port
def find_hapkit_port() -> str:
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = p.description.lower()
        if "ch340" in desc or "arduino" in desc or "usb-serial" in desc or "usb serial" in desc:
            return p.device
    return -1 

def main():
    port = find_hapkit_port()
    if port == -1:
        print("No serial ports detected! Make sure your device is connected.")
        exit(1)
    else:
        print(f"Hapkit found on port: {port}")

    # Connect to Hapkit and register parameter 0 (haptic_mode)
    link = Haplink('COM8', baudrate=115200)
        
    if not link.connect():
        print("Failed to connect to Hapkit. Exiting.")
        exit(1)
    link.register_param(0, 'haptic_mode', DataType.INT16)

    print("Type a number (0-6) to change the mode. Press Ctrl+C to exit.")

    while True:
        mode = int(input("Enter mode: "))
        link.set_param('haptic_mode', mode)
        # Send parameter packet to the board
        link.update()

if __name__ == "__main__":
    main()