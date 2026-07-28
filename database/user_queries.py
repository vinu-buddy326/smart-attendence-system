from database.db_connection import get_connection
from config import settings
from werkzeug.security import generate_password_hash, check_password_hash

def get_all_users():
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, email, role, section, subjects FROM users ORDER BY role, name")
        users = cur.fetchall()
        cur.close()
        conn.close()
        return users
    return []

def get_user_by_id(user_id):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute(f"SELECT id, name, email, role, section, subjects FROM users WHERE id = {settings.DB_PARAM}", (user_id,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        return user
    return None

def create_user(name, email, password, role, section=None, subjects=None):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        try:
            hashed = generate_password_hash(password)
            cur.execute(
                f"INSERT INTO users (name, email, password, role, section, subjects) VALUES ({settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM})",
                (name, email, hashed, role, section, subjects)
            )
            conn.commit()
            return "success"
        except Exception as e:
            conn.rollback()
            return f"error: {e}"
        finally:
            cur.close()
            conn.close()
    return "error: no connection"

def update_user_profile(user_id, name, section, subjects=None):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        try:
            cur.execute(
                f"UPDATE users SET name={settings.DB_PARAM}, section={settings.DB_PARAM}, subjects={settings.DB_PARAM} WHERE id={settings.DB_PARAM}",
                (name, section, subjects, user_id)
            )
            conn.commit()
            return "success"
        except Exception as e:
            conn.rollback()
            return f"error: {e}"
        finally:
            cur.close()
            conn.close()
    return "error: no connection"

def change_user_password(user_id, current_password, new_password):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute(f"SELECT password FROM users WHERE id = {settings.DB_PARAM}", (user_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return "error: user not found"
        if not check_password_hash(row[0], current_password):
            return "error: incorrect current password"
        conn2 = get_connection()
        cur2 = conn2.cursor()
        cur2.execute(
            f"UPDATE users SET password={settings.DB_PARAM} WHERE id={settings.DB_PARAM}",
            (generate_password_hash(new_password), user_id)
        )
        conn2.commit()
        cur2.close()
        conn2.close()
        return "success"
    return "error: no connection"

def delete_user(user_id):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        try:
            cur.execute(f"DELETE FROM users WHERE id = {settings.DB_PARAM}", (user_id,))
            conn.commit()
            return "success"
        except Exception as e:
            conn.rollback()
            return f"error: {e}"
        finally:
            cur.close()
            conn.close()
    return "error: no connection"

def admin_update_user(user_id, name, email, role, section, subjects=None):
    """Admin-only: update any user's name, email, role, section."""
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        try:
            cur.execute(
                f"UPDATE users SET name={settings.DB_PARAM}, email={settings.DB_PARAM}, role={settings.DB_PARAM}, section={settings.DB_PARAM}, subjects={settings.DB_PARAM} WHERE id={settings.DB_PARAM}",
                (name, email, role, section or None, subjects or None, user_id)
            )
            conn.commit()
            return "success"
        except Exception as e:
            conn.rollback()
            return f"error: {e}"
        finally:
            cur.close()
            conn.close()
    return "error: no connection"

def admin_reset_password(user_id, new_password):
    """Admin-only: force-reset a user's password without old password."""
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        try:
            cur.execute(
                f"UPDATE users SET password={settings.DB_PARAM} WHERE id={settings.DB_PARAM}",
                (generate_password_hash(new_password), user_id)
            )
            conn.commit()
            return "success"
        except Exception as e:
            conn.rollback()
            return f"error: {e}"
        finally:
            cur.close()
            conn.close()
    return "error: no connection"
