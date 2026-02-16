"""
Hapkit Serial Communication Controller
Interactive command-line interface for communicating with Hapkit Arduino firmware.

Usage:
    - Type commands in the format: TYPE VALUE (e.g., "F 0.25")
    - Type 'quit' or 'exit' to disconnect and exit
    - Type 'stats' to view communication statistics
    - Type 'stream on' or 'stream off' to enable/disable data streaming
    - Type 'help' for command reference
"""

import sys
import time
import threading
# Import the SerialCommunication class
from serial_communication import SerialCommunication


class HapkitController:
    """Interactive controller for Hapkit serial communication."""
    
    def __init__(self, port: str = "COM6", baudrate: int = 115200, debug: bool = True):
        """
        Initialize the Hapkit controller.
        
        Args:
            port: Serial port (e.g., "COM3" on Windows, "/dev/ttyACM0" on Linux)
            baudrate: Baud rate (default 115200)
            debug: Enable debug messages from Arduino
        """
        self.comm = SerialCommunication(
            port=port,
            baudrate=baudrate,
            timeout=0.01,
            debug_enabled=debug
        )
        self.running = False
        self.receive_thread = None
        
    def connect(self) -> bool:
        """Establish connection with handshake."""
        print(f"Connecting to {self.comm.port} at {self.comm.baudrate} baud...")
        
        if not self.comm.connect(handshake_timeout=5.0):
            print("❌ Connection failed! Check port and Arduino connection.")
            return False
        
        print("✓ Connected and ready!")
        return True
    
    def start_receive_loop(self):
        """Start background thread for receiving data."""
        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receive_thread.start()
    
    def _receive_loop(self):
        """Background thread that continuously reads data."""
        while self.running:
            self.comm.update()
            
            # Check for new debug messages
            if self.comm.last_debug_message:
                print(f"  [DEBUG] {self.comm.last_debug_message}")
                self.comm.last_debug_message = ""
            
            # Display position/velocity at moderate rate
            if self.comm.packet_count > 0:
                time.sleep(0.05)  # Update display ~20x per second
            else:
                time.sleep(0.001)
    
    def display_status(self):
        """Display current position and velocity."""
        pos, vel = self.comm.get_state()
        print(f"  Position: {pos:8.4f} m  |  Velocity: {vel:8.4f} m/s")
    
    def send_command(self, cmd_type: str, value: float):
        """Send a command to the Arduino."""
        self.comm.send_command(cmd_type, value)
        print(f"  → Sent: {cmd_type} {value}")
    
    def show_help(self):
        """Display help information."""
        help_text = """
╔════════════════════════════════════════════════════════════════╗
║              HAPKIT COMMAND REFERENCE                          ║
╚════════════════════════════════════════════════════════════════╝

COMMAND FORMAT: TYPE VALUE
  Example: F 0.25
  
CONTROL COMMANDS:
  S 0        Disable data streaming
  S 1        Enable data streaming
  
SYSTEM COMMANDS:
  help       Show this help message
  status     Display current position and velocity
  stats      Show communication statistics
  clear      Clear screen
  quit/exit  Disconnect and exit
  
EXAMPLE SESSION:
  > S 1                  (Enable streaming)
  > S 0                  (Disable streaming)
  > stats                (View statistics)
  > quit                 (Exit)
  
NOTE: Position/velocity data displays when streaming is enabled.
        """
        print(help_text)
    
    def show_stats(self):
        """Display communication statistics."""
        stats = self.comm.get_stats()
        print(f"""
  ╔═══════════════════════════════════╗
  ║   COMMUNICATION STATISTICS        ║
  ╠═══════════════════════════════════╣
  ║ Bytes Sent:       {stats['bytes_sent']:>10} B     ║
  ║ Bytes Received:   {stats['bytes_received']:>10} B     ║
  ║ Packets Received: {stats['packets_received']:>10}       ║
  ║ Connected:        {str(self.comm.is_connected()):>10}   ║
  ╚═══════════════════════════════════╝
        """)
    
    def interactive_loop(self):
        """Main interactive command loop."""
        print("\n" + "="*70)
        print("  HAPKIT CONTROLLER - INTERACTIVE SERIAL COMMUNICATION")
        print("="*70)
        print("Type 'help' for commands or just start typing commands")
        print("="*70 + "\n")
        
        while self.running:
            try:
                user_input = input("\n> ").strip()
                
                if not user_input:
                    continue
                
                # System commands
                if user_input.lower() in ["quit", "exit"]:
                    print("\nDisconnecting...")
                    self.disconnect()
                    break
                
                elif user_input.lower() == "help":
                    self.show_help()
                
                elif user_input.lower() == "status":
                    self.display_status()
                
                elif user_input.lower() == "stats":
                    self.show_stats()
                
                elif user_input.lower() == "clear":
                    import os
                    os.system("cls" if sys.platform == "win32" else "clear")
                
                # Stream control
                elif user_input.lower() == "stream on":
                    self.send_command("S", 1.0)
                
                elif user_input.lower() == "stream off":
                    self.send_command("S", 0.0)
                
                # General command format: TYPE VALUE
                else:
                    parts = user_input.split()
                    if len(parts) == 2:
                        cmd_type = parts[0].upper()
                        try:
                            value = float(parts[1])
                            self.send_command(cmd_type, value)
                        except ValueError:
                            print(f"  ❌ Invalid value: '{parts[1]}' is not a number")
                    else:
                        print(f"  ❌ Invalid format. Use: TYPE VALUE (e.g., 'F 0.25')")
                        print(f"     Or type 'help' for more information")
            
            except KeyboardInterrupt:
                print("\n\nInterrupt received. Disconnecting...")
                self.disconnect()
                break
            except Exception as e:
                print(f"  ❌ Error: {e}")
    
    def disconnect(self):
        """Disconnect and clean up."""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=1.0)
        self.comm.close()
        print("✓ Disconnected")
    
    def run(self):
        """Run the controller."""
        if not self.connect():
            return False
        
        self.start_receive_loop()
        self.interactive_loop()
        return True


def main():
    """Main entry point."""
    # Configuration
    PORT = "COM6"              # Change to your Arduino port
    BAUDRATE = 115200
    DEBUG_ENABLED = True
    
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║         HAPKIT SERIAL COMMUNICATION INTERFACE v1.0             ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"\nConfiguration:")
    print(f"  Port:     {PORT}")
    print(f"  Baudrate: {BAUDRATE}")
    print(f"  Debug:    {DEBUG_ENABLED}")
    
    controller = HapkitController(port=PORT, baudrate=BAUDRATE, debug=DEBUG_ENABLED)
    success = controller.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
