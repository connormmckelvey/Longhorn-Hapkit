"""python/main.py

Interactive Haplink connector with multi-threaded, non-blocking updates.

Connects to the Hapkit Arduino over Haplink and then *waits for you* to choose
which mode/environment to run (param id 0).

Notes:
- If you're running the 1DOF firmware in src/main.cpp, mode 0-7 are:
    ZERO, SPRING, DAMPER, SPRING_DAMPER, WALL, BUMP_VALLEY, TEXTURE, CAR_GAME.
- If you're running the 2DOF firmware in src/main2DOF.cpp, mode 0-8 are:
    ZERO, JOYSTICK, GRID, CIRCLES, HARP, DAMP, WALL, JOYSTICK_DAMPED, BOX_OBSTACLE.
"""

import time
import threading
import sys
import serial.tools.list_ports
from haplink import Haplink, DataType

MODES_1DOF = {
    "ZERO": 0,
    "SPRING": 1,
    "DAMPER": 2,
    "SPRING_DAMPER": 3,
    "WALL": 4,
    "BUMP_VALLEY": 5,
    "TEXTURE": 6,
    "CAR_GAME": 7,
}

MODES_2DOF = {
    "ZERO": 0,
    "JOYSTICK": 1,
    "GRID": 2,
    "CIRCLES": 3,
    "HARP": 4,
    "DAMP": 5,
    "WALL": 6,
    "JOYSTICK_DAMPED": 7,
    "BOX_OBSTACLE": 8,
}


def _parse_mode(user_text: str) -> int:
    text = user_text.strip()
    if not text:
        raise ValueError("empty")

    upper = text.upper()
    if upper in MODES_1DOF:
        return MODES_1DOF[upper]
    if upper in MODES_2DOF:
        return MODES_2DOF[upper]

    # Accept ints like: 8, 0x08
    return int(text, 0)


def _print_mode_help() -> None:
    print("Available named modes (1DOF src/main.cpp):")
    for name, val in MODES_1DOF.items():
        print(f"  {val}: {name}")
    print("\nAvailable named modes (2DOF src/main2DOF.cpp):")
    for name, val in MODES_2DOF.items():
        print(f"  {val}: {name}")
    print()


def find_hapkit_port() -> str:
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = p.description.lower()
        if "ch340" in desc or "arduino" in desc or "usb-serial" in desc or "usb serial" in desc:
            return p.device
    if ports:
        return ports[0].device
    return "COM5"  # default fallback


class HaplinkThread(threading.Thread):
    def __init__(self, port: str, baudrate: int):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.link = Haplink(port, baudrate=baudrate)
        self.lock = threading.Lock()
        self.running = False
        self.connected = False

    def run(self):
        print(f"Connecting to Arduino on {self.port}...")
        self.connected = self.link.connect()
        if not self.connected:
            return

        print("✓ Connected!\n")
        self.running = True
        while self.running:
            with self.lock:
                try:
                    self.link.update(debug=False)
                except Exception:
                    pass
            time.sleep(0.005)  # 200 Hz update loop

    def set_param(self, name: str, val) -> None:
        with self.lock:
            self.link.set_param(name, val)

    def get_telemetry(self, name: str):
        with self.lock:
            return self.link.get_telemetry(name)

    def register_param(self, param_id: int, name: str, data_type: DataType) -> None:
        self.link.register_param(param_id, name, data_type)

    def register_telemetry(self, telemetry_id: int, name: str, data_type: DataType) -> None:
        self.link.register_telemetry(telemetry_id, name, data_type)

    def stop(self) -> None:
        self.running = False
        self.join()
        with self.lock:
            self.link.disconnect()


def main() -> None:
    port = find_hapkit_port()
    if len(sys.argv) > 1:
        port = sys.argv[1]

    # Instantiate the thread wrapper
    haplink_thread = HaplinkThread(port, baudrate=115200)

    # Register parameters and telemetry before connecting
    # Param 0 exists in both firmwares (1DOF: environment, 2DOF: hapticMode)
    haplink_thread.register_param(0, "mode", DataType.UINT8)

    # 1DOF extra params/telemetry
    haplink_thread.register_param(1, "road_pull", DataType.FLOAT)
    haplink_thread.register_param(2, "surface_state", DataType.INT16)
    haplink_thread.register_param(3, "game_speed", DataType.FLOAT)

    # 2DOF extra params
    haplink_thread.register_param(10, "rect0_x", DataType.FLOAT)
    haplink_thread.register_param(11, "rect0_y", DataType.FLOAT)
    haplink_thread.register_param(12, "rect0_w", DataType.FLOAT)
    haplink_thread.register_param(13, "rect0_h", DataType.FLOAT)

    # Telemetry registers
    # For 1DOF: position=handle_pos, velocity=handle_vel
    # For 2DOF: position=ee_x, velocity=ee_y
    haplink_thread.register_telemetry(0, "position", DataType.FLOAT)
    haplink_thread.register_telemetry(1, "velocity", DataType.FLOAT)

    # Start connection and update loop in background
    haplink_thread.daemon = True
    haplink_thread.start()

    # Wait a moment for connection attempt
    time.sleep(1.5)
    if not haplink_thread.connected:
        print(f"ERROR: Failed to connect on {port}.")
        sys.exit(1)

    _print_mode_help()
    print("Waiting for you to choose a mode.\n"
          "- Enter a number (e.g. 7 or 8) or a name (e.g. CAR_GAME or BOX_OBSTACLE).\n"
          "- Press Enter to just poll telemetry once.\n"
          "- Type 'help' to reprint modes, 'q' to quit.\n")

    try:
        while True:
            user = input("mode> ").strip()
            if user == "":
                pos = haplink_thread.get_telemetry("position")
                vel = haplink_thread.get_telemetry("velocity")
                pos_str = f"{pos:.6f}" if pos is not None else "waiting"
                vel_str = f"{vel:.6f}" if vel is not None else "waiting"
                print(f"telemetry: position/x={pos_str}  velocity/y={vel_str}")
                continue

            lower = user.lower()
            if lower in {"q", "quit", "exit"}:
                break
            if lower in {"h", "help", "?"}:
                _print_mode_help()
                continue

            try:
                mode_val = _parse_mode(user)
                haplink_thread.set_param("mode", mode_val)
                # Let the background thread send the update packets
                print(f"✓ Sent mode -> {mode_val}")
            except ValueError:
                print("Invalid mode name or integer value. Type 'help' for details.")

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        haplink_thread.stop()


if __name__ == "__main__":
    main()
