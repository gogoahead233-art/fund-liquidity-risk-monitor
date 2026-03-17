from flask import Blueprint

bp = Blueprint('warning', __name__)

from app.warning import routes  # noqa: E402, F401
