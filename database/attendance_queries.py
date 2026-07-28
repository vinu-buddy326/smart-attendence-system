from database.db_connection import get_connection
from datetime import date as dt_date, datetime
from config import settings

import time
import os

START_TIME = time.time()
LAST_RESOLVED_PERIOD = None
SENT_SMS_CACHE = set()

def get_current_period():
    global LAST_RESOLVED_PERIOD
    if getattr(settings, "TEST_MODE", False):
        # Calculate dynamic test period based on application uptime
        # Default duration: 60 seconds per period for a swift presentation, configurable via environment
        duration = int(os.getenv("DEMO_PERIOD_DURATION_SEC", "60"))
        uptime = time.time() - START_TIME
        
        if uptime < duration:
            period = "P1"
        elif uptime < duration * 2:
            period = "P2"
        elif uptime < duration * 3:
            period = "P3"
        elif uptime < duration * 4:
            period = "P4"
        elif uptime < duration * 5:
            period = "P5"
        else:
            period = "P6"
            
        # When transitioning to a new period during demo, auto-end the current active session
        # so that a new session is created for the new period and SMS can be sent again.
        if LAST_RESOLVED_PERIOD is not None and LAST_RESOLVED_PERIOD != period:
            print(f"[DEMO] Uptime: {int(uptime)}s. Period transitioning from {LAST_RESOLVED_PERIOD} to {period}. Auto-ending active session...")
            try:
                end_active_session()
            except Exception as e:
                print(f"[DEMO] Error ending session on period transition: {e}")
                
        LAST_RESOLVED_PERIOD = period
        return period
        
    now = datetime.now().time()
    for period_name, (start_str, end_str) in getattr(settings, "PERIOD_SCHEDULE", {}).items():
        start_time = datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.strptime(end_str, "%H:%M").time()
        if start_time <= now <= end_time:
            return period_name
    return None

def get_previous_period(current_period):
    schedule = list(getattr(settings, "PERIOD_SCHEDULE", {}).keys())
    if current_period in schedule:
        idx = schedule.index(current_period)
        if idx > 0:
            return schedule[idx - 1]
    return None

def check_and_create_missed_request(student_id, detected_period, date_obj):
    prev_period = get_previous_period(detected_period)
    if not prev_period:
        return
        
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        
        # Check if student was present in the previous period
        cur.execute(f"SELECT attendance_id FROM attendance WHERE student_id = {settings.DB_PARAM} AND date = {settings.DB_PARAM} AND period = {settings.DB_PARAM}", (student_id, date_obj, prev_period))
        was_present = cur.fetchone()
        
        if not was_present:
            # Check if there's already a request to avoid duplicates
            cur.execute(f"SELECT id FROM missed_attendance_requests WHERE student_id = {settings.DB_PARAM} AND date = {settings.DB_PARAM} AND missed_period = {settings.DB_PARAM}", (student_id, date_obj, prev_period))
            existing_req = cur.fetchone()
            
            if not existing_req:
                cur.execute(f"""
                    INSERT INTO missed_attendance_requests (student_id, missed_period, detected_period, date, status)
                    VALUES ({settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, 'pending')
                    ON CONFLICT(student_id, date, missed_period) DO NOTHING
                """, (student_id, prev_period, detected_period, date_obj))
                conn.commit()
                print(f"[MISS-ATT] Missed attendance created for Student ID {student_id} (Missed: {prev_period})")
        
        cur.close()
        conn.close()

