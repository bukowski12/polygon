"""
Camera module
"""
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import pyqtSignal
from logger_config import logger

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    logger.warning("OpenCV not available - camera functionality disabled")
    CV2_AVAILABLE = False
    np = None


class Ui_Kamery(object):
    """Camera UI setup."""

    def setupUi(self, Kamery, grid, width, height):
        Kamery.setObjectName("Kamery")
        Kamery.resize(1920, 1200)
        Kamery.setWindowFlags(QtCore.Qt.Window)
        # Disable close button
        Kamery.setWindowFlags(Kamery.windowFlags() & ~QtCore.Qt.WindowCloseButtonHint)

        self.camWindow = QtWidgets.QLabel(Kamery)
        self.camWindow.setGeometry(QtCore.QRect(0, 0, grid*width, grid*height))
        self.camWindow.setObjectName("camWindow")

        self.retranslateUi(Kamery)
        QtCore.QMetaObject.connectSlotsByName(Kamery)

    def retranslateUi(self, Kamery):
        Kamery.setWindowTitle("Kamera")


class CamMatrix(QtCore.QThread):
    """Camera matrix thread for handling multiple camera streams."""

    trigger = pyqtSignal(np.ndarray) if CV2_AVAILABLE else pyqtSignal(object)

    def __init__(self, urls, width, height, user=None, password=None, parent=None):
        QtCore.QThread.__init__(self, parent)

        if not CV2_AVAILABLE:
            logger.error("Cannot initialize camera - OpenCV not available")
            return

        self.urls = urls or []
        self.width = width
        self.height = height
        self.user = user
        self.password = password
        self.running = False
        self.recording = False
        self.video_writer = None

        # Validate URLs
        self.urls = [url for url in self.urls if self._validate_url(url)]
        self.num_cameras = len(self.urls)

        logger.info(f"Initialized camera matrix with {self.num_cameras} cameras")

    def _validate_url(self, url: str) -> bool:
        """Validate camera URL format."""
        if not url or not isinstance(url, str):
            return False
        return url.startswith(('http://', 'https://', 'rtsp://'))

    def _create_no_signal_frame(self, cam_id: int):
        """Create blue 'NO SIGNAL' frame."""
        import datetime
        frame = np.full((self.height, self.width, 3), (255, 123, 0), dtype=np.uint8)
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        cv2.putText(frame, f'NO SIGNAL - CAM {cam_id+1} {time_str}',
                   (10, 50), cv2.FONT_HERSHEY_PLAIN, 2, (7, 193, 255), 4)
        return frame

    def _init_devices(self, cam=None):
        """Open VideoCapture devices. Pass cam index to reinit only one device."""
        for i, url in enumerate(self.urls):
            if cam is None or cam == i:
                try:
                    self.device[i] = cv2.VideoCapture()
                    self.device[i].open(
                        url,
                        apiPreference=cv2.CAP_FFMPEG,
                        params=[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000],
                    )
                    if not self.device[i].isOpened():
                        raise ConnectionError
                    logger.info(f"Camera {i+1} opened: {url}")
                except Exception:
                    logger.warning(f"Camera {i+1} could not be opened: {url}")

    def _get_frame(self, cam_id: int):
        """Read one frame from device; return NO SIGNAL frame on failure."""
        ret, frame = self.device[cam_id].read()
        if not ret:
            frame = self._create_no_signal_frame(cam_id)
            self.device[cam_id].release()
        else:
            # Resize if dimensions don't match
            h, w = frame.shape[:2]
            if h != self.height or w != self.width:
                frame = cv2.resize(frame, (self.width, self.height),
                                   interpolation=cv2.INTER_AREA)
        return frame

    def run(self):
        """Main camera thread loop."""
        if not CV2_AVAILABLE:
            logger.warning("Camera thread cannot run - no OpenCV")
            return

        logger.info("Camera thread starting...")
        self.running = True

        # Initialise frame buffer and capture devices
        self.frames = [self._create_no_signal_frame(i) for i in range(self.num_cameras)]
        self.device = [None] * self.num_cameras
        self._init_devices()

        try:
            while self.running:
                try:
                    for i in range(self.num_cameras):
                        if self.device[i] is None or not self.device[i].isOpened():
                            self._init_devices(i)
                        self.frames[i] = self._get_frame(i)

                    matrix_frame = self._create_matrix(self.frames)
                    self.trigger.emit(matrix_frame)

                    if self.recording and self.video_writer is not None:
                        self.video_writer.write(matrix_frame)

                    self.msleep(33)  # ~30 FPS

                except Exception as e:
                    logger.error(f"Error in camera loop: {e}")
                    self.msleep(1000)

        except Exception as e:
            logger.error(f"Fatal error in camera thread: {e}")
        finally:
            for dev in self.device:
                if dev is not None:
                    dev.release()
            if self.video_writer is not None:
                self.video_writer.release()
            logger.info("Camera thread stopped")

    def _create_matrix(self, frames):
        """Create matrix layout from individual frames like in original version."""
        # Always create matrix for all cameras (never return single frame)
        num_cameras = len(frames) if frames else self.num_cameras
        grid_size = int(np.ceil(np.sqrt(num_cameras)))

        # Create matrix with blue background like original (BGR: 0,0,153 = dark blue)
        matrix_height = grid_size * self.height  # 4 * 356 = 1424
        matrix_width = grid_size * self.width    # 4 * 475 = 1900
        matrix = np.full((matrix_height, matrix_width, 3), (0, 0, 153), dtype=np.uint8)

        for i, frame in enumerate(frames):
            row = i // grid_size
            col = i % grid_size

            y_start = row * self.height
            y_end = y_start + self.height
            x_start = col * self.width
            x_end = x_start + self.width

            matrix[y_start:y_end, x_start:x_end] = frame

        # Add date and time like in original version
        import datetime
        date_str = datetime.datetime.now().strftime("%d-%m-%Y")
        time_str = datetime.datetime.now().strftime("%H:%M:%S")

        # Position text in bottom right area (like original)
        cv2.putText(matrix, date_str, (3*self.width+120, 2*self.height+120),
                   cv2.FONT_HERSHEY_PLAIN, 2, (7, 193, 255), 4)
        cv2.putText(matrix, time_str, (3*self.width+150, 2*self.height+170),
                   cv2.FONT_HERSHEY_PLAIN, 2, (7, 193, 255), 4)

        return matrix

    def stop(self):
        """Stop camera thread."""
        self.running = False
        self.wait()


