from database.attendance_queries import mark_attendance
from database.student_queries import get_student_by_roll
from notifications.sms_sender import SMSSender
from datetime import datetime, date as dt_date, timedelta

class AttendanceMarker:
    def __init__(self):
        # Cache of student cooldowns to avoid spamming the database: roll_number -> datetime
        self.cooldowns = {}

    def mark_and_notify(self, roll_number, period, is_late=False):
        now = datetime.now()
        if roll_number in self.cooldowns:
            if now - self.cooldowns[roll_number] < timedelta(seconds=30):
                return "Skipping (Cooldown)"
        
        # Update/set the cooldown timestamp
        self.cooldowns[roll_number] = now

        # roll_number was our "id" from face_recognition
        student = get_student_by_roll(roll_number)
        if not student:
            print(f" [MARKER] Error: Student with roll {roll_number} not found in database.")
            return "Student Not Found"
            
        student_id, student_name, student_roll, section, phone_number = student[:5]
        
        if is_late:
            # Create a missed/late request instead of marking immediately
            from database.attendance_queries import create_missed_request_manually
            res = create_missed_request_manually(student_id, period)
            return "Late Request Created"
        else:
            # Mark attendance normally
            res = mark_attendance(student_id, period)
            
            if res == "Success":
                return f"Attendance Successful for {student_name}"
            return res
