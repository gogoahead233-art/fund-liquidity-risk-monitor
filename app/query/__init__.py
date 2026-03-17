from flask import Blueprint

bp = Blueprint('query', __name__)

from app.query import routes  # noqa: E402, F401
