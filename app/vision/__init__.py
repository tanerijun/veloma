import threading
import time
from typing import Any, Dict, Tuple

import cv2
import numpy as np
from mediapipe import Image as MPImage
from mediapipe import ImageFormat as MPImageFormat
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python.vision import (
    HandLandmarker,
    HandLandmarkerOptions,
    RunningMode,
)

HAND_CONNECTIONS = [
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),  # Thumb
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),  # Index
    (0, 9),
    (9, 10),
    (10, 11),
    (11, 12),  # Middle
    (0, 13),
    (13, 14),
    (14, 15),
    (15, 16),  # Ring
    (0, 17),
    (17, 18),
    (18, 19),
    (19, 20),  # Pinky
]
FINGER_TIPS = [4, 8, 12, 16, 20]


class HandTracker:
    def __init__(self, model_path="app/vision/hand_landmarker.task"):
        self.cap = None
        self.is_running = False
        self._thread = None
        self._async_stop = False
        self._on_hand_data = None

        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=RunningMode.LIVE_STREAM,
            result_callback=self._result_callback,
            num_hands=2,
        )
        self.hand_landmarker = HandLandmarker.create_from_options(options)

    def start_camera(self) -> bool:
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                return False
            self.is_running = True
            return True
        except Exception as e:
            print(f"Failed to start camera: {e}")
            return False

    def stop_camera(self):
        self.is_running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        if self.hand_landmarker:
            self.hand_landmarker.close()

    def start_async(self, on_hand_data):
        if self._thread and self._thread.is_alive():
            return
        self._async_stop = False
        self._on_hand_data = on_hand_data
        self._thread = threading.Thread(target=self._async_loop)
        self._thread.daemon = True
        self._thread.start()

    def stop_async(self):
        self._async_stop = True
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _async_loop(self):
        while not self._async_stop:
            if not self.cap or not self.is_running:
                time.sleep(0.01)
                continue
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue
            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            timestamp_ms = int(time.time() * 1000)
            # Store frame for callback
            self._latest_frame = frame
            mp_image = MPImage(image_format=MPImageFormat.SRGB, data=rgb_frame)
            self.hand_landmarker.detect_async(mp_image, timestamp_ms)
            time.sleep(0.01)

    def _result_callback(self, result, output_image, timestamp_ms):
        hand_data = {
            "frame": getattr(self, "_latest_frame", None),
            "hands": [],
            "timestamp": timestamp_ms,
        }
        if result and result.hand_landmarks:
            for idx, landmarks in enumerate(result.hand_landmarks):
                landmark_list = []
                for landmark in landmarks:
                    landmark_list.append(
                        {"x": landmark.x, "y": landmark.y, "z": landmark.z}
                    )
                palm_center = self._calculate_palm_center(landmark_list)
                rightmost_x = max(lm["x"] for lm in landmark_list)
                hand_info = {
                    "landmarks": landmark_list,
                    "palm_center": palm_center,
                    "rightmost_x": rightmost_x,
                    "hand_index": idx,
                }
                hand_info["trigger_gesture"] = self.is_fingertip_near_palm(hand_info)
                hand_data["hands"].append(hand_info)
        if self._on_hand_data:
            self._on_hand_data(hand_data)

    def _calculate_palm_center(self, landmarks) -> Tuple[float, float]:
        wrist = landmarks[0]
        middle_mcp = landmarks[9]
        center_x = (wrist["x"] + middle_mcp["x"]) / 2
        center_y = (wrist["y"] + middle_mcp["y"]) / 2
        return (center_x, center_y)

    def draw_landmarks(self, frame, hand_data: Dict[str, Any]) -> np.ndarray:
        return frame  # don't draw landmarks for now
        # if not hand_data or not hand_data["hands"]:
        #     return frame

        # h, w, _ = frame.shape
        # overlay = frame.copy()

        # for hand_info in hand_data["hands"]:
        #     landmarks = hand_info["landmarks"]

        #     # Draw connections on overlay
        #     for start_idx, end_idx in HAND_CONNECTIONS:
        #         x1 = int(landmarks[start_idx]["x"] * w)
        #         y1 = int(landmarks[start_idx]["y"] * h)
        #         x2 = int(landmarks[end_idx]["x"] * w)
        #         y2 = int(landmarks[end_idx]["y"] * h)
        #         cv2.line(overlay, (x1, y1), (x2, y2), (0, 255, 255), 2, cv2.LINE_AA)

        #     # Draw landmarks
        #     for idx, landmark in enumerate(landmarks):
        #         x = int(landmark["x"] * w)
        #         y = int(landmark["y"] * h)
        #         if idx in FINGER_TIPS:
        #             color = (0, 128, 255)  # orange for fingertips
        #             radius = 7
        #         else:
        #             color = (0, 255, 0)  # green for joints
        #             radius = 5
        #         cv2.circle(overlay, (x, y), radius, color, -1, cv2.LINE_AA)

        #     # Draw palm center
        #     palm_x, palm_y = hand_info["palm_center"]
        #     palm_pixel_x = int(palm_x * w)
        #     palm_pixel_y = int(palm_y * h)
        #     cv2.circle(
        #         overlay, (palm_pixel_x, palm_pixel_y), 10, (255, 0, 0), -1, cv2.LINE_AA
        #     )

        # # Blend overlay for transparency
        # cv2.addWeighted(overlay, 0.4, frame, 0.6, 0, frame)
        # return frame

    def draw_note_boundaries(
        self, frame, num_notes, region_start=0.5, region_end=0.9, color=(255, 255, 255)
    ):
        h, w, _ = frame.shape
        region_width = region_end - region_start
        block_width = region_width / num_notes
        for i in range(num_notes + 1):
            x_norm = region_start + i * block_width
            x_px = int(x_norm * w)
            cv2.line(frame, (x_px, 0), (x_px, h), color, 2)
        return frame

    def is_fingertip_near_palm(self, hand_info, threshold=0.08):
        # Returns True if any fingertip is close to palm center
        palm_x, palm_y = hand_info["palm_center"]
        for tip_idx in [4, 8, 12, 16, 20]:
            tip = hand_info["landmarks"][tip_idx]
            dist = ((tip["x"] - palm_x) ** 2 + (tip["y"] - palm_y) ** 2) ** 0.5
            if dist < threshold:
                return True
        return False
