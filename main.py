import threading
import os
import sys
import time
from database.db_connection import initialize_database
from backend.app import app
from logging_config import setup_logging
from config import settings

# Path Hack for PyInstaller / Subfolder discovery
sys.path.append(os.path.abspath("."))

from attendance.scheduler import scheduler_loop

def start_scheduler():
    print("AI Scheduler Thread Started...")
    try:
        scheduler_loop()
    except Exception as e:
        print(f"Scheduler Error: {e}")

if __name__ == "__main__":
    # 0. Logging
    setup_logging()

    # 1. Initialize DB & Folder Structure
    print("Checking System Readiness...")
    initialize_database()
    
    # Deactivate previous active session on startup to reset state
    try:
        from database.attendance_queries import end_active_session
        end_active_session()
        print("[STARTUP] Resetting active attendance sessions.")
    except Exception as e:
        print(f"[STARTUP] Error resetting session: {e}")
    
    # Ensure standard folders exist
    for folder in [settings.FACE_DATASET_PATH, settings.BODY_DATASET_PATH, settings.ID_CARD_DIR, "logs"]:
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
    
    # 2. Add an Admin/Mentor for testing (Skip if already exists)
    # add_initial_users() 

    # 3. Start AI Scheduler in Background
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()
    

    
    # 4. Run Flask Server (development only)
    print("Welcome to Smart CCTV Attendance System (DEV SERVER)")
    print("Server running at http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
