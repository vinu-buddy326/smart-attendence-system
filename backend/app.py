import os
import sys
import secrets
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from config import settings
from database.db_connection import get_connection

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    # If in MEIPASS, the paths were flattened or nested depending on spec.
    # We specified 'frontend/templates' so it should be there.
    return os.path.join(base_path, relative_path)

app = Flask(__name__, 
            template_folder=resource_path("../frontend/templates") if not getattr(sys, '_MEIPASS', None) else resource_path("frontend/templates"), 
            static_folder=resource_path("../static") if not getattr(sys, '_MEIPASS', None) else resource_path("static"))
app.secret_key = settings.SECRET_KEY

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, id, name, email, role, section, subjects=None):
        self.id = id
        self.name = name
        self.email = email
        self.role = role
        self.section = section
        self.subjects = subjects

@login_manager.user_loader
def load_user(user_id):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute(f"SELECT id, name, email, role, section, subjects FROM users WHERE id = {settings.DB_PARAM}", (user_id,))
        u = cur.fetchone()
        cur.close()
        conn.close()
        if u:
            return User(*u)
    return None

from backend.routes import register_routes
register_routes(app)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
