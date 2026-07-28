from database.db_connection import get_connection
from config import settings

def add_student(name, roll_number, section, phone_number, email=None, student_code=None, primary_photo=None, id_card_url=None, university=None, school=None):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        try:
            # We must use settings.DB_PARAM to stay compatible with Postgres (%s) and SQLite (?) 
            sql = f"""
                INSERT INTO students 
                (name, roll_number, section, phone_number, email, student_code, primary_photo, id_card_url, university, school) 
                VALUES ({settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM})
            """
            cur.execute(sql, (name, roll_number, section, phone_number, email, student_code, primary_photo, id_card_url, university, school))
            conn.commit()
            return "success"
        except Exception as e:
            conn.rollback()
            return f"error: {e}"
        finally:
            cur.close()
            conn.close()
    return "error: no connection"

def get_all_students(section=None):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        if section:
            cur.execute(f"SELECT student_id, name, roll_number, section, phone_number, email, student_code, primary_photo, id_card_url, university, school FROM students WHERE section = {settings.DB_PARAM} ORDER BY name ASC", (section,))
        else:
            cur.execute("SELECT student_id, name, roll_number, section, phone_number, email, student_code, primary_photo, id_card_url, university, school FROM students ORDER BY name ASC")
        students = cur.fetchall()
        cur.close()
        conn.close()
        return students
    return []

def get_student_by_id(student_id):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute(f"SELECT student_id, name, roll_number, section, phone_number, email, student_code, primary_photo, id_card_url, university, school FROM students WHERE student_id = {settings.DB_PARAM}", (student_id,))
        student = cur.fetchone()
        cur.close()
        conn.close()
        return student
    return None

def get_student_by_roll(roll_number):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        clean_roll = str(roll_number).strip()
        stripped_roll = clean_roll.lstrip('0') or '0'
        
        # Translation Mapping for folder prefixes to actual database roll numbers
        if stripped_roll == '26' or clean_roll == '0026':
            clean_roll = '11523050029'
            stripped_roll = '11523050029'
        elif stripped_roll == '541' or clean_roll == '0541':
            clean_roll = '11523050541'
            stripped_roll = '11523050541'
            
        if settings.DB_TYPE == "sqlite":
            cur.execute(
                "SELECT student_id, name, roll_number, section, phone_number, email, student_code, primary_photo, id_card_url, university, school FROM students WHERE roll_number = ? OR roll_number = ? OR LTRIM(roll_number, '0') = ?",
                (clean_roll, stripped_roll, stripped_roll)
            )
        else:
            cur.execute(
                f"SELECT student_id, name, roll_number, section, phone_number, email, student_code, primary_photo, id_card_url, university, school FROM students WHERE roll_number = %s OR roll_number = %s OR TRIM(LEADING '0' FROM roll_number) = %s",
                (clean_roll, stripped_roll, stripped_roll)
            )
        student = cur.fetchone()
        
        if student:
            cur.close()
            conn.close()
            return student
            
        # Fallback suffix check for partial roll matching
        cur.execute("SELECT student_id, name, roll_number, section, phone_number, email, student_code, primary_photo, id_card_url, university, school FROM students")
        all_students = cur.fetchall()
        cur.close()
        conn.close()
        
        for s in all_students:
            s_roll_clean = str(s[2]).strip().lstrip('0') or '0'
            if stripped_roll in s_roll_clean or s_roll_clean in stripped_roll:
                return s
    return None

def get_student_by_email(email):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute(f"SELECT student_id, name, roll_number, section, phone_number, email, student_code, primary_photo, id_card_url, university, school FROM students WHERE email = {settings.DB_PARAM}", (email,))
        student = cur.fetchone()
        cur.close()
        conn.close()
        return student
    return None

def update_student(student_id, name, section, phone_number, email=None, university=None, school=None):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        try:
            # 1. Update Students table
            cur.execute(f"UPDATE students SET name = {settings.DB_PARAM}, section = {settings.DB_PARAM}, phone_number = {settings.DB_PARAM}, email = {settings.DB_PARAM}, university = {settings.DB_PARAM}, school = {settings.DB_PARAM} WHERE student_id = {settings.DB_PARAM}", (name, section, phone_number, email, university, school, student_id))
            
            # 2. Sync with Users table if email matches
            if email:
                cur.execute(f"UPDATE users SET name = {settings.DB_PARAM}, section = {settings.DB_PARAM} WHERE email = {settings.DB_PARAM}", (name, section, email))
            
            conn.commit()
            return "success"
        except Exception as e:
            conn.rollback()
            return str(e)
        finally:
            cur.close()
            conn.close()
    return "error: no connection"

def delete_student(student_id):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        try:
            # Remove attendance records first to avoid FK constraint issues
            cur.execute(f"DELETE FROM attendance WHERE student_id = {settings.DB_PARAM}", (student_id,))
            cur.execute(f"DELETE FROM students WHERE student_id = {settings.DB_PARAM}", (student_id,))
            conn.commit()
            return "success"
        except Exception as e:
            conn.rollback()
            return f"error: {e}"
        finally:
            cur.close()
            conn.close()
    return "error: no connection"

def save_student_embedding(student_id, embedding_bytes):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        try:
            cur.execute(
                f"INSERT INTO student_embeddings (student_id, embedding) VALUES ({settings.DB_PARAM}, {settings.DB_PARAM})",
                (student_id, embedding_bytes)
            )
            conn.commit()
            return "success"
        except Exception as e:
            conn.rollback()
            return str(e)
        finally:
            cur.close()
            conn.close()
    return "error: no connection"

def get_all_embeddings():
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        try:
            cur.execute("SELECT s.roll_number, e.embedding FROM student_embeddings e JOIN students s ON e.student_id = s.student_id")
            rows = cur.fetchall()
            return rows
        except Exception as e:
            print(f"[DB] Error fetching embeddings: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    return []

