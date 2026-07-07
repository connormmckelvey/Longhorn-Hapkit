# Hapkit Port Finder
# run this script to find the serial port that the Hapkit is connected to. It will print the port name and exit.
# written by Connor McKelvey, 2026

import serial.tools.list_ports

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
    else:
        print(f"Hapkit found on port: {port}")

if __name__ == "__main__":
    main()