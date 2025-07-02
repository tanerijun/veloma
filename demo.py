#!/usr/bin/env python3
"""
Veloma Demo Script

This script demonstrates the basic functionality of Veloma without requiring
the full GUI. It shows how the vision and music modules work together.

Run this script to test the core functionality:
- Hand tracking from webcam
- Audio synthesis based on hand positions
- Real-time parameter mapping

Press 'q' to quit, 'spacebar' to toggle audio on/off.
"""

import cv2
import time
from app.vision import HandTracker
from app.music import VelomaInstrument

class VelomaDemo:

    def __init__(self):
        self.tracker = HandTracker()
        self.instrument = VelomaInstrument()
        self.is_running = False
        self.audio_enabled = True

    def run(self):
        print("Veloma Demo - Core Functionality Test")
        print("=" * 50)
        print("Testing audio first...")

        self.instrument.start_audio()
        print("Playing test note...")
        # self.instrument.theremin.play_note(72, 1, 2.0)  # Test note
        time.sleep(0.5)
        print("Audio test complete!")

        print("\nControls:")
        print("  • Move hand up/down: Control pitch")
        print("  • Move hand left/right: Control volume")
        print("  • Use two hands for advanced control")
        print("  • Press SPACEBAR: Toggle audio on/off")
        print("  • Press 'q': Quit")
        print("= " * 50)

        if not self.tracker.start_camera():
            print("Failed to start camera!")
            self.instrument.stop_audio()
            return

        self.is_running = True

        print("Camera and audio started successfully!")
        print("Move your hands to make music!")

        # self.instrument.theremin.play_note(65, 1, 2)  # Test note
        # self.instrument.theremin.play_note(64, 1, 2)  # Test note
        # self.instrument.theremin.play_note(62, 1, 2)  # Test note

       
        try:
            while self.is_running:
                # Get hand data
                hand_data = self.tracker.get_hand_positions()

                if hand_data:
                    # Process audio if enabled
                    if self.audio_enabled:
                        self.instrument.update_from_vision(hand_data)
                    else:
                        # Fade out when audio disabled
                        self.instrument.update_from_vision({'hands': []})
                      

                    # Display frame with landmarks
                    frame = hand_data['frame']
                    frame_with_landmarks = self.tracker.draw_landmarks(frame, hand_data)

                    # Add status text
                    self._add_status_text(frame_with_landmarks, hand_data)

                    # Show frame
                    cv2.imshow('Veloma Demo - Press q to quit, SPACE to toggle audio', frame_with_landmarks)

                    # Print hand info
                    self._print_hand_info(hand_data)

                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord(' '):  # Spacebar
                    self.audio_enabled = not self.audio_enabled
                    status = "ON" if self.audio_enabled else "OFF"
                    print(f"Audio: {status}")

        except KeyboardInterrupt:
            print("\nDemo stopped by user")

        finally:
            self.cleanup()

    def _add_status_text(self, frame, hand_data):
        """Add status information to the frame."""
        h, w = frame.shape[:2]

        # Audio status
        audio_status = "ON" if self.audio_enabled else "OFF"
        audio_color = (0, 255, 0) if self.audio_enabled else (0, 0, 255)
        cv2.putText(frame, f"Audio: {audio_status}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, audio_color, 2)

        # Hand count
        hand_count = len(hand_data.get('hands', []))
        cv2.putText(frame, f"Hands: {hand_count}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

        # Current parameters
        pitch = self.instrument.current_pitch
        volume = self.instrument.current_volume
        cv2.putText(frame, f"Pitch: {pitch:.1f}", (10, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        cv2.putText(frame, f"Volume: {volume:.2f}", (10, 120),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

        # Instructions
        instructions = [
            "Move hand up/down: Pitch",
            "Move hand left/right: Volume",
            "SPACE: Toggle audio",
            "Q: Quit"
        ]

        start_y = h - 120
        for i, instruction in enumerate(instructions):
            cv2.putText(frame, instruction, (10, start_y + i * 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    def _print_hand_info(self, hand_data):
        """Print hand position info to console."""
        if not hand_data.get('hands'):
            return

        hands = hand_data['hands']
        info_parts = []

        for i, hand in enumerate(hands):
            palm_x, palm_y = hand['palm_center']
            info_parts.append(f"Hand {i+1}: ({palm_x:.2f}, {palm_y:.2f})")

        # Add current audio parameters
        pitch = self.instrument.current_pitch
        volume = self.instrument.current_volume
        info_parts.append(f"Pitch: {pitch:.1f}")
        info_parts.append(f"Volume: {volume:.2f}")

        # Print on same line (overwrite previous)
        print(f"\r{' | '.join(info_parts)}", end='', flush=True)

    def cleanup(self):
        """Clean up resources."""
        print(f"\nCleaning up...")

        self.is_running = False
        self.instrument.stop_audio()
        self.tracker.stop_camera()
        cv2.destroyAllWindows()

        print("Demo cleanup complete!")


def main():
    try:
        demo = VelomaDemo()
        demo.run()
    except Exception as e:
        print(f"Demo failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
