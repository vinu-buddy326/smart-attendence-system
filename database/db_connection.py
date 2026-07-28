import sqlite3
from config import settings

def get_connection():
    try:
        if settings.DB_TYPE == "sqlite":
            return sqlite3.connect(settings.DB_NAME, check_same_thread=False)
        else:
            # Lazy import to prevent error if Postgres binaries are missing
            import psycopg
            return psycopg.connect(
                dbname=settings.DB_NAME,
                user=settings.DB_USER,
                password=settings.DB_PASS,
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                connect_timeout=5
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Error connecting to database:")
        return None

def create_database_if_not_exists():
    if settings.DB_TYPE == "sqlite": return # SQLite is file-based
    try:
        import psycopg
        # Connect to 'postgres' to create 'attendance_db'
        conn = psycopg.connect(
            dbname="postgres",
            user=settings.DB_USER,
            password=settings.DB_PASS,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            autocommit=True,
            connect_timeout=5
        )
        cur = conn.cursor()
        
        # Check if database exists
        cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (settings.DB_NAME,))
        exists = cur.fetchone()
        
        if not exists:
            cur.execute(f"CREATE DATABASE {settings.DB_NAME}")
            print(f"Database '{settings.DB_NAME}' created successfully.")
        else:
            print(f"Database '{settings.DB_NAME}' already exists.")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Critical Error: Could not connect to PostgreSQL server. Details: {e}")

def initialize_database():
    if settings.DB_TYPE == "postgres":
        create_database_if_not_exists()
    
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        
        # Use SERIAL for Postgres, AUTOINCREMENT for SQLite
        id_type = "SERIAL PRIMARY KEY" if settings.DB_TYPE == "postgres" else "INTEGER PRIMARY KEY AUTOINCREMENT"

        # Create Users table
        print("Creating Users table...")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS users (
                id {id_type},
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                section TEXT,
                subjects TEXT
            )
        """)
        
        # Create Students table
        print("Creating Students table...")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS students (
                student_id {id_type},
                name TEXT NOT NULL,
                roll_number TEXT UNIQUE NOT NULL,
                section TEXT,
                phone_number TEXT,
                email TEXT,
                student_code TEXT,
                primary_photo TEXT,
                id_card_url TEXT,
                university TEXT,
                school TEXT
            )
        """)

        # Create Attendance Sessions table
        print("Creating Attendance Sessions table...")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS attendance_sessions (
                session_id {id_type},
                session_name TEXT NOT NULL,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        """)

        # Create Student Embeddings table
        print("Creating Student Embeddings table...")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS student_embeddings (
                id {id_type},
                student_id INTEGER REFERENCES students(student_id) ON DELETE CASCADE,
                embedding BYTEA NOT NULL
            )
        """)
        
        # Create Attendance table
        print("Creating Attendance table...")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS attendance (
                attendance_id {id_type},
                student_id INTEGER REFERENCES students(student_id),
                date DATE NOT NULL,
                period TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Present',
                time_marked TIME NOT NULL,
                session_id INTEGER REFERENCES attendance_sessions(session_id) ON DELETE SET NULL,
                UNIQUE(student_id, session_id)
            )
        """)
        
        # Create Missed Attendance Requests table
        print("Creating Missed Attendance Requests table...")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS missed_attendance_requests (
                id {id_type},
                student_id INTEGER REFERENCES students(student_id),
                missed_period TEXT NOT NULL,
                detected_period TEXT NOT NULL,
                date DATE NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(student_id, date, missed_period)
            )
        """)
        
        conn.commit()

        # Migration for existing databases
        try:
            cur.execute("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS session_id INTEGER REFERENCES attendance_sessions(session_id) ON DELETE SET NULL")
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[MIGRATION] Note (session_id column): {e}")

        try:
            cur.execute("ALTER TABLE attendance DROP CONSTRAINT IF EXISTS attendance_student_id_date_period_key")
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[MIGRATION] Note (drop constraint): {e}")

        try:
            cur.execute("ALTER TABLE attendance ADD CONSTRAINT attendance_student_session_unique UNIQUE(student_id, session_id)")
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[MIGRATION] Note (add unique constraint): {e}")

        # Create Database Indexes for optimization
        print("Creating Database Indexes...")
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_students_roll ON students(roll_number)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_attendance_session ON attendance(session_id)")
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[MIGRATION] Note (indexes): {e}")

        cur.close()
        conn.close()
        print(f"Database Initialized (Type: {settings.DB_TYPE}).")
        
        # Seed test data for Vinuthna Vasanthi and Vinu
        seed_test_data()

def seed_test_data():
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        try:
            # 1. Seed Vinuthna Vasanthi (roll 0015)
            cur.execute(f"SELECT student_id FROM students WHERE roll_number = {settings.DB_PARAM}", ('0015',))
            if not cur.fetchone():
                cur.execute(f"""
                    INSERT INTO students (name, roll_number, section, phone_number, email, student_code, primary_photo, university, school)
                    VALUES ({settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, 'DSU', 'SET')
                """, ('Vinuthna Vasanthi', '0015', 'B4', '7207631753', 'vinuthna@example.com', 'STU20260015', '/get_photo/0015_Vinuthna_Vasanthi/0015_0.jpeg'))
                print("[SEED] Inserted student Vinuthna Vasanthi (0015)")

            # 2. Seed Vinu (roll 0011)
            cur.execute(f"SELECT student_id FROM students WHERE roll_number = {settings.DB_PARAM}", ('0011',))
            if not cur.fetchone():
                cur.execute(f"""
                    INSERT INTO students (name, roll_number, section, phone_number, email, student_code, primary_photo, university, school)
                    VALUES ({settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, 'DSU', 'SET')
                """, ('Vinu', '0011', 'B4', '8310264770', 'vinu@example.com', 'STU20260011', '/get_photo/0011_vinu/0011_0.jpeg'))
                print("[SEED] Inserted student Vinu (0011)")
            
            # 3. Seed users for student portals
            cur.execute(f"SELECT id FROM users WHERE email = {settings.DB_PARAM}", ('vinuthna@example.com',))
            if not cur.fetchone():
                from werkzeug.security import generate_password_hash
                hashed = generate_password_hash('0015')
                cur.execute(f"INSERT INTO users (name, email, password, role, section) VALUES ({settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, 'student', 'B4')", ('Vinuthna Vasanthi', 'vinuthna@example.com', hashed))
            
            cur.execute(f"SELECT id FROM users WHERE email = {settings.DB_PARAM}", ('vinu@example.com',))
            if not cur.fetchone():
                from werkzeug.security import generate_password_hash
                hashed = generate_password_hash('0011')
                cur.execute(f"INSERT INTO users (name, email, password, role, section) VALUES ({settings.DB_PARAM}, {settings.DB_PARAM}, {settings.DB_PARAM}, 'student', 'B4')", ('Vinu', 'vinu@example.com', hashed))

            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[SEED] Error seeding initial test data: {e}")
        finally:
            cur.close()
            conn.close()

if __name__ == "__main__":
    initialize_database()
