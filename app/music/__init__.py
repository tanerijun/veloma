import math
import threading
import time
from typing import Any, Dict, Optional

import scamp as sc


class VelomaInstrument:
    """Virtual Theremin-like instrument using SCAMP with real-time parameter control."""

    def __init__(self):
        self.session = sc.Session()
        self.session.tempo = 120

        self.theremin = self.session.new_part("theremin")
        self.theremin.send_midi_cc(64, 0)  # Sustain pedal off

        # Audio parameters
        self.current_pitch = 60  # Middle C
        self.current_volume = 0.5
        self.target_pitch = 60
        self.target_volume = 0.5

        # Note control
        self.current_note = None
        # for amplification
        self.current_note_amplify = None
        self.current_note_amplify2 = None
        self.is_note_playing = False

        # Hand position mapping ranges
        self.pitch_range = (59, 73)
        self.volume_range = (0.0, 1.0)

        # Smoothing parameters - much higher for real-time response
        self.pitch_smoothing = 0.9  # Faster pitch response
        self.volume_smoothing = 1  # Faster volume response

        # Threading
        self.audio_thread = None
        self.should_stop = False
        self.hands_detected = False
        self.min_volume_threshold = 0.5  # Minimum volume to start/maintain note

    def start_audio(self):
        """Start the audio processing thread."""
        if self.audio_thread and self.audio_thread.is_alive():
            return

        self.theremin.send_midi_cc(64, 0)
        self.should_stop = False
        self.audio_thread = threading.Thread(target=self._audio_loop)
        self.audio_thread.daemon = True
        self.audio_thread.start()
        print("Audio engine started")

    def stop_audio(self):
        """Stop the audio processing."""
        self.should_stop = True
        self._stop_current_note()
        self.theremin.send_midi_cc(64, 0)

        if self.audio_thread:
            self.audio_thread.join(timeout=1.0)
        print("Audio engine stopped")

    def update_from_vision(self, hand_data: Optional[Dict[str, Any]]):
        """
        Update audio parameters based on hand tracking data.
        Args:
            hand_data: Dictionary containing hand position information
        """
        if not hand_data or not hand_data.get("hands"):
            # No hands detected - prepare to stop playing
            self.hands_detected = False
            return

        hands = hand_data["hands"]
        self.hands_detected = True
        
        if len(hands) >= 1:
            # Use first hand for pitch control (vertical position)
            primary_hand = hands[0]
            palm_x, palm_y = primary_hand["palm_center"]

            pitch_x_clamped = max(0.5, min(1.0, palm_x))
            self.target_pitch = self._map_range(
                pitch_x_clamped, 0.5, 1.0, *self.pitch_range
            )
            
            volume_y_clamped = max(0.5, min(1.0, palm_y))
            self.target_volume = self._map_range(
                1.0 - volume_y_clamped, 0.0, 0.5, *self.volume_range
            )
            # if len(hands) >= 2:
            #     # Use distance between hands for volume control
            #     secondary_hand = hands[1]
            #     palm_x2, palm_y2 = secondary_hand["palm_center"]
            #     primary_palm_x, primary_palm_y = hands[0]["palm_center"]

            #     # Calculate distance between hands
            #     distance = math.sqrt(
            #         (palm_x2 - primary_palm_x) ** 2 + (palm_y2 - primary_palm_y) ** 2
            #     )
            #     self.target_volume = self._map_range(
            #         distance, 0.0, 0.5, *self.volume_range
            #     )
            if len(hands) >= 2:
                if hands[0]["palm_center"][0] > hands[1]["palm_center"][0]:
                    right_hand = hands[0]
                    left_hand = hands[1]
                else:
                    right_hand = hands[1]
                    left_hand = hands[0]

                
                # 音高：右手（看 x）
                pitch_x = right_hand["palm_center"][0]
                # 0.5~1
                pitch_x_clamped = max(0.5, min(1.0, pitch_x))
                self.target_pitch = self._map_range(
                    pitch_x_clamped, 0.5, 1.0, *self.pitch_range
                )
                

                # 音量：左手
                volume_y = left_hand["palm_center"][1]
                volume_y_clamped = max(0.5, min(1.0, volume_y))
                # 因為越上面音量越大
                self.target_volume = self._map_range(
                    1.0 - volume_y_clamped, 0.0, 0.5, *self.volume_range
                )

    def _audio_loop(self):
        """Main audio processing loop with real-time parameter updates."""
        print("Real-time audio loop started")

        while not self.should_stop:
            # Smooth parameter transitions
            self.current_pitch = self._smooth_value(
                self.current_pitch, self.target_pitch, self.pitch_smoothing
            )
            self.current_volume = self._smooth_value(
                self.current_volume, self.target_volume, self.volume_smoothing
            )

            # Decide whether to play, update, or stop note
            should_play = (
                self.hands_detected and self.current_volume > self.min_volume_threshold
            )

            if should_play:
                if not self.is_note_playing:
                    # Start new continuous note
                    self._start_continuous_note()
                else:
                    # Update existing note parameters
                    self._update_note_parameters()
            else:
                if self.is_note_playing:
                    # Stop current note
                    self._stop_current_note()

            # ~1000 Hz update rate
            time.sleep(0.001)

        # Ensure note is stopped when loop exits
        self._stop_current_note()
        print("Real-time audio loop ended")

    def _start_continuous_note(self):
        """Start a new continuous note."""
        try:
            self.theremin.send_midi_cc(64, 1)

            self.current_note = self.theremin.start_note(
                pitch=self.current_pitch, volume=1
            )
            self.current_note_amplify = self.theremin.start_note(
                pitch=self.current_pitch, volume=1
            )
            self.current_note_amplify2 = self.theremin.start_note(
                pitch=self.current_pitch, volume=1
            )
            self.is_note_playing = True
            print(
                f"Started note: pitch={self.current_pitch:.1f}, volume={self.current_volume:.2f}"
            )

        except Exception as e:
            print(f"Error starting note: {e}")
            self.is_note_playing = False

    def _update_note_parameters(self):
        """Update parameters of the currently playing note."""
        if self.current_note and self.is_note_playing:
            try:
                
                self.current_note.change_pitch(self.current_pitch)
                self.current_note.change_volume(1)
                self.current_note_amplify.change_pitch(self.current_pitch)
                self.current_note_amplify.change_volume(1)
                self.current_note_amplify2.change_pitch(self.current_pitch)
                self.current_note_amplify2.change_volume(1)
            except Exception as e:
                print(f"Error updating note parameters: {e}")
                self._stop_current_note()

    def _stop_current_note(self):
        """Stop the currently playing note."""
        if self.current_note and self.is_note_playing:
            try:
                self.current_note.end()
                self.current_note = None
                self.current_note_amplify.end()
                self.current_note_amplify = None
                self.current_note_amplify2.end()
                self.current_note_amplify2 = None
                self.is_note_playing = False
                self.theremin.send_midi_cc(64, 0)
                print("Note stopped")

            except Exception as e:
                print(f"Error stopping note: {e}")
                # Force cleanup
                self.current_note = None
                self.is_note_playing = False
                self.theremin.end_all_notes()

    @staticmethod
    def _map_range(
        value: float, in_min: float, in_max: float, out_min: float, out_max: float
    ) -> float:
        """Map a value from one range to another."""
        # Clamp input value
        value = max(in_min, min(in_max, value))

        # Map to output range
        return out_min + (value - in_min) * (out_max - out_min) / (in_max - in_min)

    @staticmethod
    def _smooth_value(current: float, target: float, smoothing: float) -> float:
        """Apply smoothing to value changes."""
        return current + (target - current) * smoothing



    @staticmethod
    def _round_value(current: float) -> int:
        return int(current)
