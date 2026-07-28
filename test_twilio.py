import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from notifications.sms_sender import SMSSender
from config import settings

def test_twilio():
    print(f"Twilio Account SID: {settings.TWILIO_ACCOUNT_SID}")
    print(f"Twilio From Number: {settings.TWILIO_PHONE_NUMBER}")
    
    sender = SMSSender()
    
    # Test phone number (user should replace this)
    test_number = input("Enter a phone number to send a test message to (with country code, e.g., +91...): ")
    
    if not test_number:
        print("No number entered. Exiting.")
        return
        
    print(f"Sending test message to {test_number}...")
    sender.send_custom_msg(test_number, "Test Message from Smart Attendance AI: Twilio is working correctly!")
    print("Check the terminal for ' [SMS] Custom Sent' message.")

if __name__ == "__main__":
    test_twilio()
