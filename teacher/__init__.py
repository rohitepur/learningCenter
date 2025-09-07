from flask import Blueprint

teacher_bp = Blueprint("teacher", __name__, url_prefix="/teacher")

# Import routes to register on blueprint
from .blueprint import *  # noqa: E402,F401
