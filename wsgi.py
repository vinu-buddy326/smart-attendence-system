from logging_config import setup_logging
from backend.app import app as application

# Ensure logging is configured when running under WSGI/Waitress
setup_logging()

