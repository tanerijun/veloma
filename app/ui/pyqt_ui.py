from typing import Callable, Optional

import cv2
import numpy as np
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QCursor, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from app.music import DEFAULT_GLIDE_MODE, INSTRUMENTS, get_scale_names


class VelomaUI(QMainWindow):
    camera_frame_signal = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.is_running = False
        self.window_width = 1400
        self.window_height = 900
        self.camera_width = 800
        self.camera_height = 600

        # Callbacks
        self.on_start_callback = None
        self.on_stop_callback = None
        self.on_settings_change_callback = None

        # UI state
        self.current_pitch = 60.0
        self.current_volume = 0.0
        self.hands_detected = 0
        self.frame_count = 0

        # UI elements
        self.camera_label: Optional[QLabel] = None
        self.camera_status_label: Optional[QLabel] = None
        self.pitch_slider: Optional[QSlider] = None
        self.volume_slider: Optional[QSlider] = None
        self.smoothing_slider: Optional[QSlider] = None
        self.pitch_value_label: Optional[QLabel] = None
        self.volume_value_label: Optional[QLabel] = None
        self.smoothing_value_label: Optional[QLabel] = None

        self.camera_frame_signal.connect(self.update_camera_frame)

        self.setup()

    def setup(self):
        """Setup the main window and UI components."""
        self.setWindowTitle("Veloma - Virtual Theremin")
        self.setGeometry(100, 100, self.window_width, self.window_height)
        self.setMinimumSize(1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self._create_toolbar(main_layout)
        self._create_camera_panel(main_layout)
        main_layout.setStretch(1, 1)  # camera preview takes remaining space

    def _create_toolbar(self, parent_layout):
        """Create a horizontal toolbar with controls and help."""
        toolbar = QHBoxLayout()

        # Start Key
        toolbar.addWidget(QLabel("Start Key:"))
        self.start_key_slider = QSlider(Qt.Orientation.Horizontal)
        self.start_key_slider.setRange(20, 80)
        self.start_key_slider.setValue(60)
        self.start_key_slider.setFixedWidth(120)
        self.start_key_slider.valueChanged.connect(self._on_settings_changed)
        self.start_key_value_label = QLabel("60")
        toolbar.addWidget(self.start_key_slider)
        toolbar.addWidget(self.start_key_value_label)
        toolbar.addItem(
            QSpacerItem(20, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        )

        # Octave Range
        toolbar.addWidget(QLabel("Octave Range:"))
        self.octave_range_slider = QSlider(Qt.Orientation.Horizontal)
        self.octave_range_slider.setRange(1, 5)
        self.octave_range_slider.setValue(1)
        self.octave_range_slider.setFixedWidth(80)
        self.octave_range_slider.valueChanged.connect(self._on_settings_changed)
        self.octave_range_value_label = QLabel("1")
        toolbar.addWidget(self.octave_range_slider)
        toolbar.addWidget(self.octave_range_value_label)
        toolbar.addItem(
            QSpacerItem(20, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        )

        # Instrument
        toolbar.addWidget(QLabel("Instrument:"))
        self.instrument_combo = QComboBox()
        self.instrument_combo.addItems(INSTRUMENTS)
        self.instrument_combo.setCurrentText(INSTRUMENTS[0])
        self.instrument_combo.currentTextChanged.connect(self._on_settings_changed)
        toolbar.addWidget(self.instrument_combo)
        toolbar.addItem(
            QSpacerItem(10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        )

        # Scale
        toolbar.addWidget(QLabel("Scale:"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(get_scale_names())
        self.scale_combo.setCurrentText(get_scale_names()[0])
        self.scale_combo.currentTextChanged.connect(self._on_settings_changed)
        toolbar.addWidget(self.scale_combo)
        toolbar.addItem(
            QSpacerItem(10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        )

        # Glide mode
        self.glide_checkbox = QCheckBox("Theremin Mode")
        self.glide_checkbox.setChecked(DEFAULT_GLIDE_MODE)
        self.glide_checkbox.stateChanged.connect(self._on_settings_changed)
        toolbar.addWidget(self.glide_checkbox)
        toolbar.addItem(
            QSpacerItem(10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        )

        # Show guidelines
        self.show_boundaries_checkbox = QCheckBox("Show Guide")
        self.show_boundaries_checkbox.setChecked(True)
        self.show_boundaries_checkbox.stateChanged.connect(self._on_settings_changed)
        toolbar.addWidget(self.show_boundaries_checkbox)
        toolbar.addItem(
            QSpacerItem(10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        )

        # Spacer
        toolbar.addStretch()

        # Help icon button
        help_btn = QPushButton("❔")
        help_btn.setFixedSize(32, 32)
        help_btn.setToolTip("Show Instructions")
        help_btn.clicked.connect(self._show_help_modal)
        help_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        toolbar.addWidget(help_btn)

        # Exit button
        exit_button = QPushButton("Exit")
        exit_button.setFixedSize(80, 32)
        exit_button.clicked.connect(self._on_exit_clicked)
        exit_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                border-radius: 12px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #ffa733;
            }
        """)
        exit_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        toolbar.addWidget(exit_button)

        parent_layout.addLayout(toolbar)

    def _create_camera_panel(self, parent_layout):
        """Create camera preview panel (fills below toolbar)."""
        camera_layout = QVBoxLayout()
        self.camera_label = QLabel()
        self.camera_label.setMinimumSize(self.camera_width, self.camera_height)
        self.camera_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.camera_label.setStyleSheet(
            "border: 2px solid #ccc; background-color: #000;"
        )
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        camera_layout.addWidget(self.camera_label)

        # pitch/volume display at the bottom
        info_layout = QHBoxLayout()
        info_layout.addStretch()
        info_layout.addWidget(QLabel("Pitch:"))
        self.pitch_value_label = QLabel("60.0")
        info_layout.addWidget(self.pitch_value_label)
        info_layout.addSpacing(20)
        info_layout.addWidget(QLabel("Volume:"))
        self.volume_value_label = QLabel("0.0")
        info_layout.addWidget(self.volume_value_label)
        info_layout.addStretch()
        camera_layout.addLayout(info_layout)

        camera_layout.addStretch()
        parent_layout.addLayout(camera_layout)

    def _show_help_modal(self):
        from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout

        dialog = QDialog(self)
        dialog.setWindowTitle("Instructions")
        dialog.setFixedWidth(400)
        layout = QVBoxLayout(dialog)

        instructions = [
            "<b>Single-hand mode:</b>",
            "• Move your hand left/right to control pitch",
            "• Move your hand up/down to control volume",
            "<b>Dual-hand mode:</b>",
            "• Move right hand left/right to control pitch",
            "• Move left hand up/down to control volume",
        ]
        for line in instructions:
            label = QLabel(line)
            label.setWordWrap(True)
            layout.addWidget(label)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.setLayout(layout)
        dialog.exec()

    def _display_image(self, image):
        """Display an image in the camera label."""
        try:
            height, width, channel = image.shape
            bytes_per_line = 3 * width
            q_image = QImage(
                image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888
            )
            pixmap = QPixmap.fromImage(q_image)
            if self.camera_label:
                label_width = self.camera_label.width()
                label_height = self.camera_label.height()
                scaled_pixmap = pixmap.scaled(
                    label_width,
                    label_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.camera_label.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"Error displaying image: {e}")
            self._show_error_pattern()

    def _show_error_pattern(self):
        """Show error pattern when image display fails."""
        error_image = np.zeros(
            (self.camera_height, self.camera_width, 3), dtype=np.uint8
        )
        error_image[:, :] = [255, 0, 0]  # Red background

        # Add error stripes
        for y in range(100, 150):
            for x in range(100, 400):
                if (x + y) % 4 == 0:
                    error_image[y, x] = [255, 255, 255]  # White stripes

        self._display_image(error_image)

    def start_application(self):
        if self.on_start_callback:
            try:
                result = self.on_start_callback()
                print(f"Auto-start result: {result}")
            except Exception as e:
                print(f"Auto-start failed: {e}")

    def _on_exit_clicked(self):
        """Handle exit button click."""
        self.stop()

    def _on_settings_changed(self):
        """Handle settings slider changes."""
        # Update slider value labels
        if self.start_key_value_label and self.start_key_slider:
            self.start_key_value_label.setText(f"{self.start_key_slider.value()}")
        if self.octave_range_value_label and self.octave_range_slider:
            self.octave_range_value_label.setText(f"{self.octave_range_slider.value()}")

        if (
            self.on_settings_change_callback
            and self.start_key_slider
            and self.octave_range_slider
            and self.scale_combo
            and self.glide_checkbox
        ):
            settings = {
                "start_key": int(self.start_key_slider.value()),
                "octave_range": int(self.octave_range_slider.value()),
                "instrument": self.instrument_combo.currentText(),
                "scale": self.scale_combo.currentText(),
                "glide_mode": self.glide_checkbox.isChecked(),
                "show_note_boundaries": self.show_boundaries_checkbox.isChecked(),
            }
            self.on_settings_change_callback(settings)

        self.octave_range_slider.setEnabled(not self.glide_checkbox.isChecked())
        self.scale_combo.setEnabled(not self.glide_checkbox.isChecked())
        self.instrument_combo.setEnabled(not self.glide_checkbox.isChecked())

    def update_camera_frame(self, frame: Optional[np.ndarray]):
        """Update the camera preview with new frame."""
        if frame is None:
            return

        try:
            # Convert BGR to RGB (OpenCV uses BGR by default)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self._display_image(rgb_frame)
        except Exception as e:
            print(f"Camera frame update error: {e}")
            self._show_error_pattern()

    def update_audio_params(self, pitch: float, volume: float):
        """Update audio parameter displays."""
        self.current_pitch = pitch
        self.current_volume = volume

        if self.pitch_slider:
            self.pitch_slider.setValue(int(pitch))
        if self.pitch_value_label:
            self.pitch_value_label.setText(f"{pitch:.2f}")

        if self.volume_slider:
            self.volume_slider.setValue(int(volume * 100))
        if self.volume_value_label:
            self.volume_value_label.setText(f"{volume:.3f}")

    def set_callbacks(
        self,
        on_start: Optional[Callable] = None,
        on_stop: Optional[Callable] = None,
        on_settings_change: Optional[Callable] = None,
    ):
        """Set callback functions for UI events."""
        self.on_start_callback = on_start
        self.on_stop_callback = on_stop
        self.on_settings_change_callback = on_settings_change

    def run(self):
        """Run the UI main loop."""
        self.is_running = True
        self.showFullScreen()

        # Auto-start the application after UI is shown
        QTimer.singleShot(100, self.start_application)

    def stop(self):
        """Stop the UI."""
        self.is_running = False
        self.close()
        QApplication.quit()

    def cleanup(self):
        """Clean up resources."""
        self.stop()

    def closeEvent(self, a0: Optional[QCloseEvent]):
        """Handle window close event."""
        self.stop()
        if a0:
            a0.accept()
