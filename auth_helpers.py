from functools import wraps
from flask import abort
try:
    from flask_login import current_user, login_required
    HAVE_FLASK_LOGIN = True
except Exception:
    HAVE_FLASK_LOGIN = False
    current_user = None

def teacher_required(fn):
    """
    Requires user.role in ("teacher", "admin") if Flask-Login is installed.
    If Flask-Login isn't available, this becomes a no-op (open access).
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if HAVE_FLASK_LOGIN:
            # Ensure user is logged in
            protected = login_required(lambda: None)
            resp = protected()
            if resp is not None:
                return resp  # redirects to login, if configured

            role = getattr(current_user, "role", None)
            if role not in ("teacher", "admin"):
                return abort(403)
        return fn(*args, **kwargs)
    return wrapper
