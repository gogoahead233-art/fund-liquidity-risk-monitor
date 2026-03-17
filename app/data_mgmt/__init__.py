from flask import Blueprint

bp = Blueprint('data_mgmt', __name__)

from app.data_mgmt import routes  # noqa: E402, F401
