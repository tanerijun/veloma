import cv2
import mediapipe as mp
import numpy as np
from typing import Optional, Tuple, Dict, Any


class HandTracker:
    """Hand tracking using MediaPipe."""

    def __init__(self):
        self.mp_hands = mp.solutions.hands # type: ignore
        self.mp_drawing = mp.solutions.drawing_utils # type: ignore
        print(self.mp_hands)
        print(self.mp_drawing)
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.cap = None
        self.is_running = False

    def start_camera(self) -> bool:
        """Start the camera capture."""
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
        """Stop the camera capture."""
        self.is_running = False
        if self.cap:
            self.cap.release()
            self.cap = None

    def get_hand_positions(self) -> Optional[Dict[str, Any]]:
        """
        Get current hand positions from camera.
        Returns dict with hand position data or None if no hands detected.
        """
        if not self.cap or not self.is_running:
            print("WARN: Camera not available or not running")
            return None

        ret, frame = self.cap.read()
        if not ret:
            print("WARN: Failed to read frame from camera")
            return None

        # Flip frame horizontally for mirror effect
        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        results = self.hands.process(rgb_frame)

        hand_data = {
            'frame': frame,
            'hands': [],
            'timestamp': cv2.getTickCount()
        }

        if results.multi_hand_landmarks:
            for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                landmarks = []
                for landmark in hand_landmarks.landmark:
                    landmarks.append({
                        'x': landmark.x,
                        'y': landmark.y,
                        'z': landmark.z
                    })

                palm_center = self._calculate_palm_center(landmarks)

                hand_info = {
                    'landmarks': landmarks,
                    'palm_center': palm_center,
                    'hand_index': idx
                }

                hand_data['hands'].append(hand_info)

        return hand_data

    def _calculate_palm_center(self, landmarks) -> Tuple[float, float]:
        """Calculate approximate palm center from landmarks."""
        # Use wrist and middle finger MCP joint as reference points
        wrist = landmarks[0]  # Wrist
        middle_mcp = landmarks[9]  # Middle finger MCP joint

        center_x = (wrist['x'] + middle_mcp['x']) / 2
        center_y = (wrist['y'] + middle_mcp['y']) / 2

        return (center_x, center_y)

    def draw_landmarks(self, frame, hand_data: Dict[str, Any]) -> np.ndarray:
        """Draw hand landmarks on frame for visualization."""
        if not hand_data or not hand_data['hands']:
            return frame

        for hand_info in hand_data['hands']:
            # Convert normalized coordinates to pixel coordinates
            h, w, _ = frame.shape
            landmarks = hand_info['landmarks']

            # Draw landmarks
            for i, landmark in enumerate(landmarks):
                x = int(landmark['x'] * w)
                y = int(landmark['y'] * h)

                if i == 0:
                    color = (0, 255, 255)  # 掌根 - 黃色
                elif 5 <= i <= 8:
                    color = (255, 0, 0)    # 食指 - 藍色
                else:
                    color = (0, 255, 0)    # 其他 - 綠色

                cv2.circle(frame, (x, y), 5, color, -1)

            # Draw palm center
            palm_x, palm_y = hand_info['palm_center']
            palm_pixel_x = int(palm_x * w)
            palm_pixel_y = int(palm_y * h)
            cv2.circle(frame, (palm_pixel_x, palm_pixel_y), 10, (255, 0, 0), -1)

        return frame
