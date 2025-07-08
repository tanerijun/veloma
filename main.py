import sys
import time
import threading
from typing import Dict, Any
from PyQt6.QtWidgets import QApplication

from app.vision import HandTracker
from app.music import PITCH_X_MARGIN, VelomaInstrument, get_scale_names
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

        self.show_note_boundaries = True

    def _start_tracking(self) -> bool:
        """Start the hand tracking and audio synthesis."""
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

        return True

    def _stop_tracking(self):
        """Stop the hand tracking and audio synthesis."""
        self.is_running = False
        self.instrument.stop_audio()
        self.hand_tracker.stop_camera()

        # Wait for main thread to finish
        if self.main_thread and self.main_thread.is_alive():
            self.main_thread.join(timeout=2.0)

    def _update_settings(self, settings: Dict[str, Any]):
        """Update instrument settings from UI."""
        # Update pitch range
        start_key = settings.get('start_key', 60)
        octave_range = settings.get('octave_range', 2)
        self.instrument.start_key = start_key
        self.instrument.octave_range = octave_range
        self.instrument.pitch_range = (start_key, start_key + octave_range * 12)

        # Update smoothing
        # smoothing = settings.get('smoothing', 0.1)
        # self.instrument.pitch_smoothing = smoothing
        # self.instrument.volume_smoothing = smoothing

        # Update scale
        scale_name = settings.get('scale', get_scale_names()[0])
        self.instrument.set_scale(scale_name)

        # Update glide mode
        self.instrument.glide_mode = settings.get('glide_mode', False)

        # Update show boundaries setting
        self.show_note_boundaries = settings.get('show_note_boundaries', True)

        if self.instrument.glide_mode:
            self.instrument.set_instrument("Sine Wave")
            # If hands are detected and should_play, start note immediately
            if self.last_hand_data and self.last_hand_data.get("hands"):
                self.instrument.update_from_vision(self.last_hand_data)
        else:
            self.instrument.set_instrument("Piano")

    def _main_loop(self):
        """Main processing loop"""
        while self.is_running:
            try:
                hand_data = self.hand_tracker.get_hand_positions()
                now = time.time()

                frame = None
                if hand_data:
                    frame = hand_data.get('frame')

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

                if hand_data:
                    self.instrument.update_from_vision(use_hand_data)
                    if frame is not None:
                        frame_with_landmarks = self.hand_tracker.draw_landmarks(frame, hand_data)
                        if not self.instrument.glide_mode and self.show_note_boundaries:
                            num_notes = len(self.instrument.pitch_pool)
                            region_start = 0.5
                            region_end = 1.0 - PITCH_X_MARGIN
                            frame_with_landmarks = self.hand_tracker.draw_note_boundaries(
                                frame_with_landmarks, num_notes, region_start, region_end
                            )
                        self.ui.update_camera_frame(frame_with_landmarks)
                    self.ui.update_audio_params(
                        self.instrument.current_pitch,
                        self.instrument.current_volume
                    )
                else:
                    # No valid hand data for too long: force note off
                    self.instrument.update_from_vision({'hands': []})
                    if frame is not None:
                        self.ui.update_camera_frame(frame)

                time.sleep(0.01)
            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(0.1)

    def run(self):
        self.ui.run()
        if self.app:
            self.app.aboutToQuit.connect(self.cleanup)
            return self.app.exec()
        return 0

    def cleanup(self):
        """Clean up all resources."""
        if self.is_running:
            self._stop_tracking()

        if self.ui:
            self.ui.cleanup()


def main():
    app = VelomaApp()
    app.run()


if __name__ == "__main__":
    main()
