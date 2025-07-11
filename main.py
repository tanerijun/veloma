import sys
import time
from typing import Any, Dict

from PyQt6.QtWidgets import QApplication

from app.music import (
    GLIDE_MODE_INSTRUMENT,
    INSTRUMENTS,
    PITCH_X_MARGIN,
    VelomaInstrument,
    get_scale_names,
)
from app.ui import VelomaUI
from app.vision import HandTracker


class VelomaApp:
    def __init__(self):
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication(sys.argv)

        self.hand_tracker = HandTracker()
        self.instrument = VelomaInstrument()
        self.ui = VelomaUI()

        self.is_running = False

        self.ui.set_callbacks(
            on_start=self._start_tracking,
            on_stop=self._stop_tracking,
            on_settings_change=self._update_settings,
        )

        self.last_hand_data = None
        self.last_hand_time = 0
        self.hand_hold_timeout = 0.5  # seconds to hold last hand data on dropout

        self.show_note_boundaries = True

        self.current_instrument_name = INSTRUMENTS[0]

    def _start_tracking(self) -> bool:
        """Start the hand tracking and audio synthesis."""
        if not self.hand_tracker.start_camera():
            print("Failed to start camera!")
            return False

        self.instrument.start_audio()
        self.is_running = True
        self.hand_tracker.start_async(self._on_hand_data)
        return True

    def _stop_tracking(self):
        """Stop the hand tracking and audio synthesis."""
        self.is_running = False
        self.instrument.stop_audio()
        self.hand_tracker.stop_async()
        self.hand_tracker.stop_camera()

    def _update_settings(self, settings: Dict[str, Any]):
        """Update instrument settings from UI."""
        start_key = settings.get("start_key", 60)
        octave_range = settings.get("octave_range", 2)
        self.instrument.update_pitch_range(start_key, octave_range)

        # Update scale
        scale_name = settings.get("scale", get_scale_names()[0])
        self.instrument.set_scale(scale_name)

        # Update glide mode
        self.instrument.glide_mode = settings.get("glide_mode", False)

        # Update show boundaries setting
        self.show_note_boundaries = settings.get("show_note_boundaries", True)

        # Update instrument
        instrument_name = settings.get("instrument", INSTRUMENTS[0])

        if self.instrument.glide_mode:
            if self.current_instrument_name != GLIDE_MODE_INSTRUMENT:
                self.instrument.set_instrument(GLIDE_MODE_INSTRUMENT)
                self.current_instrument_name = GLIDE_MODE_INSTRUMENT
            if self.last_hand_data and self.last_hand_data.get("hands"):
                self.instrument.update_from_vision(self.last_hand_data)
        else:
            if self.current_instrument_name != instrument_name:
                self.instrument.set_instrument(instrument_name)
                self.current_instrument_name = instrument_name

    def _on_hand_data(self, hand_data):
        now = time.time()
        frame = None
        if hand_data:
            frame = hand_data.get("frame")

        if hand_data and hand_data.get("hands"):
            self.last_hand_data = hand_data
            self.last_hand_time = now
            use_hand_data = hand_data
        else:
            # Use cached hand data only if within timeout
            if (
                self.last_hand_data
                and (now - self.last_hand_time) < self.hand_hold_timeout
            ):
                use_hand_data = self.last_hand_data
            else:
                use_hand_data = None

        if hand_data:
            self.instrument.update_from_vision(use_hand_data)
            if frame is not None:
                frame_with_landmarks = self.hand_tracker.draw_landmarks(
                    frame, hand_data
                )
                if not self.instrument.glide_mode and self.show_note_boundaries:
                    num_notes = len(self.instrument.pitch_pool)
                    region_start = 0.5
                    region_end = 1.0 - PITCH_X_MARGIN
                    frame_with_landmarks = self.hand_tracker.draw_note_boundaries(
                        frame_with_landmarks, num_notes, region_start, region_end
                    )
                self.ui.camera_frame_signal.emit(frame_with_landmarks)
            self.ui.update_audio_params(
                self.instrument.current_pitch, self.instrument.current_volume
            )
        else:
            # No valid hand data for too long: force note off
            self.instrument.update_from_vision({"hands": []})
            if frame is not None:
                self.ui.camera_frame_signal.emit(frame)

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
