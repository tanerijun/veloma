import os
import threading
import time
from typing import Any, Dict, Optional

import scamp as sc
from scamp_extensions.pitch import Scale

SCALES = {
    "major": Scale.major,  # first scale == default scale
    "aeolian": Scale.aeolian,
    "blues": Scale.blues,
    "chromatic": Scale.chromatic,
    "diatonic": Scale.diatonic,
    "dorian": Scale.dorian,
    "harmonic_minor": Scale.harmonic_minor,
    "ionian": Scale.ionian,
    "locrian": Scale.locrian,
    "lydian": Scale.lydian,
    "melodic_minor": Scale.melodic_minor,
    "mixolydian": Scale.mixolydian,
    "natural_minor": Scale.natural_minor,
    "octatonic": Scale.octatonic,
    "pentatonic": Scale.pentatonic,
    "pentatonic_minor": Scale.pentatonic_minor,
    "phrygian": Scale.phrygian,
    "whole_tone": Scale.whole_tone,
}

DEFAULT_GLIDE_MODE = False
PITCH_X_MARGIN = 0.01  # 1% margin on the right

INSTRUMENTS = [
    "Marimba",
    "Vibraphone",
    "Xylophone",
    "Glockenspiel",
    "Dulcimer",
    "Steel Drum",
    "Timpani Half",
    "Harp LP2",
    "Kalimba",
]

GLIDE_MODE_INSTRUMENT = "Sine Wave"


def get_scale_names():
    return list(SCALES.keys())


# Paths to sound fonts
current_dir = os.path.dirname(os.path.abspath(__file__))
soundFontPath_7777777 = os.path.join(current_dir, "soundFonts", "7777777.sf2")