def mark_attendance(student_id_or_roll, period=None):
    if not period:
        period = get_current_period() or "TEST-NOW"
        
    session_id, session_name = get_or_create_active_session()
    if not session_id:
        return "No active session"
        
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        
        # Resolve student_id if roll number is provided
        student_id = student_id_or_roll
        if isinstance(student_id_or_roll, str):
            from database.student_queries import get_student_by_roll
            student = get_student_by_roll(student_id_or_roll)
            if student:
                student_id = student[0]
            else: 
                cur.close(); conn.close()
                return "Student not found"

        today = dt_date.today()
        # Prevent duplicate entries per session
        cur.execute(f"SELECT attendance_id FROM attendance WHERE student_id = {settings.DB_PARAM} AND session_id = {settings.DB_PARAM}", (student_id, session_id))
        if cur.fetchone():
            cur.close(); conn.close()
            return "Already marked for this session"
        
        cur.execute(f"INSERT INTO attendance (student_id, date, period, time_marked, session_id) VALUES ({settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM})",
                    (student_id, today, period, datetime.now().time(), session_id))
        conn.commit()
        
        # Check for missed previous period
        if getattr(settings, 'DB_TYPE', 'sqlite') != 'sqlite' or True: # Works on both
            check_and_create_missed_request(student_id, period, today)
            
        # Dispatch Real-Time SMS Notification
        global SENT_SMS_CACHE
        cache_key = (student_id, period)
        if cache_key not in SENT_SMS_CACHE:
            cur.execute(f"SELECT name, phone_number FROM students WHERE student_id = {settings.DB_PARAM}", (student_id,))
            sdata = cur.fetchone()
            if sdata and sdata[1]:
                SENT_SMS_CACHE.add(cache_key)
                try:
                    from notifications.sms_sender import SMSSender
                    sms_client = SMSSender()
                    formatted_time = datetime.now().strftime("%I:%M %p")
                    import threading
                    threading.Thread(target=sms_client.send_attendance_msg, args=(sdata[0], sdata[1], period, today, formatted_time), daemon=True).start()
                except Exception as e:
                    print(f"[SMS] Dispatch Error: {e}")
        else:
            print(f"[SMS] Skipping duplicate SMS for student {student_id} in period {period} (already sent in this run)")

        cur.close(); conn.close()
        return "Success"
    return "DB Connection Failed"

def get_attendance_by_section(section, date=None):
    if not date:
        date = dt_date.today()
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT s.name, s.roll_number, a.period, a.time_marked, a.status
            FROM attendance a
            JOIN students s ON a.student_id = s.student_id
            WHERE s.section = {settings.DB_PARAM} AND a.date = {settings.DB_PARAM}
            ORDER BY s.name ASC, a.period ASC
        """, (section, date))
        attendance_rec = cur.fetchall()
        cur.close()
        conn.close()
        return attendance_rec
    return []

def get_all_attendance(date=None):
    if not date:
        date = dt_date.today()
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT s.name, s.roll_number, s.section, a.period, a.time_marked, a.status, a.date
            FROM attendance a
            JOIN students s ON a.student_id = s.student_id
            WHERE a.date = {settings.DB_PARAM}
            ORDER BY s.name ASC, a.period ASC
        """, (date,))
        attendance_rec = cur.fetchall()
        cur.close()
        conn.close()
        return attendance_rec
    return []

def get_daily_stats(section=None):
    today = dt_date.today()
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        if section:
            cur.execute(f"SELECT COUNT(DISTINCT student_id) FROM attendance WHERE date = {settings.DB_PARAM} AND student_id IN (SELECT student_id FROM students WHERE section = {settings.DB_PARAM})", (today, section))
            present = cur.fetchone()[0] or 0
            cur.execute(f"SELECT COUNT(*) FROM students WHERE section = {settings.DB_PARAM}", (section,))
            total = cur.fetchone()[0] or 0
        else:
            cur.execute(f"SELECT COUNT(DISTINCT student_id) FROM attendance WHERE date = {settings.DB_PARAM}", (today,))
            present = cur.fetchone()[0] or 0
            cur.execute("SELECT COUNT(*) FROM students")
            total = cur.fetchone()[0] or 0
        cur.close()
        conn.close()
        return {"total": total, "present": present}
    return {"total": 0, "present": 0}

def get_sections():
    """Return list of distinct section names."""
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT section FROM students ORDER BY section")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [r[0] for r in rows if r[0]]
    return []

