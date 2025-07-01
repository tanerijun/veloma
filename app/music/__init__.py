import scamp as sc
import threading
from typing import Dict, Any, Optional
import math


class VelomaInstrument:
    """Virtual Theremin-like instrument using SCAMP."""

    def __init__(self):
        self.session = sc.Session()
        self.session.tempo = 120

        self.theremin = self.session.new_part("theremin")

        # Audio parameters
        self.current_pitch = 60  # Middle C
        self.current_volume = 0.5
        self.is_playing = False

        # Hand position mapping ranges
        self.pitch_range = (40, 80)  # MIDI note range
        self.volume_range = (0.0, 1.0)

        # Smoothing parameters
        self.pitch_smoothing = 0.1
        self.volume_smoothing = 0.1

        # Threading
        self.audio_thread = None
        self.should_stop = False
        self.note_duration = 0.3
        self.hands_detected = False

    def start_audio(self):
        """Start the audio processing thread."""
        if self.audio_thread and self.audio_thread.is_alive():
            return

        self.should_stop = False
        self.audio_thread = threading.Thread(target=self._audio_loop)
        self.audio_thread.daemon = True
        self.audio_thread.start()
        print("Audio engine started")

    def stop_audio(self):
        """Stop the audio processing."""
        self.should_stop = True
        if self.audio_thread:
            self.audio_thread.join(timeout=1.0)
        print("Audio engine stopped")

    def update_from_vision(self, hand_data: Optional[Dict[str, Any]]):
        """
        Update audio parameters based on hand tracking data.

        Args:
            hand_data: Dictionary containing hand position information
        """
        if not hand_data or not hand_data.get('hands'):
            # No hands detected - stop playing
            self.hands_detected = False
            self.is_playing = False
            return

        hands = hand_data['hands']
        self.hands_detected = True

        if len(hands) >= 1:
            # Use first hand for pitch control (vertical position)
            primary_hand = hands[0]
            palm_x, palm_y = primary_hand['palm_center']

            # Map Y position to pitch (inverted - higher position = higher pitch)
            target_pitch = self._map_range(1.0 - palm_y, 0.0, 1.0, *self.pitch_range)
            self.current_pitch = self._smooth_value(self.current_pitch, target_pitch, self.pitch_smoothing)

        if len(hands) >= 2:
            # Use second hand for volume control (distance from first hand)
            secondary_hand = hands[1]
            palm_x2, palm_y2 = secondary_hand['palm_center']
            primary_palm_x, primary_palm_y = hands[0]['palm_center']

            # Calculate distance between hands
            distance = math.sqrt((palm_x2 - primary_palm_x)**2 + (palm_y2 - primary_palm_y)**2)
            target_volume = self._map_range(distance, 0.0, 0.5, *self.volume_range)
            self.current_volume = self._smooth_value(self.current_volume, target_volume, self.volume_smoothing)
        else:
            # Single hand - use X position for volume
            palm_x, palm_y = hands[0]['palm_center']
            target_volume = self._map_range(palm_x, 0.0, 1.0, *self.volume_range)
            self.current_volume = self._smooth_value(self.current_volume, target_volume, self.volume_smoothing)

        if not self.is_playing:
            self.is_playing = True

    def _audio_loop(self):
        """Main audio processing loop."""
        print("Audio loop started")

        while not self.should_stop:
            if self.hands_detected and self.is_playing and self.current_volume > 0.01:
                self.theremin.play_note(
                    pitch=self.current_pitch,
                    volume=self.current_volume,
                    length=self.note_duration
                )

            # Sleep for a bit less than note duration to create overlapping notes
            sc.wait(self.note_duration * 0.7)

        print("Audio loop ended")

    @staticmethod
    def _map_range(value: float, in_min: float, in_max: float, out_min: float, out_max: float) -> float:
        """Map a value from one range to another."""
        # Clamp input value
        value = max(in_min, min(in_max, value))

        # Map to output range
        return out_min + (value - in_min) * (out_max - out_min) / (in_max - in_min)

    @staticmethod
    def _smooth_value(current: float, target: float, smoothing: float) -> float:
        """Apply smoothing to value changes."""
        return current + (target - current) * smoothing
