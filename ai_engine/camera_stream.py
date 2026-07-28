import cv2
import threading
import time
import numpy as np
from datetime import datetime
from ai_engine.face_recognition_module import FaceRecognitionModule
from database.attendance_queries import mark_attendance
from config import settings

class CameraStream:
    def __init__(self):
        self.video_capture = None
        self.is_running = False
        self.frame = None
        self.lock = threading.Lock()
        self.thread = None
        
        # Load the Face Recognition Engine (heavy)
        print("[AI] Initializing Face Engine...")
        self.face_engine = FaceRecognitionModule(dataset_path="datasets/faces/", model_dir="models/")
        
        # Avoid spamming DB logic
        self.last_marked_time = {} # student_id -> timestamp
        self.last_status = {}      # student_id -> status string
        self.current_recognition_status = {"status": "Scanning...", "student_name": "", "message": "Searching for faces..."}
        self.last_recognized_roll = None

    def _run_demo_mode(self):
        """Simulator mode that cycles through existing images in the dataset."""
        import os
        import random
        
        all_images = []
        for root, dirs, files in os.walk("datasets/faces/"):
            for f in files:
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    all_images.append(os.path.join(root, f))
        
        if not all_images:
            print("[DEMO] No images found in datasets/faces/ to simulate.")
            self.frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(self.frame, "No Camera & No Demo Images", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            time.sleep(2)
            return

        while self.is_running and self.video_capture is None:
            img_path = random.choice(all_images)
            frame = cv2.imread(img_path)
            if frame is None: continue
            
            # Simulate detection and UI
            print(f"[DEMO] Simulating camera feed with: {os.path.basename(img_path)}")
            
            # We must detect and mark just like the real loop
            h, w, _ = frame.shape
            self.face_engine.detector.setInputSize((w, h))
            _, faces = self.face_engine.detector.detect(frame)
            
            if faces is not None and len(faces) > 0:
                self.current_recognition_status["status"] = "Recognizing Face..."
                self.current_recognition_status["message"] = "Analyzing biometrics..."
                for face in faces:
                    x, y, fw, fh = [int(v) for v in face[0:4]]
                    x, y = max(0, x), max(0, y)
                    bbox_ltrb = [x, y, x+fw, y+fh]
                    student_id = self.face_engine.recognize_face(frame, bbox_ltrb)
                    
                    if student_id != "Unknown":
                        from database.student_queries import get_student_by_roll
                        student = get_student_by_roll(student_id)
                        student_name = student[1] if student else student_id
                        
                        self.current_recognition_status["status"] = "Face Matched"
                        self.current_recognition_status["student_name"] = student_name
                        self.last_recognized_roll = student_id
                        print("Manager Recognized", flush=True)
                        
                        now = time.time()
                        last_time = self.last_marked_time.get(student_id, 0)
                        
                        if now - last_time > 15:
                            res = mark_attendance(student_id) # Let queries auto-determine period (resolves to P2 in test mode)
                            if res == "Success":
                                self.last_marked_time[student_id] = now
                                self.last_status[student_id] = "Attendance Marked Successfully"
                            elif "Already" in res or res == "Already marked for this session":
                                self.last_marked_time[student_id] = now
                                self.last_status[student_id] = "Attendance Already Marked"
                            else:
                                self.last_status[student_id] = res
                        
                        status_msg = self.last_status.get(student_id, "Processing...")
                        self.current_recognition_status["message"] = status_msg
                        
                        color = (0, 255, 159) if "Successfully" in status_msg else (0, 159, 255)
                        label = f"{student_name}: {status_msg}"
                    else:
                        color = (77, 77, 255)
                        label = "Unknown"
                    
                    cv2.rectangle(frame, (x, y), (x+fw, y+fh), color, 2)
                    cv2.putText(frame, label, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            else:
                self.current_recognition_status = {"status": "Scanning...", "student_name": "", "message": "Searching for faces..."}

            with self.lock:
                self.frame = frame.copy()
            
            # Show each 'demo' frame for 3 seconds
            for _ in range(30):
                if not self.is_running or self.video_capture is not None: break
                time.sleep(0.1)

    def start(self):
        with self.lock:
            if self.is_running:
                return
            self.is_running = True
            
            # Start read/process loop in thread (it will handle opening the camera)
            self.thread = threading.Thread(target=self._update_loop, daemon=True)
            self.thread.start()

    def _open_camera(self):
        print("[CAMERA] Attempting to connect to video source...")
        # RTSP CCTV mode
        if getattr(settings, "CAMERA_SOURCE", "webcam") == "rtsp":
            rtsp_url = getattr(settings, "RTSP_URL", "")
            if not rtsp_url:
                print("[CAMERA] CAMERA_SOURCE=rtsp but RTSP_URL is empty.")
                return None
            cap = cv2.VideoCapture(rtsp_url)
            if cap is not None and cap.isOpened():
                print(f"[CAMERA] Connected to RTSP stream: {rtsp_url}")
                return cap
            print("[CAMERA] Failed to open RTSP stream.")
            return None

        # Webcam mode (Windows laptop/USB)
        backend_map = {
            "any": cv2.CAP_ANY,
            "dshow": cv2.CAP_DSHOW,
            "msmf": cv2.CAP_MSMF,
        }
        preferred_backend = backend_map.get(getattr(settings, "CAMERA_BACKEND", "any"), cv2.CAP_ANY)

        # Build backend preference list (try preferred first).
        backends = [preferred_backend]
        for b in (cv2.CAP_ANY, cv2.CAP_DSHOW, cv2.CAP_MSMF):
            if b not in backends:
                backends.append(b)

        preferred_idx = int(getattr(settings, "CAMERA_INDEX", 0))
        max_idx = int(getattr(settings, "CAMERA_SCAN_MAX_INDEX", 5))
        scan_idxs = [preferred_idx] + [i for i in range(0, max_idx + 1) if i != preferred_idx]

        for backend in backends:
            for cam_idx in scan_idxs:
                cap = cv2.VideoCapture(cam_idx, backend)
                if cap is not None and cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    print(f"[CAMERA] Connected to camera index {cam_idx} with backend {backend}")
                    return cap
                try:
                    cap.release()
                except Exception:
                    pass
        return None

    def _update_loop(self):
        fail_counter = 0
        while self.is_running:
            if self.video_capture is None or not self.video_capture.isOpened():
                self.video_capture = self._open_camera()
                if self.video_capture is None:
                    fail_counter += 1
                    if fail_counter >= 3:
                        # Enter DEMO MODE if no camera found after 3 attempts
                        print("[CAMERA] No physical camera found. Switching to DEMO MODE using dataset images.")
                        self._run_demo_mode()
                        continue
                    print(f"[CAMERA] No camera found. Retry {fail_counter}/3 in 3 seconds...")
                    time.sleep(3)
                    continue

            fail_counter = 0
            ret, frame = self.video_capture.read()
            if not ret or frame is None:
                if self.video_capture is not None:
                    self.video_capture.release()
                    self.video_capture = None
                time.sleep(0.5)
                continue
                
            fail_counter = 0
            frame = cv2.flip(frame, 1) # Mirror mode
            
            # Detect faces using YuNet
            h, w, _ = frame.shape
            self.face_engine.detector.setInputSize((w, h))
            _, faces = self.face_engine.detector.detect(frame)
            
            if faces is not None and len(faces) > 0:
                self.current_recognition_status["status"] = "Recognizing Face..."
                self.current_recognition_status["message"] = "Analyzing biometrics..."
                for face in faces:
                    # YuNet output: bbox x, y, w, h
                    x, y, fw, fh = [int(v) for v in face[0:4]]
                    
                    # Prevent out of bounds
                    x = max(0, x)
                    y = max(0, y)
                    
                    bbox_ltrb = [x, y, x+fw, y+fh]
                    
                    # Recognize
                    student_id = self.face_engine.recognize_face(frame, bbox_ltrb)
                    
                    if student_id != "Unknown":
                        from database.student_queries import get_student_by_roll
                        student = get_student_by_roll(student_id)
                        student_name = student[1] if student else student_id
                        
                        self.current_recognition_status["status"] = "Face Matched"
                        self.current_recognition_status["student_name"] = student_name
                        self.last_recognized_roll = student_id
                        print("Manager Recognized", flush=True)
                        
                        now = time.time()
                        last_time = self.last_marked_time.get(student_id, 0)
                        
                        if now - last_time > 15:
                            res = mark_attendance(student_id)  # Let queries auto-determine period
                            if res == "Success":
                                print(f"[ATTENDANCE] Marked {student_id} ({student_name}) present!")
                                self.last_marked_time[student_id] = now
                                self.last_status[student_id] = "Attendance Marked Successfully"
                            elif "Already" in res or res == "Already marked for this session":
                                self.last_marked_time[student_id] = now
                                self.last_status[student_id] = "Attendance Already Marked"
                            else:
                                self.last_status[student_id] = res
                                
                        status_msg = self.last_status.get(student_id, "Processing...")
                        self.current_recognition_status["message"] = status_msg
                        
                        color = (0, 255, 159) if "Successfully" in status_msg else (0, 159, 255)
                        label = f"{student_name}: {status_msg}"
                    else:
                        color = (77, 77, 255) # Red
                        label = "Unknown"
                        
                    # Draw UI
                    cv2.rectangle(frame, (x, y), (x+fw, y+fh), color, 2)
                    cv2.putText(frame, label, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            else:
                self.current_recognition_status = {"status": "Scanning...", "student_name": "", "message": "Searching for faces..."}

            with self.lock:
                self.frame = frame.copy()
            
            time.sleep(0.03) # Cap at ~30 FPS
            
    def get_frame(self):
        with self.lock:
            if self.frame is None:
                # Return eager black frame
                return cv2.imencode('.jpg', cv2.resize(cv2.imread('static/images/empty_cam.jpg') if False else cv2.Mat(np.zeros((480, 640, 3), dtype=np.uint8)), (640, 480)))[1].tobytes()
            ret, jpeg = cv2.imencode('.jpg', self.frame)
            return jpeg.tobytes()

    def reload_ai(self):
        print("[AI] Reloading face signatures...")
        self.face_engine.load_known_faces()

    def stop(self):
        self.is_running = False
        if self.thread is not None:
            self.thread.join()
        if self.video_capture is not None:
            self.video_capture.release()
            print("[CAMERA] Stream Stopped.")

# Singleton instance
stream = CameraStream()
