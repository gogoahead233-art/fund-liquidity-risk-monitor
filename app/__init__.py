import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'

# Global data provider instance (set during create_app)
data_provider = None


def create_app(config_name=None):
    app = Flask(__name__)

    # Load configuration
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')

    from app.config import config as config_dict
    app.config.from_object(config_dict[config_name])

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)

    # Initialize data provider
    global data_provider
    provider_type = app.config.get('DATA_PROVIDER', 'csv')
    if provider_type == 'wind':
        try:
            from app.data_provider.wind_provider import WindDataProvider
            data_provider = WindDataProvider()
            app.logger.info('Using Wind data provider')
        except ImportError:
            app.logger.warning('Wind not available, falling back to CSV provider')
            from app.data_provider.csv_provider import CsvDataProvider
            data_provider = CsvDataProvider()
    else:
        from app.data_provider.csv_provider import CsvDataProvider
        data_provider = CsvDataProvider()

    # Register blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)

    from app.warning import bp as warning_bp
    app.register_blueprint(warning_bp, url_prefix='/warning')

    from app.query import bp as query_bp
    app.register_blueprint(query_bp, url_prefix='/query')

    from app.analysis import bp as analysis_bp
    app.register_blueprint(analysis_bp, url_prefix='/analysis')

    from app.data_mgmt import bp as data_mgmt_bp
    app.register_blueprint(data_mgmt_bp, url_prefix='/data')

    # User loader
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Create tables on first request
    with app.app_context():
        db.create_all()

    # Inject static version for cache busting
    @app.context_processor
    def inject_static_version():
        return {'STATIC_VERSION': '1.0.0'}

    return app
