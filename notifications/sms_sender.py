from twilio.rest import Client
from config import settings
import threading
import os
import logging

class SMSSender:
    def __init__(self):
        # Configure logging
        self.logger = logging.getLogger(__name__)
        self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self.from_number = settings.TWILIO_PHONE_NUMBER
        
        # Load test mode configuration from environment / settings
        self.test_mode = os.getenv("TWILIO_TEST_MODE", "true").lower() == "true"
        verified_str = os.getenv("TWILIO_VERIFIED_NUMBERS", "")
        self.verified_numbers = [num.strip() for num in verified_str.split(",") if num.strip()]

    def _is_verified(self, phone):
        # Normalize: keep only digits, match the last 10 digits
        digits_phone = "".join(c for c in str(phone) if c.isdigit())
        if len(digits_phone) < 10:
            return False
        suffix_phone = digits_phone[-10:]
        
        for v_num in self.verified_numbers:
            digits_v = "".join(c for c in str(v_num) if c.isdigit())
            if len(digits_v) >= 10 and digits_v[-10:] == suffix_phone:
                return True
        return False

    def _format_phone(self, phone):
        clean = str(phone).strip()
        if not clean.startswith('+'):
            clean = f"+91{clean}"
        return clean

    def send_attendance_msg(self, student_name, student_phone, period, date, time):
        # Create a background thread to send the SMS so AI processing doesn't lag
        thread = threading.Thread(
            target=self._execute_send, 
            args=(student_name, student_phone, period, date, time)
        )
        thread.daemon = True
        thread.start()

    def send_custom_msg(self, phone_number, message_text):
        if self.test_mode and not self._is_verified(phone_number):
            self.logger.warning(f"[SMS] [TEST MODE] Skipping unverified number: {phone_number}")
            print("Notification Processed (Test Mode)", flush=True)
            return
            
        to_phone = self._format_phone(phone_number)
        try:
            msg = self.client.messages.create(
                body=message_text,
                from_=self.from_number,
                to=to_phone
            )
            self.logger.info(f"[SMS] Custom Sent to {to_phone}: {msg.sid}")
            print("Notification Sent", flush=True)
        except Exception as e:
            if "exceeded" in str(e).lower() or "63038" in str(e):
                self.logger.warning(f"[SMS] Twilio Quota Exceeded for {to_phone}: {e}")
            else:
                self.logger.error(f"[SMS] Custom Failed for {to_phone}: {e}")
            print("Notification Processed (Fallback)", flush=True)

    def _execute_send(self, student_name, student_phone, period, date, time):
        if self.test_mode and not self._is_verified(student_phone):
            self.logger.warning(f"[SMS] [TEST MODE] Skipping message for {student_name} (unverified phone: {student_phone})")
            print("Notification Processed (Test Mode)", flush=True)
            return
            
        to_phone = self._format_phone(student_phone)
        try:
            message = f"your attendance is marked for {period}"
            msg = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_phone
            )
            self.logger.info(f"[SMS] Sent to {student_name} ({to_phone}): {msg.sid}")
            print("Notification Sent", flush=True)
        except Exception as e:
            if "exceeded" in str(e).lower() or "63038" in str(e):
                self.logger.warning(f"[SMS] Twilio Daily Quota Exceeded for {student_name} ({to_phone}). Attendance recorded successfully.")
            else:
                self.logger.error(f"[SMS] Failed to send message for {student_name} ({to_phone}): {e}")
            print("Notification Processed (Fallback)", flush=True)
