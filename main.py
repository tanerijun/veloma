import sys
import time
import threading
from typing import Dict, Any
from PyQt6.QtWidgets import QApplication

from app.vision import HandTracker
from app.music import VelomaInstrument, get_scale_names
from app.ui import VelomaUI


class VelomaApp:
    def __init__(self):
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication(sys.argv)

        self.hand_tracker = HandTracker()
        self.instrument = VelomaInstrument()
        self.ui = VelomaUI()

        self.is_running = False
        self.main_thread = None

        self.ui.set_callbacks(
            on_start=self._start_tracking,
            on_stop=self._stop_tracking,
            on_settings_change=self._update_settings
        )

        self.last_hand_data = None
        self.last_hand_time = 0
        self.hand_hold_timeout = 0.5  # seconds to hold last hand data on dropout

    def _start_tracking(self) -> bool:
        """Start the hand tracking and audio synthesis."""
        print("Starting Veloma...")

        # Start camera
        if not self.hand_tracker.start_camera():
            print("Failed to start camera!")
            return False

        self.instrument.start_audio()

        # Start main processing loop
        self.is_running = True
        self.main_thread = threading.Thread(target=self._main_loop)
        self.main_thread.daemon = True
        self.main_thread.start()

        print("Veloma started successfully!")
        return True

    def _stop_tracking(self):
        """Stop the hand tracking and audio synthesis."""
        print("Stopping Veloma...")

        self.is_running = False
        self.instrument.stop_audio()
        self.hand_tracker.stop_camera()

        # Wait for main thread to finish
        if self.main_thread and self.main_thread.is_alive():
            self.main_thread.join(timeout=2.0)

        print("Veloma stopped.")

    def _update_settings(self, settings: Dict[str, Any]):
        """Update instrument settings from UI."""
        # Update pitch range
        start_key = settings.get('start_key', 60)
        octave_range = settings.get('octave_range', 2)
        self.instrument.start_key = start_key
        self.instrument.octave_range = octave_range
        self.instrument.pitch_range = (start_key, start_key + octave_range * 12)

        # Update smoothing
        smoothing = settings.get('smoothing', 0.1)
        self.instrument.pitch_smoothing = smoothing
        self.instrument.volume_smoothing = smoothing

        # Update scale
        scale_name = settings.get('scale', get_scale_names()[0])
        self.instrument.set_scale(scale_name)

        # Update glide mode
        self.instrument.glide_mode = settings.get('glide_mode', False)

        print(f"Settings updated: {settings}")

    def _main_loop(self):
        """Main processing loop"""
        print("Main processing loop started")

        while self.is_running:
            try:
                hand_data = self.hand_tracker.get_hand_positions()
                now = time.time()

                if hand_data and hand_data.get('hands'):
                    self.last_hand_data = hand_data
                    self.last_hand_time = now
                    use_hand_data = hand_data
                else:
                    # Use cached hand data only if within timeout
                    if self.last_hand_data and (now - self.last_hand_time) < self.hand_hold_timeout:
                        use_hand_data = self.last_hand_data
                    else:
                        use_hand_data = None

                if use_hand_data is not None:
                    self.instrument.update_from_vision(use_hand_data)
                    frame = use_hand_data.get('frame')
                    if frame is not None:
                        frame_with_landmarks = self.hand_tracker.draw_landmarks(frame, use_hand_data)
                        self.ui.update_camera_frame(frame_with_landmarks)
                    self.ui.update_audio_params(
                        self.instrument.current_pitch,
                        self.instrument.current_volume
                    )
                    hands_count = len(use_hand_data.get('hands', []))
                    self.ui.update_hands_count(hands_count)
                else:
                    # No valid hand data for too long: force note off
                    self.instrument.update_from_vision({'hands': []})
                    self.ui.update_hands_count(0)

                time.sleep(0.01)
            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(0.1)

        print("Main processing loop ended")

    def run(self):
        print("Starting Veloma...")
        self.ui.run()
        if self.app:
            self.app.aboutToQuit.connect(self.cleanup)
            return self.app.exec()
        return 0

    def cleanup(self):
        """Clean up all resources."""
        print("Cleaning up...")

        if self.is_running:
            self._stop_tracking()

        if self.ui:
            self.ui.cleanup()

        print("Cleanup complete.")


def main():
    print("=" * 50)
    print("Veloma - Virtual Theremin")
    print("Gesture-controlled musical instrument")
    print("=" * 50)

    app = VelomaApp()
    app.run()


if __name__ == "__main__":
    main()