def get_attendance_summary(filter_date=None, section=None):
    """
    Per-student attendance summary for a given date.
    Returns: (student_id, name, roll, section, phone, periods_present, total_periods, pct, is_present_today)
    """
    if not filter_date:
        filter_date = dt_date.today()
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        # Total distinct periods recorded in current active session
        cur.execute("SELECT COUNT(DISTINCT period) FROM attendance WHERE session_id = (SELECT session_id FROM attendance_sessions WHERE is_active = 1 LIMIT 1)")
        total_periods = cur.fetchone()[0] or 1

        section_clause = f"AND s.section = {settings.DB_PARAM}" if section else ""
        params = [filter_date]
        if section:
            params.append(section)

        cur.execute(f"""
            SELECT
                s.student_id,
                s.name,
                s.roll_number,
                s.section,
                s.phone_number,
                COUNT(a.attendance_id) AS periods_present,
                {total_periods} AS total_periods,
                CASE WHEN COUNT(a.attendance_id) > 0 THEN 1 ELSE 0 END AS is_present
            FROM students s
            LEFT JOIN attendance a
                ON s.student_id = a.student_id
                AND a.date = {settings.DB_PARAM}
                AND a.session_id = (SELECT session_id FROM attendance_sessions WHERE is_active = 1 LIMIT 1)
            WHERE 1=1 {section_clause}
            GROUP BY s.student_id, s.name, s.roll_number, s.section, s.phone_number
            ORDER BY s.name ASC
        """, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        # Append percentage: row = (id, name, roll, section, phone, periods_present, total_periods, is_present)
        result = []
        for r in rows:
            tp = total_periods if total_periods > 0 else 1
            pct = round((r[5] / tp) * 100, 1)
            result.append(r + (pct,))
        return result
    return []

def get_all_attendance_filtered(filter_date=None, section=None):
    """Detailed raw logs filtered by date and optionally section."""
    if not filter_date:
        filter_date = dt_date.today()
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        section_clause = f"AND s.section = {settings.DB_PARAM}" if section else ""
        params = [filter_date]
        if section:
            params.append(section)
        cur.execute(f"""
            SELECT s.name, s.roll_number, s.section, a.period, a.time_marked, a.status, a.date, s.email, s.phone_number, s.university, s.school
            FROM attendance a
            JOIN students s ON a.student_id = s.student_id
            WHERE a.date = {settings.DB_PARAM} {section_clause}
            ORDER BY s.name ASC, a.period ASC
        """, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    return []

def get_attendance_by_range(start_date, end_date, section=None):
    """Retrieve all attendance logs within a date range."""
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        section_clause = f"AND s.section = {settings.DB_PARAM}" if section else ""
        params = [start_date, end_date]
        if section:
            params.append(section)
        
        cur.execute(f"""
            SELECT s.name, s.roll_number, s.section, a.period, a.time_marked, a.status, a.date, s.email, s.phone_number, s.university, s.school
            FROM attendance a
            JOIN students s ON a.student_id = s.student_id
            WHERE (a.date BETWEEN {settings.DB_PARAM} AND {settings.DB_PARAM}) {section_clause}
            ORDER BY a.date DESC, s.name ASC, a.period ASC
        """, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    return []

def get_student_attendance(roll_number):
    """Retrieve all attendance logs for a specific student by roll number."""
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT s.name, a.date, a.time_marked, a.period
            FROM attendance a
            JOIN students s ON a.student_id = s.student_id
            WHERE s.roll_number = {settings.DB_PARAM}
            ORDER BY a.date DESC, a.time_marked DESC
        """, (roll_number,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    return []

# --- Missed Attendance Queries ---

def get_missed_attendance_requests(section=None):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        section_clause = f"AND s.section = {settings.DB_PARAM}" if section else ""
        params = []
        if section:
            params.append(section)
            
        cur.execute(f"""
            SELECT m.id, s.name, s.roll_number, s.section, m.missed_period, m.detected_period, m.date, m.status
            FROM missed_attendance_requests m
            JOIN students s ON m.student_id = s.student_id
            WHERE 1=1 {section_clause}
            ORDER BY m.created_at DESC
        """, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    return []

def create_missed_request_manually(student_id, period):
    """Specifically for the 10-15 min late window."""
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        today = dt_date.today()
        try:
            cur.execute(f"""
                INSERT INTO missed_attendance_requests (student_id, missed_period, detected_period, date, status)
                VALUES ({settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, 'pending')
                ON CONFLICT(student_id, date, missed_period) DO NOTHING
            """, (student_id, period, period, today))
            conn.commit()
            return "success"
        except Exception as e:
            return str(e)
        finally:
            cur.close()
            conn.close()
    return "DB Error"

def get_student_missed_requests(student_id):
    """Retrieve missed attendance requests for a specific student."""
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT m.id, m.missed_period, m.detected_period, m.date, m.status
            FROM missed_attendance_requests m
            WHERE m.student_id = {settings.DB_PARAM}
            ORDER BY m.date DESC, m.missed_period DESC
        """, (student_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    return []

def process_missed_request(request_id, action):
    # action should be 'approved' or 'rejected'
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        
        cur.execute(f"SELECT student_id, date, missed_period, status FROM missed_attendance_requests WHERE id = {settings.DB_PARAM}", (request_id,))
        req = cur.fetchone()
        
        if not req:
            cur.close(); conn.close()
            return "Request not found"
            
        if req[3] != 'pending':
            cur.close(); conn.close()
            return "Request already processed"
            
        student_id, r_date, missed_period = req[0], req[1], req[2]
        
        if action == "approved":
            # Just insert a present record if it doesn't exist. "time_marked" can just be 00:00:00 or current.
            cur.execute(f"SELECT attendance_id FROM attendance WHERE student_id = {settings.DB_PARAM} AND date = {settings.DB_PARAM} AND period = {settings.DB_PARAM}", (student_id, r_date, missed_period))
            if not cur.fetchone():
                cur.execute(f"INSERT INTO attendance (student_id, date, period, status, time_marked) VALUES ({settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, 'Present', '00:00:00')", (student_id, r_date, missed_period))
        
        cur.execute(f"UPDATE missed_attendance_requests SET status = {settings.DB_PARAM} WHERE id = {settings.DB_PARAM}", (action, request_id))
        conn.commit()
        cur.close()
        conn.close()
        return "success"
    return "DB error"

def get_or_create_active_session():
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        try:
            # Look for active session
            cur.execute("SELECT session_id, session_name FROM attendance_sessions WHERE is_active = 1 LIMIT 1")
            row = cur.fetchone()
            if row:
                return row[0], row[1]
            
            # None active, create a new one
            cur.execute("SELECT COALESCE(MAX(session_id), 0) + 1 FROM attendance_sessions")
            next_id = cur.fetchone()[0]
            session_name = f"Session {next_id}"
            
            if settings.DB_TYPE == "sqlite":
                cur.execute(
                    "INSERT INTO attendance_sessions (session_id, session_name, is_active) VALUES (?, ?, 1)",
                    (next_id, session_name)
                )
            else:
                cur.execute(
                    "INSERT INTO attendance_sessions (session_id, session_name, is_active) VALUES (%s, %s, 1)",
                    (next_id, session_name)
                )
            conn.commit()
            print(f"[SESSION] Created new active session: {session_name} (ID: {next_id})")
            return next_id, session_name
        except Exception as e:
            conn.rollback()
            print(f"[SESSION] Error creating session: {e}")
            return None, None
        finally:
            cur.close()
            conn.close()
    return None, None

def end_active_session():
    global SENT_SMS_CACHE
    SENT_SMS_CACHE.clear()
    
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        try:
            cur.execute("UPDATE attendance_sessions SET is_active = 0, end_time = CURRENT_TIMESTAMP WHERE is_active = 1")
            conn.commit()
            print("[SESSION] Ended active session.")
            
            # Reset in-memory cache/cooldown in stream if running
            try:
                from ai_engine.camera_stream import stream
                stream.last_marked_time = {}
                stream.last_status = {}
            except Exception as e:
                pass
                
            return "success"
        except Exception as e:
            conn.rollback()
            print(f"[SESSION] Error ending active session: {e}")
            return str(e)
        finally:
            cur.close()
            conn.close()
    return "no connection"
