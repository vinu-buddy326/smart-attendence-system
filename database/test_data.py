from werkzeug.security import generate_password_hash
from database.db_connection import get_connection
from config import settings

def add_test_data():
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        
        # Add Admin
        cur.execute(f"SELECT id FROM users WHERE email = {settings.DB_PARAM}", ("admin@example.com",))
        if not cur.fetchone():
            cur.execute(f"INSERT INTO users (name, email, password, role) VALUES ({settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM})",
                        ("Admin User", "admin@example.com", generate_password_hash("admin123"), "admin"))
            print("[TEST-DATA] Added Admin (admin@example.com)")

        # Add Mentor
        cur.execute(f"SELECT id FROM users WHERE email = {settings.DB_PARAM}", ("mentor@example.com",))
        if not cur.fetchone():
            cur.execute(f"INSERT INTO users (name, email, password, role, section) VALUES ({settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM})",
                        ("Mentor John", "mentor@example.com", generate_password_hash("mentor123"), "mentor", "A"))
            print("[TEST-DATA] Added Mentor (mentor@example.com)")
        
        # Add Students
        students = [
            ("Alice Smith", "ROLL001", "A", "+1234567890"),
            ("Bob Jones", "ROLL002", "A", "+1234567891"),
            ("Charlie Brown", "ROLL003", "B", "+1234567892")
        ]
        
        for s in students:
            cur.execute(f"SELECT student_id FROM students WHERE roll_number = {settings.DB_PARAM}", (s[1],))
            if not cur.fetchone():
                cur.execute(f"INSERT INTO students (name, roll_number, section, phone_number) VALUES ({settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM})", s)
                print(f"[TEST-DATA] Added Student {s[0]} ({s[1]})")

        conn.commit()
        cur.close()
        conn.close()
        print("Test data verification complete.")

if __name__ == "__main__":
    add_test_data()
