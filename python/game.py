"""
Hapkit Visualization Game
Displays the position and velocity of the hapkit end effector in real-time using pygame.
"""

import pygame
import sys
import threading
from serial_communication import SerialCommunication


class HapkitGame:
    """Pygame visualization for Hapkit end effector position and speed."""
    
    def __init__(self, port: str = "COM6", baudrate: int = 115200, debug: bool = True):
        """
        Initialize the Hapkit game.
        
        Args:
            port: Serial port (e.g., "COM6" on Windows, "/dev/ttyACM0" on Linux)
            baudrate: Baud rate (default 115200)
            debug: Enable debug messages
        """
        # Initialize pygame
        pygame.init()
        
        # Display settings
        self.WIDTH = 1000
        self.HEIGHT = 600
        self.FPS = 60
        
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption("Hapkit Visualization - Position & Speed")
        self.clock = pygame.time.Clock()
        
        # Colors
        self.BLACK = (0, 0, 0)
        self.WHITE = (255, 255, 255)
        self.BLUE = (0, 100, 255)
        self.RED = (255, 50, 50)
        self.GREEN = (50, 200, 50)
        self.GRAY = (100, 100, 100)
        
        # Fonts
        self.font_large = pygame.font.Font(None, 48)
        self.font_medium = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 24)
        
        # Serial communication
        self.comm = SerialCommunication(
            port=port,
            baudrate=baudrate,
            timeout=0.01,
            debug_enabled=debug
        )
        
        self.running = False
        self.connected = False
        self.position = 0.0
        self.velocity = 0.0
        
        # Position scaling for visualization (adjust as needed)
        self.position_min = -0.1  # meters
        self.position_max = 0.1   # meters
        
    def connect(self) -> bool:
        """Establish connection with handshake."""
        print(f"Connecting to {self.comm.port} at {self.comm.baudrate} baud...")
        
        if not self.comm.connect(handshake_timeout=5.0):
            print("❌ Connection failed! Check port and Arduino connection.")
            return False
        
        print("✓ Connected and ready!")
        self.connected = True
        return True
    
    def update(self):
        """Update serial communication and game state."""
        if self.connected:
            self.comm.update()
            self.position, self.velocity = self.comm.get_state()
    
    def render(self):
        """Render the game screen."""
        self.screen.fill(self.BLACK)
        
        # Title
        title = self.font_large.render("Hapkit Visualization", True, self.WHITE)
        self.screen.blit(title, (self.WIDTH // 2 - title.get_width() // 2, 20))
        
        if not self.connected:
            error_text = self.font_medium.render("Not Connected", True, self.RED)
            self.screen.blit(error_text, (self.WIDTH // 2 - error_text.get_width() // 2, 150))
            return
        
        # Position visualization
        self._render_position_meter()
        
        # Position value
        position_text = self.font_medium.render(f"Position: {self.position:.4f} m", True, self.BLUE)
        self.screen.blit(position_text, (50, 350))
        
        # Speed value
        speed_text = self.font_medium.render(f"Speed: {self.velocity:.4f} m/s", True, self.GREEN)
        self.screen.blit(speed_text, (50, 420))
        
        # Connection status
        status_text = self.font_small.render("● Connected", True, self.GREEN)
        self.screen.blit(status_text, (self.WIDTH - 200, self.HEIGHT - 40))
        
        pygame.display.flip()
    
    def _render_position_meter(self):
        """Render a visual meter showing the current position."""
        meter_y = 150
        meter_x_start = 100
        meter_width = 800
        meter_height = 60
        
        # Background
        pygame.draw.rect(self.screen, self.GRAY, (meter_x_start, meter_y, meter_width, meter_height))
        
        # Border
        pygame.draw.rect(self.screen, self.WHITE, (meter_x_start, meter_y, meter_width, meter_height), 2)
        
        # Min and max labels
        min_label = self.font_small.render(f"{self.position_min:.2f}m", True, self.WHITE)
        max_label = self.font_small.render(f"{self.position_max:.2f}m", True, self.WHITE)
        self.screen.blit(min_label, (meter_x_start - 80, meter_y + 20))
        self.screen.blit(max_label, (meter_x_start + meter_width + 10, meter_y + 20))
        
        # Calculate position on meter (clamped)
        normalized_pos = (self.position - self.position_min) / (self.position_max - self.position_min)
        normalized_pos = max(0, min(1, normalized_pos))  # Clamp between 0 and 1
        
        indicator_x = meter_x_start + (normalized_pos * meter_width)
        
        # Draw indicator line
        pygame.draw.line(self.screen, self.RED, (indicator_x, meter_y - 10), (indicator_x, meter_y + meter_height + 10), 3)
        
        # Center line (zero position)
        zero_x = meter_x_start + (0 - self.position_min) / (self.position_max - self.position_min) * meter_width
        pygame.draw.line(self.screen, self.WHITE, (zero_x, meter_y), (zero_x, meter_y + meter_height), 1)
    
    def handle_events(self):
        """Handle pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
    
    def run(self):
        """Main game loop."""
        if not self.connect():
            return
        
        self.running = True
        
        try:
            while self.running:
                self.handle_events()
                self.update()
                self.render()
                self.clock.tick(self.FPS)
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources."""
        self.comm.close()
        pygame.quit()
        print("Game closed.")


def main():
    """Main entry point."""
    game = HapkitGame(port="COM6", debug=False)
    game.run()


if __name__ == "__main__":
    main()