class Camera(QtWidgets.QWidget, Ui_Kamery):
    """Main camera widget."""

    def __init__(self, urls, width, height, user=None, password=None, parent=None):
        super().__init__(parent)

        self.urls = urls or []
        self.width = width
        self.height = height

        # Calculate grid size
        num_cameras = len(self.urls)
        self.grid_size = int(np.ceil(np.sqrt(num_cameras))) if CV2_AVAILABLE else 3

        self.setupUi(self, self.grid_size, width, height)
        # Set geometry again like in original version
        self.camWindow.setGeometry(QtCore.QRect(0, 0, self.grid_size*width, self.grid_size*height))
        logger.info(f"camWindow geometry set to: {self.grid_size*width}x{self.grid_size*height}")

        # Set window icon before show()
        import os
        icon_path = os.path.join(os.path.dirname(__file__), '../files/video.png')
        if os.path.exists(icon_path):
            from PyQt5 import QtGui
            self.setWindowIcon(QtGui.QIcon(icon_path))

        if CV2_AVAILABLE and self.urls:
            self.cam_thread = CamMatrix(urls, width, height, user, password, self)
            # Connect signal BEFORE show and start (like in original version)
            self.cam_thread.trigger.connect(self.display)
            # Show the camera window (like in original version)
            self.show()
            # Start thread AFTER signal is connected
            self.cam_thread.start()
        else:
            logger.warning("Camera not initialized - OpenCV unavailable or no URLs")
            self.cam_thread = None

    def display(self, camGrid):
        """Display camera matrix like in original version."""
        try:
            if CV2_AVAILABLE and camGrid is not None:
                height, width, bytes_per_component = camGrid.shape
                bytes_per_line = bytes_per_component * width
                # Convert BGR to RGB and create QImage (width, height order for QImage!)
                image = QImage(camGrid.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
                self.camWindow.setPixmap(QPixmap.fromImage(image))
        except Exception as e:
            logger.error(f"Error displaying camera matrix: {e}")

    def startRecord(self, folder_path):
        """Start recording to folder_path using cv2.VideoWriter."""
        if not self.cam_thread:
            return
        import datetime
        import os
        filename = datetime.datetime.now().strftime('%Y%m%d%H%M%S') + '.avi'
        filepath = os.path.join(folder_path, filename)
        os.makedirs(folder_path, exist_ok=True)
        grid = self.cam_thread.num_cameras and int(np.ceil(np.sqrt(self.cam_thread.num_cameras))) or self.grid_size
        out_w = grid * self.width
        out_h = grid * self.height
        try:
            self.cam_thread.video_writer = cv2.VideoWriter(
                filepath,
                cv2.VideoWriter_fourcc(*'XVID'),
                1,
                (out_w, out_h),
            )
            self.cam_thread.recording = True
            logger.info(f"Recording started: {filepath}")
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")

    def stopRecord(self):
        """Stop recording and release VideoWriter."""
        if not self.cam_thread:
            return
        self.cam_thread.recording = False
        if self.cam_thread.video_writer is not None:
            self.cam_thread.video_writer.release()
            self.cam_thread.video_writer = None
        logger.info("Recording stopped")

    def closeEvent(self, event):
        """Handle widget close event."""
        if self.cam_thread:
            self.cam_thread.stop()
            self.cam_thread.wait()  # Wait for thread to finish
        event.accept()
        super().closeEvent(event)