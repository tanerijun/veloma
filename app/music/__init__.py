import threading
import time
from typing import Any, Dict, Optional
import os
import scamp as sc
from scamp_extensions.pitch import Scale

SCALES = {
    "major": Scale.major, # first scale == default scale
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

def get_scale_names():
    return list(SCALES.keys())

# Paths to sound fonts
current_dir = os.path.dirname(os.path.abspath(__file__))
soundFontPath_theremin_high = os.path.join(current_dir, "soundFonts", "theremin_high.sf2")
soundFontPath_theremin_trill = os.path.join(current_dir, "soundFonts", "theremin_trill.sf2")
soundFontPath_7777777 = os.path.join(current_dir, "soundFonts", "7777777.sf2")

class VelomaInstrument:
    """Virtual Theremin-like instrument using SCAMP with real-time parameter control."""

    def __init__(self):
        self.pc = 0

        self.session = sc.Session()
        self.session = sc.Session(default_soundfont=soundFontPath_7777777)
        # self.session = sc.Session(default_soundfont=soundFontPath_theremin_high)
        # self.session = sc.Session(default_soundfont="theremin_high.sf2")
        # self.session = sc.Session(default_soundfont=soundFontPath_theremin_trill)

        self.session.tempo = 120

        # self.theremin = self.session.new_part("Sine Wave")
        self.theremin = self.session.new_part("Theremin")
        self.theremin.send_midi_cc(64, 0)  # Sustain pedal off

        # Audio parameters
        self.current_pitch = 60  # Middle C
        self.current_volume = 0.5
        self.target_pitch = 60.0
        self.target_volume = 0.5

        self.current_notes = [] # hold all active notes
        self.num_amplified_notes = 3 # number of notes playing at the same time
        self.is_note_playing = False

        # Hand position mapping ranges
        self.glide_mode=DEFAULT_GLIDE_MODE
        self.start_key = 60.0
        self.octave_range = 2

        self.scale_name = "major"
        self.pitch_pool = self._generate_pitch_pool(self.scale_name)

        self.pitch_range = (self.start_key, self.start_key + self.octave_range * 12) # 12 semitones per octave
        self.volume_range = (0.0, 1.0)

        self.gesture_list= {
            "arpeggio":[0,2,4,2,0],
            "greeting":[1,2,1,2,1,2,0],
            "greeting_arc":[1,2,1,2,1,2,0.5],
            "haha":[1,1,1,1,1,1,1],
            "haha_arc":[1,1,-0.5,1,-0.5,1,1],
            "down":[4,3,2,1],
            "down_arc":[4,2,3,1],
            "up":[1,2,3,4],
            "up_arc":[1,3,2,4],
            "nonesence":[7,3,1,7],
            "nonesence":[7,3,1,7],
            "arpeggio_arc":[0,3,5,3,0],
            "arpeggio2":[0,2,4,2,4,2],
            "arpeggio2_arc":[0,3,5,3,5,3],
            "bridge":[0,7,1.5,0.5],
            "bridge_arc":[0,7,1,0],
            "ending":[8.5,6,5,4,4.5,4,2.5,4,5,5.5],
            "ending_arc":[8,7,5,4,5,2,4,5,4,5],
            "ending2":[5,5,5,5,1,1],
            "ending3":[3,3,3,2,2],
            "final":[0]
        }

        # Smoothing parameters - much higher for real-time response
        self.pitch_smoothing = 1
        self.volume_smoothing = 1

        # Threading
        self.audio_thread = None
        self.should_stop = False
        self.hands_detected = False
        self.min_volume_threshold = 0.3  # Minimum volume to start / maintain note

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

        self.pc += 1
        if self.pc > 37:
            self.pc = 0
            print("index finger:",
            f"({hands[0]['landmarks'][5]['x']:.3f}, {hands[0]['landmarks'][5]['y']:.3f}, {hands[0]['landmarks'][5]['z']:.3f})",
            f"({hands[0]['landmarks'][6]['x']:.3f}, {hands[0]['landmarks'][6]['y']:.3f}, {hands[0]['landmarks'][6]['z']:.3f})",
            f"({hands[0]['landmarks'][7]['x']:.3f}, {hands[0]['landmarks'][7]['y']:.3f}, {hands[0]['landmarks'][7]['z']:.3f})",
            f"({hands[0]['landmarks'][8]['x']:.3f}, {hands[0]['landmarks'][8]['y']:.3f}, {hands[0]['landmarks'][8]['z']:.3f})",)
            print("middle finger:",
            f"({hands[0]['landmarks'][9]['x']:.3f}, {hands[0]['landmarks'][9]['y']:.3f}, {hands[0]['landmarks'][9]['z']:.3f})",
            f"({hands[0]['landmarks'][10]['x']:.3f}, {hands[0]['landmarks'][10]['y']:.3f}, {hands[0]['landmarks'][10]['z']:.3f})",
            f"({hands[0]['landmarks'][11]['x']:.3f}, {hands[0]['landmarks'][11]['y']:.3f}, {hands[0]['landmarks'][11]['z']:.3f})",
            f"({hands[0]['landmarks'][12]['x']:.3f}, {hands[0]['landmarks'][12]['y']:.3f}, {hands[0]['landmarks'][12]['z']:.3f})\n",)

            index_tip_x = hands[0]['landmarks'][8]['x']
            middle_tip_x = hands[0]['landmarks'][12]['x']
            index_base_x = hands[0]['landmarks'][5]['x']
            middle_base_x = hands[0]['landmarks'][9]['x']
            # 假設以 x 軸為判斷基準（左右交錯）
            index_left_of_middle = index_tip_x < middle_tip_x
            base_left_of_middle = index_base_x < middle_base_x
            # 若 tip 和 base 的左右關係不同，代表交叉
            crossed = (index_left_of_middle != base_left_of_middle)
            if crossed:
                print("食指與中指交叉！")
                sc.fork(self.play_gesture)
                # for i in range(len(self.gesture_list['arpeggio'])):
                #     self.theremin.play_note(self.scale[self.gesture_list['arpeggio'][i]],
                #         self.current_volume,
                #         1,
                #         blocking=False
                #         )
                #     sc.wait(1)
            # else:
            #     self.theremin.end_all_notes()
        if len(hands) >= 1:
            # Use first hand for pitch control (vertical position)
            primary_hand = hands[0]
            palm_x, palm_y = primary_hand["palm_center"]

            if self.glide_mode:
                # pitch_x_clamped = max(0.5, min(1.0, palm_x))
                self.target_pitch = self._map_range(
                    palm_x, 0.5, 1.0, *self.pitch_range
                )
            else:
                mapped_index_float = self._map_range(palm_x, 0.5, 1.0, 0, len(self.pitch_pool) - 1 )
                mapped_index = int(round(mapped_index_float))
                self.target_pitch=self.pitch_pool[mapped_index]

            # volume_y_clamped = max(0.5, min(1.0, palm_y))
            self.target_volume = self._map_range(
                1.0 - palm_y, 0.0, 0.5, *self.volume_range
            )

            if len(hands) >= 2:
                if hands[0]["palm_center"][0] > hands[1]["palm_center"][0]:
                    right_hand = hands[0]
                    left_hand = hands[1]
                else:
                    right_hand = hands[1]
                    left_hand = hands[0]


                pitch_x = right_hand["palm_center"][0]
                if self.glide_mode:
                    # 音高：右手（看 x）

                    # 0.5~1
                    # pitch_x_clamped = max(0.5, min(1.0, pitch_x))
                    self.target_pitch = self._map_range(
                        pitch_x, 0.5, 1.0, *self.pitch_range
                    )
                else:
                    mapped_index_float = self._map_range(pitch_x, 0.5, 1.0, 0, len(self.pitch_pool) - 1 )
                    mapped_index = int(round(mapped_index_float))
                    self.target_pitch=self.pitch_pool[mapped_index]

                # 音量：左手
                volume_y = left_hand["palm_center"][1]
                # volume_y_clamped = max(0.5, min(1.0, volume_y))
                # 因為越上面音量越大
                self.target_volume = self._map_range(
                    1.0 - volume_y, 0.0, 0.5, *self.volume_range
                )

    def _audio_loop(self):
        """Main audio processing loop with real-time parameter updates."""
        print("Audio loop started")

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

            if should_play:
                if not self.is_note_playing:
                    self._start_continuous_note()
                else:
                    self._update_note_parameters()
            else:
                if self.is_note_playing:
                    self._stop_current_note()

            time.sleep(0.0001)

        self._stop_current_note()
        print("Audio loop ended")

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
            except Exception as e:
                print(f"Error stopping note: {e}")
                self.current_notes = []
                self.is_note_playing = False
                self.theremin.end_all_notes()

    def set_scale(self, scale_name: str):
        if scale_name in SCALES:
            self.scale_name = scale_name
            self.pitch_pool = self._generate_pitch_pool(scale_name)

    def play_gesture(self, gesture_name: str = "arpeggio"):
        for i in range(len(self.gesture_list['arpeggio'])):
            self.theremin.play_note(self.gesture_list[gesture_name][i], self.current_volume, 1, blocking=False)
            sc.wait(1)

        self.theremin.end_all_notes()

    def _generate_pitch_pool(self, scale_name: str) -> list:
        if scale_name == "chromatic":
            # All semitones in the range
            return [self.start_key + i for i in range(self.octave_range * 12 + 1)]
        else:
            # Use the scale generator
            return [pitch for pitch in SCALES[scale_name](self.start_key)
                    if pitch <= self.start_key + self.octave_range * 12.0]

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