class VelomaInstrument:
    """Virtual Theremin-like instrument using SCAMP with real-time parameter control."""

    def __init__(self):
        self.session = sc.Session()
        self.session.tempo = 120

        self.theremin = self.session.new_part(INSTRUMENTS[0])
        self.theremin.send_midi_cc(64, 0)  # Sustain pedal off

        self.current_pitch = 60  # Middle C
        self.current_volume = 0.5
        self.target_pitch = 60.0
        self.target_volume = 0.5

        self.current_notes = []  # hold all active notes
        self.num_amplified_notes = 3  # number of notes playing at the same time
        self.is_note_playing = False

        self.glide_mode = DEFAULT_GLIDE_MODE
        self.start_key = 60.0
        self.octave_range = 1

        self.scale_name = "major"
        self.pitch_pool = self._generate_pitch_pool(self.scale_name)

        self.pitch_range = (
            self.start_key,
            self.start_key + self.octave_range * 12,
        )  # 12 semitones per octave
        self.volume_range = (0.0, 1.0)

        # Smoothing parameters
        self.pitch_smoothing = 1
        self.volume_smoothing = 1

        # Threading
        self.audio_thread = None
        self.should_stop = False
        self.hands_detected = False
        self.min_volume_threshold = 0.3  # minimum volume to start / maintain note

        # Beginner mode
        self.note_played_recently = False
        self.note_play_cooldown = 0.2  # seconds
        self.last_note_time = 0
        self.last_note_index = None
        self.last_pitch_x = None
        self.right_hand_trigger = False

    def start_audio(self):
        """Start the audio processing thread."""
        if self.audio_thread and self.audio_thread.is_alive():
            return

        self.theremin.send_midi_cc(64, 0)
        self.should_stop = False
        self.audio_thread = threading.Thread(target=self._audio_loop)
        self.audio_thread.daemon = True
        self.audio_thread.start()

    def stop_audio(self):
        """Stop the audio processing."""
        self.should_stop = True
        self._stop_current_note()
        self.theremin.send_midi_cc(64, 0)

        if self.audio_thread:
            self.audio_thread.join(timeout=1.0)

    def update_from_vision(self, hand_data: Optional[Dict[str, Any]]):
        if not hand_data or not hand_data.get("hands"):
            self.hands_detected = False
            self.right_hand_trigger = False
            return

        hands = hand_data["hands"]
        self.hands_detected = True

        region_start = 0.5
        region_end = 1.0 - PITCH_X_MARGIN
        num_notes = len(self.pitch_pool)
        region_width = region_end - region_start
        block_width = region_width / num_notes

        if len(hands) >= 1:
            primary_hand = hands[0]
            pitch_x = primary_hand.get("rightmost_x", primary_hand["palm_center"][0])
            self.last_pitch_x = pitch_x

            self.right_hand_trigger = primary_hand.get("trigger_gesture", False)

            if self.glide_mode:
                self.target_pitch = self._map_range(
                    pitch_x, region_start, region_end, *self.pitch_range
                )
            else:
                x = max(region_start, min(region_end, pitch_x))
                mapped_index = int((x - region_start) / block_width)
                mapped_index = min(mapped_index, num_notes - 1)
                self.target_pitch = self.pitch_pool[mapped_index]

            self.target_volume = self._map_range(
                1.0 - primary_hand["palm_center"][1], 0.0, 0.5, *self.volume_range
            )

            if len(hands) >= 2:
                if hands[0]["palm_center"][0] > hands[1]["palm_center"][0]:
                    right_hand = hands[0]
                    left_hand = hands[1]
                else:
                    right_hand = hands[1]
                    left_hand = hands[0]

                pitch_x = right_hand.get("rightmost_x", right_hand["palm_center"][0])
                volume_y = left_hand["palm_center"][1]

                self.last_pitch_x = pitch_x
                self.right_hand_trigger = right_hand.get("trigger_gesture", False)

                if self.glide_mode:
                    self.target_pitch = self._map_range(
                        pitch_x, region_start, region_end, *self.pitch_range
                    )
                else:
                    x = max(region_start, min(region_end, pitch_x))
                    mapped_index = int((x - region_start) / block_width)
                    mapped_index = min(mapped_index, num_notes - 1)
                    self.target_pitch = self.pitch_pool[mapped_index]

                self.target_volume = self._map_range(
                    1.0 - volume_y, 0.0, 0.5, *self.volume_range
                )
        else:
            self.right_hand_trigger = False

    def _audio_loop(self):
        """Main audio processing loop with real-time parameter updates."""
        region_start = 0.5
        region_end = 1.0 - PITCH_X_MARGIN

        while not self.should_stop:
            # Smooth parameter transitions
            self.current_pitch = self._smooth_value(
                self.current_pitch, self.target_pitch, self.pitch_smoothing
            )
            self.current_volume = self._smooth_value(
                self.current_volume, self.target_volume, self.volume_smoothing
            )

            should_play = (
                self.hands_detected and self.current_volume > self.min_volume_threshold
            )

            if self.glide_mode:
                if should_play:
                    if not self.is_note_playing:
                        self._start_continuous_note()
                    else:
                        self._update_note_parameters()
                else:
                    if self.is_note_playing:
                        self._stop_current_note()
            else:
                # Beginner mode: discrete notes
                num_notes = len(self.pitch_pool)
                region_width = region_end - region_start
                block_width = region_width / num_notes

                pitch_x = self.last_pitch_x
                triggered = getattr(self, "right_hand_trigger", False)
                if should_play and pitch_x is not None:
                    if pitch_x < region_start:
                        # Hand is left of the pitch region: reset and do not play
                        self.last_note_index = None
                    else:
                        # Hand is inside the pitch region: map to note
                        x = max(region_start, min(region_end, pitch_x))
                        note_index = int((x - region_start) / block_width)
                        note_index = min(note_index, num_notes - 1)

                        now = time.time()
                        if (
                            note_index is not None
                            and (
                                self.last_note_index is None
                                or note_index != self.last_note_index
                                or (triggered and not self.last_trigger_state)
                            )
                            and now - self.last_note_time > self.note_play_cooldown
                        ):
                            self.theremin.play_note(
                                self.pitch_pool[note_index], self.current_volume, 0.4
                            )
                            self.last_note_time = now
                            self.last_note_index = note_index
                    self.last_trigger_state = triggered
                else:
                    self.last_note_index = None
                    self.last_trigger_state = False

            time.sleep(0.0001)

        self._stop_current_note()

    def _start_continuous_note(self):
        """Start a new continuous note."""
        self.current_notes = []
        for _ in range(self.num_amplified_notes):
            note = self.theremin.start_note(
                pitch=self.current_pitch, volume=self.current_volume
            )
            self.current_notes.append(note)

        self.is_note_playing = True

    def _update_note_parameters(self):
        """Update parameters of the currently playing note."""
        if self.current_notes and self.is_note_playing:
            try:
                for note in self.current_notes:
                    note.change_pitch(self.current_pitch)
                    note.change_volume(self.current_volume)
            except Exception as e:
                print(f"Error updating note parameters: {e}")
                self._stop_current_note()

    def _stop_current_note(self):
        """Stop the currently playing note."""
        if self.current_notes and self.is_note_playing:
            try:
                for note in self.current_notes:
                    note.end()
                self.current_notes = []
                self.is_note_playing = False
                self.theremin.send_midi_cc(64, 0)
                self.theremin.end_all_notes()
            except Exception as e:
                print(f"Error stopping note: {e}")
                self.current_notes = []
                self.is_note_playing = False
                self.theremin.end_all_notes()

    def set_scale(self, scale_name: str):
        if scale_name in SCALES:
            self.scale_name = scale_name
            self.pitch_pool = self._generate_pitch_pool(scale_name)

    def _generate_pitch_pool(self, scale_name: str) -> list:
        if scale_name == "chromatic":
            # All semitones in the range
            return [self.start_key + i for i in range(self.octave_range * 12 + 1)]
        else:
            pitch_pool = []
            max_pitch = self.start_key + self.octave_range * 12.0
            scale = SCALES[scale_name](self.start_key)

            i = 0
            while True:
                pitch = scale[i]

                if pitch > max_pitch:
                    break

                pitch_pool.append(pitch)
                i += 1

            return pitch_pool

    def set_instrument(self, instrument_name: str):
        self._stop_current_note()
        self.theremin.remove_soundfont_playback()

        if instrument_name == GLIDE_MODE_INSTRUMENT:
            self.theremin = self.session.new_part(
                instrument_name, soundfont=soundFontPath_7777777
            )
        else:
            self.theremin = self.session.new_part(instrument_name)

        self.theremin.send_midi_cc(64, 0)
        self.is_note_playing = False
        self.current_notes = []

    def update_pitch_range(self, start_key: float, octave_range: int):
        """Update the pitch range and regenerate pitch pool."""
        self.start_key = start_key
        self.octave_range = octave_range
        self.pitch_range = (start_key, start_key + octave_range * 12)
        # self.pitch_pool = self._generate_pitch_pool(self.scale_name)

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
    def _get_scale_index(current: float) -> int:
        return int(current)

    @staticmethod
    def _round_value(current: float) -> int:
        return int(current)
