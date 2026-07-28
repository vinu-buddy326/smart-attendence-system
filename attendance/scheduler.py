import sys
import os
import time
import threading
from datetime import datetime, timedelta

# Fix imports for file structure - MUST be at the top
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import schedule
from config import settings
from ai_engine.person_detection import PersonDetector
from ai_engine.tracking import ObjectTracker
from ai_engine.face_recognition_module import FaceRecognitionModule
from ai_engine.body_recognition_module import BodyRecognitionFallback
from ai_engine.liveness_detection import LivenessDetector
from attendance.attendance_marker import AttendanceMarker
import cv2

def run_detection_for(duration_mins=None, period="TEST-NOW", duration_secs=None):
    print(f"{period} Started", flush=True)
    start_time = datetime.now()
    if duration_secs is not None:
        end_time = start_time + timedelta(seconds=duration_secs)
    else:
        end_time = start_time + timedelta(minutes=duration_mins or 15)

    detector = PersonDetector(settings.YOLO_MODEL_PATH)
    tracker = ObjectTracker()
    face_rec = FaceRecognitionModule(settings.FACE_DATASET_PATH)
    liveness = LivenessDetector()
    marker = AttendanceMarker()

    # Camera/RTSP source
    cap = None
    if settings.CAMERA_SOURCE == "rtsp":
        if not settings.RTSP_URL:
            print("[SCHEDULER] CAMERA_SOURCE=rtsp but RTSP_URL is empty.")
            return
        cap = cv2.VideoCapture(settings.RTSP_URL)
        if not cap.isOpened():
            print(f"[SCHEDULER] Failed to open RTSP stream: {settings.RTSP_URL}")
            return
        print(f"[SCHEDULER] Using RTSP stream for period {period}")
    else:
        backend_map = {
            "any": cv2.CAP_ANY,
            "dshow": cv2.CAP_DSHOW,
            "msmf": cv2.CAP_MSMF,
        }
        preferred_backend = backend_map.get(getattr(settings, "CAMERA_BACKEND", "any").lower().strip(), cv2.CAP_ANY)
        cap = cv2.VideoCapture(settings.CAMERA_INDEX, preferred_backend)
        if not cap.isOpened():
            print(f"[SCHEDULER] Camera index {settings.CAMERA_INDEX} not available.")
            return
        print(f"[SCHEDULER] Using webcam index {settings.CAMERA_INDEX} (backend: {getattr(settings, 'CAMERA_BACKEND', 'any')}) for period {period}")
    
    while datetime.now() < end_time:
        # Calculate time elapsed in minutes
        elapsed_mins = (datetime.now() - start_time).total_seconds() / 60
        is_late = elapsed_mins > 10
        
        ret, frame = cap.read()
        if not ret or frame is None:
            print("[SCHEDULER] Frame read failed, attempting reconnect...")
            time.sleep(1)
            continue
        
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ = frame.shape
        # YOLOv8 handles BGR fine
        dets = detector.detect_persons(frame)
        
        # DeepSort prefers RGB for feature extraction
        active_tracks = tracker.update_tracker(dets, rgb_frame)
        
        for track_id, ltrb in active_tracks:
            # Face Recognition (SFace based on our training expects BGR)
            result_id = face_rec.recognize_face(frame, ltrb)
            
            if result_id and result_id != "Unknown":
                print(f" [AI-ID] Recognized Student: '{result_id}'")
                print("Manager Recognized", flush=True)
                
                # Crop face for liveness to avoid scanning whole frame
                l, t, r, b = [int(x) for x in ltrb]
                # Slightly larger crop to include eyes if person is well-framed
                face_crop_rgb = rgb_frame[max(0, t):min(h, b), max(0, l):min(w, r)]
                
                if face_crop_rgb.size > 0 and liveness.check_liveness(face_crop_rgb, track_id):
                    # Mark attendance or create late request
                    result = marker.mark_and_notify(result_id, period, is_late=is_late)
                    print(f" [AI-RESULT] {result}")

        # Remove GUI for server/background operation
        # cv2.imshow("CCTV Attendance Feed", frame)
        # if cv2.waitKey(1) & 0xFF == ord('q'): break
        
    cap.release()
    # cv2.destroyAllWindows()
    print(f"Ended detection for period: {period}")

def scheduler_loop():
    if settings.TEST_MODE:
        print("[TEST_MODE] Running Demo Scheduler (P1 to P6 sequentially)...")
        from database.attendance_queries import end_active_session
        end_active_session()
        
        duration_sec = int(os.getenv("DEMO_PERIOD_DURATION_SEC", "60"))
        
        for period in ["P1", "P2", "P3", "P4", "P5", "P6"]:
            # Auto-end previous active session so that the transition starts a fresh session
            end_active_session()
            run_detection_for(period=period, duration_secs=duration_sec)
            
        print("Demo Scheduler Completed P1 to P6.")
        return

    # Regular Schedule
    for period_name, (start_time, _) in settings.PERIOD_SCHEDULE.items():
        print(f"[SCHEDULER] Registered schedule for {period_name} at {start_time}")
        schedule.every().day.at(start_time).do(run_detection_for, duration_mins=settings.DETECTION_DURATION_MINS, period=period_name)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    scheduler_loop()
