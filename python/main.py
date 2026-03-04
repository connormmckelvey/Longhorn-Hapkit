"""python/main.py

Interactive Haplink connector.

Connects to the Hapkit Arduino over Haplink and then *waits for you* to choose
which mode/environment to run (param id 0).

Notes:
- If you're running the 1DOF firmware in src/main.cpp, mode 0-4 are:
    VIRTUAL_WALL, VIRTUAL_SPRING, CONST_DAMPENER, BUMPS, FISHROD_CAST.
- If you're running the 2DOF firmware in src/main2DOF.cpp, mode 0-8 are:
    ZERO, JOYSTICK, GRID, CIRCLES, HARP, DAMP, WALL, JOYSTICK_DAMPED, BOX_OBSTACLE.
"""

from haplink import Haplink, DataType
import time


MODES_1DOF = {
    "VIRTUAL_WALL": 0,
    "VIRTUAL_SPRING": 1,
    "CONST_DAMPENER": 2,
    "BUMPS": 3,
    "FISHROD_CAST": 4,
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

def main() -> None:
    # Connect to device
    haplink = Haplink("COM5", baudrate=115200)
    print("Connecting to Arduino...")
    if not haplink.connect():
        raise SystemExit("ERROR: Failed to connect")

    print("✓ Connected!\n")

    # Register parameters.
    # Param 0 exists in both firmwares (1DOF: environment, 2DOF: hapticMode).
    # The name here is only on the PC side.
    print("Registering parameters...")
    haplink.register_param(0, "mode", DataType.UINT8)

    # These extra params/telemetry match src/main.cpp (1DOF). If you're running the
    # 2DOF firmware, they'll just remain None / unused.
    haplink.register_param(1, "k_wall", DataType.FLOAT)
    haplink.register_param(2, "K_spring", DataType.FLOAT)

    print("Registering telemetry...")
    haplink.register_telemetry(0, "position", DataType.FLOAT)
    haplink.register_telemetry(1, "velocity", DataType.FLOAT)
    print("✓ Registered\n")

    _print_mode_help()
    print("Waiting for you to choose a mode.\n"
          "- Enter a number (e.g. 8 or 0x08) or a name (e.g. BOX_OBSTACLE).\n"
          "- Press Enter to just poll telemetry once.\n"
          "- Type 'help' to reprint modes, 'q' to quit.\n")

    try:
        while True:
            # Keep the link alive / update incoming packets.
            haplink.update(debug=False)

            user = input("mode> ").strip()
            if user == "":
                pos = haplink.get_telemetry("position")
                vel = haplink.get_telemetry("velocity")
                pos_str = f"{pos:.6f}" if pos is not None else "waiting"
                vel_str = f"{vel:.6f}" if vel is not None else "waiting"
                print(f"telemetry: position={pos_str}  velocity={vel_str}")
                continue

            lower = user.lower()
            if lower in {"q", "quit", "exit"}:
                break
            if lower in {"h", "help", "?"}:
                _print_mode_help()
                continue

            mode_val = _parse_mode(user)
            haplink.set_param("mode", mode_val)
            # Give the device a couple update cycles to apply.
            for _ in range(3):
                haplink.update(debug=False)
                time.sleep(0.02)

            print(f"✓ Sent mode -> {mode_val}")

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        haplink.disconnect()


if __name__ == "__main__":
    main()
