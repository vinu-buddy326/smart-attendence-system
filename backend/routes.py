from flask import render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import login_user, login_required, logout_user, current_user
from database.db_connection import get_connection
from database.student_queries import get_all_students, add_student, get_student_by_id, update_student, delete_student, get_student_by_roll
from database.attendance_queries import get_all_attendance, get_attendance_by_section, get_sections, get_attendance_summary, get_all_attendance_filtered
from database.user_queries import get_all_users, get_user_by_id, create_user, update_user_profile, change_user_password, delete_user, admin_update_user, admin_reset_password
from database.attendance_queries import get_missed_attendance_requests, process_missed_request
from reports.daily_report import generate_excel_report
from functools import wraps
import os
from config import settings
import logging
from werkzeug.security import check_password_hash, generate_password_hash

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash("Admin access required.")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

def staff_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['admin', 'mentor']:
            flash("Staff access required. Redirecting to student portal.")
            return redirect(url_for('student_portal'))
        return f(*args, **kwargs)
    return decorated

def register_routes(app):
    # Simple logger for routes (can be extended by main logger config)
    logger = logging.getLogger(__name__)

    @app.route("/")
    def index():
        return redirect(url_for('login'))

    @app.route("/login", methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            role = request.form.get('role', 'student') # Default to student
            
            conn = get_connection()
            if not conn:
                flash("Database connection error. Please verify database server status and try again.")
                return render_template("login.html")
            cur = conn.cursor()
            cur.execute(f"SELECT id, name, email, password, role, section, subjects FROM users WHERE email = {settings.DB_PARAM} AND role = {settings.DB_PARAM}", (email, role))
            user_data = cur.fetchone()
            cur.close()
            conn.close()
            
            if user_data and check_password_hash(user_data[3], password):
                from backend.app import User
                u = User(user_data[0], user_data[1], user_data[2], user_data[4], user_data[5], user_data[6])
                login_user(u)
                return redirect(url_for('dashboard'))
            else:
                flash("Invalid credentials or role mismatch.")
        return render_template("login.html")

    @app.route("/student/update_section", methods=['POST'])
    @login_required
    def student_update_section():
        if current_user.role != 'student': return redirect(url_for('dashboard'))
        
        new_section = request.form.get('section')
        if not new_section:
            flash("Section cannot be empty.")
            return redirect(url_for('student_portal'))
            
        try:
            conn = get_connection()
            cur = conn.cursor()
            # Update students table
            cur.execute(f"UPDATE students SET section = {settings.DB_PARAM} WHERE email = {settings.DB_PARAM}", (new_section, current_user.email))
            # Update users table (since we synced them)
            cur.execute(f"UPDATE users SET section = {settings.DB_PARAM} WHERE email = {settings.DB_PARAM}", (new_section, current_user.email))
            conn.commit()
            cur.close()
            conn.close()
            # Update current_user object in session
            current_user.section = new_section
            flash("Section updated successfully!", "success")
        except Exception as e:
            flash(f"Error updating section: {e}", "error")
            
        return redirect(url_for('student_portal'))
    @app.route("/register_student", methods=['GET', 'POST'])
    def register_student():
        import os
        from werkzeug.utils import secure_filename
        from reports.id_card_generator import create_student_id_card
        
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            roll_number = request.form.get('roll_number', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            section = request.form.get('section', '').strip()
            university = request.form.get('university', '').strip()
            school = request.form.get('school', '').strip()
            
            photos = request.files.getlist('photos')
            if len(photos) != 5:
                flash("Exactly 5 photos are required for biometric registration.", "error")
                return redirect(url_for('register_student'))

            # Basic Validation
            import re
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                flash("Invalid email format.", "error")
                return redirect(url_for('register_student'))
            
            # Create unique student code based on year and roll number
            from datetime import datetime
            import random
            student_code = f"STU{datetime.now().year}{random.randint(1000, 9999)}"
            
            # Save photos temporarily to validate
            temp_dir = os.path.join("datasets", "temp", f"{roll_number}")
            os.makedirs(temp_dir, exist_ok=True)
            
            from ai_engine.camera_stream import stream
            face_ai = stream.face_engine
            
            saved_photo_paths = []
            for i, photo in enumerate(photos):
                if photo.filename:
                    ext = os.path.splitext(photo.filename)[1].lower() or ".jpg"
                    filepath = os.path.join(temp_dir, f"test_{i}{ext}")
                    photo.save(filepath)
                    
                    is_valid, msg = face_ai.validate_image(filepath)
                    if not is_valid:
                        import shutil
                        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
                        flash(f"Photo {i+1} verification failed: {msg}", "error")
                        return redirect(url_for('register_student'))
                    
                    saved_photo_paths.append(filepath)

            if len(saved_photo_paths) != 5:
                # Clean up if any
                import shutil
                if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
                flash("Could not process all 5 photos. Please use valid JPG/PNG files.", "error")
                return redirect(url_for('register_student'))

            # Move from temp to permanent
            dataset_dir = os.path.join("datasets", "faces", f"{roll_number}_{name.replace(' ','_')}")
            os.makedirs(dataset_dir, exist_ok=True)
            final_photo_paths = []
            for filepath in saved_photo_paths:
                dest = os.path.join(dataset_dir, os.path.basename(filepath).replace("test_", f"{roll_number}_"))
                os.replace(filepath, dest)
                final_photo_paths.append(dest)
            
            # Clean up temp
            import shutil
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
                
            primary_photo = final_photo_paths[0]
            
            # Generate ID Card
            student_data = {
                "name": name,
                "roll_number": roll_number,
                "student_code": student_code,
                "section": section,
                "phone": phone,
                "email": email,
                "university": university,
                "school": school
            }
            urls = create_student_id_card(student_data, primary_photo)
            
            # Save to Database
            res = add_student(name, roll_number, section, phone, email=email, student_code=student_code, primary_photo=f"/get_photo/{roll_number}_{name.replace(' ','_')}/{os.path.basename(primary_photo)}", id_card_url=urls['pdf_url'], university=university, school=school)
            
            if res == "success":
                import cv2
                from database.student_queries import save_student_embedding
                # Get the student_id
                student = get_student_by_roll(roll_number)
                if student:
                    student_id = student[0]
                    # Generate and save embedding for each final photo
                    for filepath in final_photo_paths:
                        try:
                            image = cv2.imread(filepath)
                            if image is not None:
                                h, w, _ = image.shape
                                face_ai.detector.setInputSize((w, h))
                                _, faces = face_ai.detector.detect(image)
                                if faces is not None and len(faces) > 0:
                                    aligned_face = face_ai.recognizer.alignCrop(image, faces[0])
                                    feature = face_ai.recognizer.feature(aligned_face)
                                    save_student_embedding(student_id, feature.tobytes())
                        except Exception as e:
                            print(f"[AI] Error generating embedding: {e}")
                
                # 1. Trigger AI Reload
                try:
                    stream.reload_ai()
                except Exception as e:
                    print(f"[AI] Error reloading signatures: {e}")

                # 2. Mark First Attendance (as requested)
                try:
                    from database.attendance_queries import mark_attendance
                    mark_attendance(roll_number) # Use roll_number or student_id? The engine uses roll_number
                except: pass

                # 3. Create Automated User Profile for Student Login
                # Default password is the Roll Number for initial setup
                from database.user_queries import create_user
                create_user(name, email, roll_number, "student", section)

                flash(f"Success! Your Digital ID is ready. <a href='{urls['pdf_url']}' target='_blank' style='color: var(--success); font-weight: bold;'>Download ID Card</a><br>You can now login using your Email and Roll Number as password.", "success")
            else:
                msg = f"Failed to register: {res}"
                if "UNIQUE constraint" in str(res):
                    msg = "Error: This Roll Number is already registered. Please login or contact support."
                flash(msg, "error")
            return redirect(url_for('register_student'))
            
        return render_template("register_student.html")

    @app.route('/get_photo/<path:filename>')
    def get_photo(filename):
        from flask import send_from_directory
        return send_from_directory(os.path.join(os.getcwd(), 'datasets', 'faces'), filename)


    @app.route("/dashboard")
    @login_required
    def dashboard():
        from database.attendance_queries import get_daily_stats
        if current_user.role == 'admin':
            students = get_all_students()
            stats = get_daily_stats()
            return render_template("admin_dashboard.html", students=students, stats=stats)
        elif current_user.role == 'mentor':
            students = get_all_students(section=current_user.section)
            stats = get_daily_stats(section=current_user.section)
            attendance = get_attendance_by_section(current_user.section)
            missed_requests = get_missed_attendance_requests(section=current_user.section)
            return render_template("mentor_dashboard.html", students=students, attendance=attendance, stats=stats, missed_requests=missed_requests)
        else:
            return redirect(url_for('student_portal'))

    @app.route("/student_portal")
    @login_required
    def student_portal():
        if current_user.role != 'student':
            return redirect(url_for('dashboard'))
        
        from database.student_queries import get_student_by_email
        student = get_student_by_email(current_user.email)
        
        if not student:
            flash("Student profile not found.")
            return redirect(url_for('logout'))
            
        from database.attendance_queries import get_student_attendance, get_student_missed_requests
        attendance = get_student_attendance(student[2]) # student[2] is roll_number
        missed = get_student_missed_requests(student[0]) # student[0] is student_id
        return render_template("student_portal.html", student=student, attendance=attendance, missed=missed)

    @app.route("/student/update_profile", methods=['POST'])
    @login_required
    def student_update_profile():
        if current_user.role != 'student':
            flash("Unauthorized access.", "error")
            return redirect(url_for('login'))
            
        section = request.form.get('section', '').strip()
        university = request.form.get('university', '').strip()
        school = request.form.get('school', '').strip()

        from database.student_queries import update_student, get_student_by_email
        
        student = get_student_by_email(current_user.email)
        if student:
            res = update_student(student[0], student[1], section, student[4], student[5], university=university, school=school)
            if res == "success":
                try:
                    current_user.section = section
                except Exception:
                    pass
                flash("Profile updated successfully!", "success")
            else:
                flash(f"Failed to update profile: {res}", "error")
        else:
            flash("Student profile not found.", "error")
            
        return redirect(url_for('student_portal'))

    # ─────────────────────────────────────────────
    # Live AI Camera Stream Endpoint
    # ─────────────────────────────────────────────

    @app.route("/video_feed")
    @login_required
    def video_feed():
        from ai_engine.camera_stream import stream
        from flask import Response
        
        # Start stream if not running
        stream.start()

        def generate():
            while True:
                frame = stream.get_frame()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

    @app.route("/video_feed_login")
    def video_feed_login():
        from ai_engine.camera_stream import stream
        from flask import Response
        
        # Start stream if not running
        stream.start()

        def generate():
            while True:
                frame = stream.get_frame()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

    @app.route("/api/live_status")
    def api_live_status():
        from ai_engine.camera_stream import stream
        return jsonify(stream.current_recognition_status)

    @app.route("/api/end_session", methods=['POST'])
    @login_required
    @staff_required
    def api_end_session():
        from database.attendance_queries import end_active_session
        res = end_active_session()
        if res == "success":
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "message": res}), 400

    @app.route("/api/check_face_login_status")
    def api_check_face_login_status():
        from ai_engine.camera_stream import stream
        roll = stream.last_recognized_roll
        if roll:
            from database.student_queries import get_student_by_roll
            student = get_student_by_roll(roll)
            user_data = None

            if student:
                email = student[5]
                name = student[1]
                roll_num = student[2]
                section = student[3]
                
                if not email:
                    email = f"{roll_num.lower()}@student.local"

                conn = get_connection()
                if conn:
                    cur = conn.cursor()
                    cur.execute(f"SELECT id, name, email, password, role, section, subjects FROM users WHERE LOWER(email) = LOWER({settings.DB_PARAM})", (email,))
                    user_data = cur.fetchone()
                    cur.close()
                    conn.close()

                # If user doesn't exist in users table, auto-create student account
                if not user_data:
                    from database.user_queries import create_user
                    create_user(name, email, roll_num, "student", section)
                    conn = get_connection()
                    if conn:
                        cur = conn.cursor()
                        cur.execute(f"SELECT id, name, email, password, role, section, subjects FROM users WHERE LOWER(email) = LOWER({settings.DB_PARAM})", (email,))
                        user_data = cur.fetchone()
                        cur.close()
                        conn.close()

            if not user_data:
                # Direct check in users table by email or name
                conn = get_connection()
                if conn:
                    cur = conn.cursor()
                    cur.execute(f"SELECT id, name, email, password, role, section, subjects FROM users WHERE LOWER(email) = LOWER({settings.DB_PARAM}) OR LOWER(name) LIKE LOWER({settings.DB_PARAM})", (roll, f"%{roll}%"))
                    user_data = cur.fetchone()
                    cur.close()
                    conn.close()

            if user_data:
                stream.last_recognized_roll = None
                from backend.app import User
                u = User(user_data[0], user_data[1], user_data[2], user_data[4], user_data[5], user_data[6])
                login_user(u)
                return jsonify({"status": "success", "redirect": url_for('dashboard')})

        return jsonify({"status": "pending"})

    # ─────────────────────────────────────────────
    # Student Management Routes (Admin Only)
    # ─────────────────────────────────────────────

    @app.route("/students")
    @login_required
    @staff_required
    def students_page():
        # Admins see all; mentors see only their section
        if current_user.role == 'admin':
            students = get_all_students()
        else:
            students = get_all_students(section=current_user.section)
        return render_template("students.html", students=students)

    @app.route("/students/add", methods=['POST'])
    @login_required
    @admin_required
    def student_add():  # Add stays admin-only
        name        = request.form.get('name', '').strip()
        roll_number = request.form.get('roll_number', '').strip()
        section     = request.form.get('section', '').strip()
        phone       = request.form.get('phone_number', '').strip()
        email       = request.form.get('email', '').strip()
        university  = request.form.get('university', '').strip()
        school      = request.form.get('school', '').strip()

        if not name or not roll_number or not section:
            flash("Name, Roll Number, and Section are required.", "error")
            return redirect(url_for('students_page'))

        from datetime import datetime
        import random
        student_code = f"STU{datetime.now().year}{random.randint(1000, 9999)}"

        result = add_student(name, roll_number, section, phone, email=email, student_code=student_code, university=university, school=school)
        if result == "success":
            flash(f"Student '{name}' added successfully!", "success")
        else:
            flash(f"Could not add student: {result}", "error")
        return redirect(url_for('students_page'))

    @app.route("/students/edit/<int:student_id>", methods=['GET', 'POST'])
    @login_required
    def student_edit(student_id):  # Both admin and mentor can edit
        student = get_student_by_id(student_id)
        if not student:
            flash("Student not found.", "error")
            return redirect(url_for('students_page'))

        if request.method == 'POST':
            name         = request.form.get('name', '').strip()
            section      = request.form.get('section', '').strip()
            phone_number = request.form.get('phone_number', '').strip()
            email        = request.form.get('email', '').strip()
            university   = request.form.get('university', '').strip()
            school       = request.form.get('school', '').strip()

            if not name or not section:
                flash("Name and Section are required.", "error")
                return redirect(url_for('student_edit', student_id=student_id))

            result = update_student(student_id, name, section, phone_number, email=email, university=university, school=school)
            if result == "success":
                flash("Student profile updated successfully!", "success")
                return redirect(url_for('students_page'))
            else:
                flash(f"Error updating student: {result}", "error")

        return render_template("student_edit.html", student=student)

    @app.route("/students/regenerate_id/<int:student_id>", methods=['POST'])
    @login_required
    @admin_required
    def student_regenerate_id(student_id):
        from reports.id_card_generator import create_student_id_card
        student = get_student_by_id(student_id)
        if not student:
            flash("Student not found.", "error")
            return redirect(url_for('students_page'))
            
        # We need the primary photo path. It's stored as /get_photo/...
        # We need to map it back to the local path or use the raw path if available.
        # student[7] is /get_photo/ROLL_NAME/filename.ext
        photo_url = student[7]
        if photo_url and photo_url.startswith('/get_photo/'):
            parts = photo_url.split('/')
            relative_path = os.path.join(*parts[2:]) # Skip empty and get_photo
            primary_photo = os.path.join("datasets", "faces", relative_path)
        else:
            flash("Cannot regenerate ID: No primary photo found.", "error")
            return redirect(url_for('student_edit', student_id=student_id))

        student_data = {
            "name": student[1],
            "roll_number": student[2],
            "student_code": student[6],
            "section": student[3],
            "phone": student[4],
            "email": student[5]
        }
        
        try:
            urls = create_student_id_card(student_data, primary_photo)
            # Update database
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(f"UPDATE students SET id_card_url = {settings.DB_PARAM} WHERE student_id = {settings.DB_PARAM}", (urls['pdf_url'], student_id))
            conn.commit()
            cur.close()
            conn.close()
            flash("Digital ID Card regenerated successfully!", "success")
        except Exception as e:
            flash(f"Error regenerating ID: {e}", "error")
            
        return redirect(url_for('student_edit', student_id=student_id))

    @app.route("/students/delete/<int:student_id>", methods=['POST'])
    @login_required
    @admin_required
    def student_delete(student_id):
        student = get_student_by_id(student_id)
        if student:
            result = delete_student(student_id)
            if result == "success":
                flash(f"Student '{student[1]}' removed.", "success")
            else:
                flash(f"Delete failed: {result}", "error")
        else:
            flash("Student not found.", "error")
        return redirect(url_for('students_page'))

    # ─────────────────────────────────────────────
    # Reports
    # ─────────────────────────────────────────────

    @app.route("/reports")
    @login_required
    @staff_required
    def reports():
        from datetime import date as dt_date
        date_str = request.args.get('date', '')
        section  = request.args.get('section', '')

        if current_user.role != 'admin':
            section = current_user.section

        try:
            filter_date = dt_date.fromisoformat(date_str) if date_str else dt_date.today()
        except ValueError:
            filter_date = dt_date.today()

        section_filter = section if section else None

        if section_filter:
            attendance_data = get_all_attendance_filtered(filter_date=filter_date, section=section_filter)
        elif current_user.role == 'admin':
            attendance_data = get_all_attendance_filtered(filter_date=filter_date)
        else:
            attendance_data = get_all_attendance_filtered(filter_date=filter_date, section=current_user.section)

        sections = get_sections() if current_user.role == 'admin' else []

        return render_template("reports.html",
            attendance=attendance_data,
            sections=sections,
            selected_date=filter_date.isoformat(),
            selected_section=section,
            total_records=len(attendance_data),
        )

    @app.route("/download_report")
    @login_required
    def download_report():
        from datetime import date as dt_date, timedelta
        from database.attendance_queries import get_attendance_by_range
        
        report_type = request.args.get('type', 'daily') # daily, weekly, monthly
        date_str = request.args.get('date', '')
        section  = request.args.get('section', '')
        
        if current_user.role != 'admin':
            section = current_user.section
            
        try:
            target_date = dt_date.fromisoformat(date_str) if date_str else dt_date.today()
        except ValueError:
            target_date = dt_date.today()
            
        start_date = target_date
        end_date = target_date
        
        if report_type == 'weekly':
            # Last 7 days including today
            start_date = target_date - timedelta(days=6)
        elif report_type == 'monthly':
            # Last 30 days including today
            start_date = target_date - timedelta(days=29)

        section_filter = section if section else None
        
        if report_type == 'daily':
            data = get_all_attendance_filtered(filter_date=target_date, section=section_filter)
            filepath = generate_excel_report(data, target_date, section_filter)
        else:
            data = get_attendance_by_range(start_date, end_date, section=section_filter)
            filepath = generate_excel_report(data, section=section_filter, start_date=start_date, end_date=end_date)
            
        return send_file(filepath, as_attachment=True)

    @app.route("/download_pdf")
    @login_required
    def download_pdf():
        from datetime import date as dt_date
        from reports.daily_report import generate_pdf_report
        date_str = request.args.get('date', '')
        section  = request.args.get('section', '')
        if current_user.role != 'admin':
            section = current_user.section
        try:
            filter_date = dt_date.fromisoformat(date_str) if date_str else dt_date.today()
        except ValueError:
            filter_date = dt_date.today()
        section_filter = section if section else None
        summary = get_attendance_summary(filter_date, section_filter)
        try:
            filepath = generate_pdf_report(summary, filter_date, section_filter)
            return send_file(filepath, as_attachment=True, mimetype='application/pdf')
        except Exception as e:
            flash(f"PDF generation failed: {e}. Try installing reportlab: pip install reportlab", "error")
            return redirect(url_for('reports'))


    @app.route("/logout")
    def logout():
        logout_user()
        return redirect(url_for('login'))

    @app.route("/health")
    def health():
        """
        Lightweight health-check: DB connectivity + (optional) camera status.
        Returns JSON: {status: 'ok'|'degraded'|'error', details: {...}}
        """
        db_ok = False
        try:
            conn = get_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.fetchone()
                cur.close()
                conn.close()
                db_ok = True
        except Exception as e:
            logger.error(f"Health DB check failed: {e}")

        camera_status = "unknown"
        try:
            from ai_engine.camera_stream import stream
            camera_status = "running" if stream.is_running else "stopped"
        except Exception:
            camera_status = "unavailable"

        overall = "ok" if db_ok else "error"
        return jsonify({
            "status": overall,
            "db": "ok" if db_ok else "error",
            "camera": camera_status,
        })

    # ─────────────────────────────────────────────
    # Attendance Dashboard (real-time)
    # ─────────────────────────────────────────────

    @app.route("/attendance")
    @login_required
    @staff_required
    def attendance_dashboard():
        from datetime import date as dt_date
        # Read filters from query string
        date_str  = request.args.get('date', '')
        section   = request.args.get('section', '')

        # Restrict mentors to their section
        if current_user.role != 'admin':
            section = current_user.section

        # Parse date
        try:
            filter_date = dt_date.fromisoformat(date_str) if date_str else dt_date.today()
        except ValueError:
            filter_date = dt_date.today()

        section_filter = section if section else None

        summary  = get_attendance_summary(filter_date, section_filter)
        sections = get_sections() if current_user.role == 'admin' else []
        stats    = {
            "total":   len(summary),
            "present": sum(1 for s in summary if s[7] == 1),
            "date":    filter_date.strftime("%d %b %Y"),
        }
        stats["absent"] = stats["total"] - stats["present"]
        stats["pct"] = round((stats["present"] / stats["total"]) * 100, 1) if stats["total"] else 0

        return render_template(
            "attendance.html",
            summary=summary,
            sections=sections,
            selected_section=section,
            selected_date=filter_date.isoformat(),
            stats=stats,
        )

    @app.route("/api/attendance_summary")
    @login_required
    def api_attendance_summary():
        from datetime import date as dt_date
        date_str = request.args.get("date", "")
        section = request.args.get("section", "")

        if current_user.role != "admin":
            section = current_user.section

        try:
            filter_date = dt_date.fromisoformat(date_str) if date_str else dt_date.today()
        except ValueError:
            filter_date = dt_date.today()

        section_filter = section if section else None
        summary = get_attendance_summary(filter_date, section_filter)

        stats = {
            "total": len(summary),
            "present": sum(1 for s in summary if s[7] == 1),
            "date": filter_date.isoformat(),
            "section": section if section else "",
        }
        stats["absent"] = stats["total"] - stats["present"]
        stats["pct"] = round((stats["present"] / stats["total"]) * 100, 1) if stats["total"] else 0

        # s = (id, name, roll, section, phone, periods_present, total_periods, is_present, pct)
        payload = [
            {
                "student_id": s[0],
                "name": s[1],
                "roll_number": s[2],
                "section": s[3],
                "phone_number": s[4],
                "periods_present": s[5],
                "total_periods": s[6],
                "is_present": int(s[7]),
                "pct": float(s[8]),
            }
            for s in summary
        ]
        return jsonify({"stats": stats, "summary": payload})

    @app.route("/api/mentor_today_logs")
    @login_required
    def api_mentor_today_logs():
        from datetime import date as dt_date
        if current_user.role not in ("mentor", "admin"):
            return jsonify({"error": "forbidden"}), 403

        section = request.args.get("section", "")
        if current_user.role != "admin":
            section = current_user.section
        if not section:
            return jsonify({"error": "section required"}), 400

        try:
            logs = get_attendance_by_section(section, date=dt_date.today())
            # rec = (name, roll, period, time_marked, status)
            payload = [
                {
                    "name": r[0],
                    "roll_number": r[1],
                    "period": r[2],
                    "time_marked": r[3].strftime("%H:%M:%S") if hasattr(r[3], "strftime") else str(r[3]),
                    "status": r[4],
                }
                for r in logs
            ]
            return jsonify({"section": section, "count": len(payload), "logs": payload})
        except Exception as e:
            print(f"[API ERROR] mentor_today_logs: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500


    # ─────────────────────────────────────────────
    # Missed Attendance Requests
    # ─────────────────────────────────────────────
    
    @app.route("/api/process_missed_request/<int:req_id>", methods=['POST'])
    @login_required
    def api_process_missed_request(req_id):
        if current_user.role not in ('admin', 'mentor'):
            return jsonify({"error": "Unauthorized"}), 403
            
        action = request.json.get('action')
        if action not in ('approved', 'rejected'):
            return jsonify({"error": "Invalid action"}), 400
            
        res = process_missed_request(req_id, action)
        if res == "success":
            return jsonify({"status": "success"})
        return jsonify({"error": res}), 400


    # ─────────────────────────────────────────────
    # Admin: Edit User Profile
    # ─────────────────────────────────────────────

    @app.route("/users/edit/<int:user_id>", methods=['GET', 'POST'])
    @login_required
    @admin_required
    def user_edit(user_id):
        user = get_user_by_id(user_id)
        if not user:
            flash("User not found.", "error")
            return redirect(url_for('users_page'))

        if request.method == 'POST':
            name    = request.form.get('name', '').strip()
            email   = request.form.get('email', '').strip()
            role    = request.form.get('role', 'mentor').strip()
            section = request.form.get('section', '').strip()
            
            # Handle 4 subjects
            s1 = request.form.get('subject_1', '').strip()
            s2 = request.form.get('subject_2', '').strip()
            s3 = request.form.get('subject_3', '').strip()
            s4 = request.form.get('subject_4', '').strip()
            subjects = ", ".join([s for s in [s1, s2, s3, s4] if s]) or None

            result = admin_update_user(user_id, name, email, role, section, subjects)
            if result == "success":
                # Sync logic for students if needed
                if role == 'student':
                    from database.db_connection import get_connection
                    conn = get_connection()
                    if conn:
                        cur = conn.cursor()
                        cur.execute(f"UPDATE students SET name = {settings.DB_PARAM}, section = {settings.DB_PARAM} WHERE email = {settings.DB_PARAM}", (name, section, email))
                        conn.commit(); cur.close(); conn.close()
                
                flash(f"User '{name}' updated successfully!", "success")
            else:
                flash(f"Update failed: {result}", "error")
            return redirect(url_for('users_page'))

        return render_template("user_edit.html", user=user)

    @app.route("/users/reset-password/<int:user_id>", methods=['POST'])
    @login_required
    @admin_required
    def user_reset_password(user_id):
        if user_id == current_user.id:
            flash("Use 'Change Password' on your profile page instead.", "error")
            return redirect(url_for('users_page'))
        new_pw = request.form.get('new_password', '').strip()
        if len(new_pw) < 6:
            flash("Password must be at least 6 characters.", "error")
            return redirect(url_for('user_edit', user_id=user_id))
        result = admin_reset_password(user_id, new_pw)
        if result == "success":
            flash("Password reset successfully!", "success")
        else:
            flash(f"Reset failed: {result}", "error")
        return redirect(url_for('users_page'))

    # ─────────────────────────────────────────────
    # Profile Routes (All logged-in users)
    # ─────────────────────────────────────────────

    @app.route("/profile", methods=['GET', 'POST'])
    @login_required
    def profile():
        if request.method == 'POST':
            name     = request.form.get('name', '').strip()
            # Admins keep their section null or as-is; others can update
            section  = request.form.get('section', '').strip() if current_user.role != 'admin' else current_user.section
            
            if current_user.role != 'student':
                # Handle 4 subjects
                s1 = request.form.get('subject_1', '').strip()
                s2 = request.form.get('subject_2', '').strip()
                s3 = request.form.get('subject_3', '').strip()
                s4 = request.form.get('subject_4', '').strip()
                subjects = ", ".join([s for s in [s1, s2, s3, s4] if s]) or None
            else:
                subjects = None
            
            result  = update_user_profile(current_user.id, name, section, subjects)
            if result == "success":
                # Update current_user in session immediately
                current_user.name = name
                current_user.section = section
                current_user.subjects = subjects
                
                # If it's a student, sync name with students table
                if current_user.role == 'student':
                    from database.db_connection import get_connection
                    conn = get_connection()
                    if conn:
                        cur = conn.cursor()
                        cur.execute(f"UPDATE students SET name = {settings.DB_PARAM}, section = {settings.DB_PARAM} WHERE email = {settings.DB_PARAM}", (name, section, current_user.email))
                        conn.commit(); cur.close(); conn.close()

                flash("Profile updated successfully!", "success")
            else:
                flash(f"Update failed: {result}", "error")
            return redirect(url_for('profile'))
        user = get_user_by_id(current_user.id)
        return render_template("profile.html", user=user)

    @app.route("/change-password", methods=['POST'])
    @login_required
    def change_password():
        current_pw  = request.form.get('current_password', '')
        new_pw      = request.form.get('new_password', '')
        confirm_pw  = request.form.get('confirm_password', '')

        if new_pw != confirm_pw:
            flash("New passwords do not match.", "error")
            return redirect(url_for('profile'))
        if len(new_pw) < 6:
            flash("Password must be at least 6 characters.", "error")
            return redirect(url_for('profile'))

        result = change_user_password(current_user.id, current_pw, new_pw)
        if result == "success":
            flash("Password changed successfully!", "success")
        elif "incorrect" in result:
            flash("Current password is wrong. Please try again.", "error")
        else:
            flash(f"Error: {result}", "error")
        return redirect(url_for('profile'))

    # ─────────────────────────────────────────────
    # User Management Routes (Admin Only)
    # ─────────────────────────────────────────────

    @app.route("/users")
    @login_required
    @admin_required
    def users_page():
        users = get_all_users()
        return render_template("users.html", users=users)

    @app.route("/admin/mentor_academic_works")
    @login_required
    @admin_required
    def mentor_academic_works():
        # Fetch all mentors
        conn = get_connection()
        mentors = []
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT name, subjects, section FROM users WHERE role = 'mentor' ORDER BY name")
            mentors = cur.fetchall()
            cur.close()
            conn.close()
        else:
            flash("Database connection error. Could not retrieve mentor list.", "error")
        return render_template("mentor_academic_works.html", mentors=mentors)

    @app.route("/users/add", methods=['POST'])
    @login_required
    @admin_required
    def user_add():
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role     = request.form.get('role', 'mentor').strip()
        section  = request.form.get('section', '').strip() or None
        
        # Handle 4 subjects
        s1 = request.form.get('subject_1', '').strip()
        s2 = request.form.get('subject_2', '').strip()
        s3 = request.form.get('subject_3', '').strip()
        s4 = request.form.get('subject_4', '').strip()
        subjects = ", ".join([s for s in [s1, s2, s3, s4] if s]) or None

        if not name or not email or not password:
            flash("Name, email and password are required.", "error")
            return redirect(url_for('users_page'))

        result = create_user(name, email, password, role, section, subjects)
        if result == "success":
            flash(f"User '{name}' created!", "success")
        else:
            flash("Could not create user. Email may already exist.", "error")
        return redirect(url_for('users_page'))

    @app.route("/users/delete/<int:user_id>", methods=['POST'])
    @login_required
    @admin_required
    def user_delete(user_id):
        if user_id == current_user.id:
            flash("You cannot delete your own account.", "error")
            return redirect(url_for('users_page'))
        user = get_user_by_id(user_id)
        if user:
            result = delete_user(user_id)
            if result == "success":
                flash(f"User '{user[1]}' deleted.", "success")
            else:
                flash(f"Delete failed: {result}", "error")
        else:
            flash("User not found.", "error")
        return redirect(url_for('users_page'))
