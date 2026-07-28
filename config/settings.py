import os
import sys
from dotenv import load_dotenv

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_path, relative_path)

load_dotenv()

# Database Config
DB_TYPE = os.getenv("DB_TYPE", "postgres") # Forced to postgres
DB_NAME = os.getenv("DB_NAME", "attendance_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_PARAM = "?" if DB_TYPE == "sqlite" else "%s"

SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Twilio Config
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "YOUR_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "YOUR_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "YOUR_TWILIO_PHONE")

# Attendance Times
PERIOD_SCHEDULE = {
    "P1": ("11:00", "11:15"),
    "P2": ("11:50", "12:05"),
    "P3": ("13:00", "13:15"),
    "P4": ("13:50", "14:05"),
    "P5": ("14:40", "14:55"),
    "P6": ("15:00", "15:15"),
    "P7": ("15:50", "16:05"),
}

# --- FOR TESTING / DEMO ---
# Set to True if you want to run attendance RIGHT NOW regardless of the clock
TEST_MODE = os.getenv("TEST_MODE", "False").lower() == "true"
ATTENDANCE_PERIODS = list(PERIOD_SCHEDULE.keys())
DETECTION_DURATION_MINS = 15 # How long AI recognizes when period starts

# AI Model Paths
YOLO_MODEL_PATH = resource_path("models/yolov8n.pt")  # Pre-trained YOLOv8 Nano

# Face Recognition Settings
# Datasets and ID cards should stay in the project folder, not inside the EXE temp folder
FACE_DATASET_PATH = os.path.join(os.getcwd(), "datasets/faces/")
BODY_DATASET_PATH = os.path.join(os.getcwd(), "datasets/bodies/")
ID_CARD_DIR = os.path.join(os.getcwd(), "static/id_cards/")

# Camera settings (Windows webcams or RTSP CCTV)
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
# one of: any, dshow, msmf
CAMERA_BACKEND = os.getenv("CAMERA_BACKEND", "any").lower().strip()
CAMERA_SCAN_MAX_INDEX = int(os.getenv("CAMERA_SCAN_MAX_INDEX", "5"))
CAMERA_SOURCE = os.getenv("CAMERA_SOURCE", "webcam").lower().strip()  # webcam or rtsp
RTSP_URL = os.getenv("RTSP_URL", "")

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-12345")
