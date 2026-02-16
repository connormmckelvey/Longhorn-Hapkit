import time
import serial

class SerialCommunication:
    """
    Python class to manage serial communication with the serial_communication.h module. Designed for haptic feedback applications, but can be adapted for other uses.

    This will create commands in the expected format for the firmware format:
        <COMMAND_TYPE><DELIMITER (default space)><VALUE>
    
    Recieves data in the format:
        <POSITION>,<VELOCITY>
    or
        DBG:<MSG>
    """
    # =========================================================
    # Initialization (Does NOT auto-connect)
    # =========================================================

    def __init__(self,
                 port: str,
                 baudrate: int = 115200,
                 timeout: float = 0.001,
                 delimiter: str = ' ',
                 debug_enabled: bool = False):

        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.delimiter = delimiter
        self.debug_enabled = debug_enabled

        self.ser = None
        self.connected = False

        # State variables
        self.position = 0.0
        self.velocity = 0.0
        self.last_update_time = 0.0

        # Debug
        self.last_debug_message = ""

        # Diagnostics
        self.bytes_sent = 0
        self.bytes_received = 0
        self.packet_count = 0

    # =========================================================
    # Connection / Handshake
    # =========================================================

    def connect(self, handshake_timeout: float = 2.0) -> bool:
        """
        Opens serial port and performs handshake.

        Sends:
            HELLO

        Expects:
            READY

        Returns True if successful, False otherwise.
        """

        try:
            self.ser = serial.Serial(self.port,
                                     self.baudrate,
                                     timeout=self.timeout)
        except serial.SerialException as e:
            print(f"failed error: {e}")
            return False
        
        # Allow Arduino reset
        time.sleep(2)

        # Clear buffer
        self.ser.reset_input_buffer()

        # Send handshake
        self.ser.write(b"HELLO\n")

        start_time = time.time()

        while time.time() - start_time < handshake_timeout:

            line = self.ser.readline()

            if not line:
                continue

            try:
                decoded = line.decode('utf-8').strip()
            except UnicodeDecodeError:
                continue

            if decoded == "READY":
                self.connected = True
                return True

        # If timeout reached
        self.ser.close()
        self.connected = False
        return False

    def close(self):
        if self.ser and self.connected:
            self.ser.close()
        self.connected = False

    # =========================================================
    # Command Sending
    # =========================================================

    def send_command(self, cmd_type: str, value: float):

        if not self.connected:
            return

        message = f"{cmd_type}{self.delimiter}{value}\n"
        encoded = message.encode('utf-8')

        self.ser.write(encoded)
        self.bytes_sent += len(encoded)

    # =========================================================
    # Receiving / Update
    # =========================================================

    def update(self):

        if not self.connected:
            return

        line = self.ser.readline()

        if not line:
            return

        self.bytes_received += len(line)

        try:
            decoded = line.decode('utf-8').strip()
        except UnicodeDecodeError:
            return

        # Debug message
        if decoded.startswith("DBG:"):
            self.last_debug_message = decoded[4:]
            if self.debug_enabled:
                print("[ARDUINO DEBUG]", self.last_debug_message)
            return

        # Position, velocity
        try:
            pos_str, vel_str = decoded.split(",")
            self.position = float(pos_str)
            self.velocity = float(vel_str)
            self.packet_count += 1
            self.last_update_time = time.time()
        except ValueError:
            pass

    # =========================================================
    # Accessors
    # =========================================================

    def get_state(self):
        return self.position, self.velocity

    def is_connected(self):
        return self.connected

    def get_stats(self):
        return {
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "packets_received": self.packet_count
        }