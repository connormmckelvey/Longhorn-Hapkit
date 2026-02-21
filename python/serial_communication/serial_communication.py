import time
import serial


class SerialCommunication:
    """
    Manages serial communication with Hapkit Arduino firmware.
    
    Sends commands in format: TYPE VALUE (e.g., "F 0.25")
    Receives data in format: POSITION,VELOCITY or DBG:MESSAGE
    
    This class handles the low-level serial protocol and state tracking.
    Message display/logging should be handled by the calling code.
    """

    def __init__(self,
                 port: str,
                 baudrate: int = 115200,
                 timeout: float = 0.001,
                 delimiter: str = ' '):
        """
        Initialize SerialCommunication (does not auto-connect).
        
        Args:
            port: Serial port name (e.g., "COM5" on Windows)
            baudrate: Serial communication speed (default 115200)
            timeout: Read timeout in seconds (default 0.001)
            delimiter: Command separator character (default space)
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.delimiter = delimiter

        self.ser = None
        self.connected = False

        # State tracking
        self.position = 0.0
        self.velocity = 0.0
        self.last_update_time = 0.0

        # Latest debug message from device
        self.last_debug_message = ""

        # Communication statistics
        self.bytes_sent = 0
        self.bytes_received = 0
        self.packet_count = 0

    def connect(self, handshake_timeout: float = 2.0) -> bool:
        """
        Open serial port and perform handshake with device.
        
        Handshake protocol:
        - Send: HELLO
        - Expect: READY
        
        Args:
            handshake_timeout: Maximum time to wait for READY response (seconds)
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.ser = serial.Serial(self.port,
                                     self.baudrate,
                                     timeout=self.timeout)
        except serial.SerialException as e:
            print(f"Connection error: {e}")
            return False

        # Allow Arduino to reset after opening serial port
        time.sleep(2)

        # Clear any spurious data in buffer
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

        # Handshake timeout
        self.ser.close()
        self.connected = False
        return False

    def close(self) -> None:
        """Close the serial connection."""
        if self.ser and self.connected:
            self.ser.close()
        self.connected = False

    def send_command(self, cmd_type: str, value: float) -> None:
        """
        Send a command to the device.
        
        Args:
            cmd_type: Command type identifier (e.g., "F", "S")
            value: Command value (converted to float)
        """
        if not self.connected:
            return

        message = f"{cmd_type}{self.delimiter}{value}\n"
        encoded = message.encode('utf-8')
        self.ser.write(encoded)
        self.bytes_sent += len(encoded)

    def update(self) -> None:
        """
        Update state by reading and processing incoming data.
        
        Handles two message types:
        - Position/Velocity: "POSITION,VELOCITY"
        - Debug messages: "DBG:MESSAGE"
        """
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

        # Debug message from device
        if decoded.startswith("DBG:"):
            self.last_debug_message = decoded[4:]
            return

        # Position and velocity data
        try:
            pos_str, vel_str = decoded.split(",")
            self.position = float(pos_str)
            self.velocity = float(vel_str)
            self.packet_count += 1
            self.last_update_time = time.time()
        except ValueError:
            # Malformed data, ignore
            pass

    def get_state(self) -> tuple:
        """
        Get current position and velocity.
        
        Returns:
            Tuple of (position, velocity)
        """
        return self.position, self.velocity

    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self.connected

    def get_stats(self) -> dict:
        """
        Get communication statistics.
        
        Returns:
            Dictionary with keys: bytes_sent, bytes_received, packets_received
        """
        return {
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "packets_received": self.packet_count
        }