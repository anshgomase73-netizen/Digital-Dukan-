from flask import Flask
from config import Config
from app.utils import close_db_connection, get_db_connection, get_db_cursor


def create_app(config_class=Config):
    """
    Application Factory for Digital Dukan.
    Initializes Flask application instance, registers teardown handlers,
    configures CORS headers, and registers blueprints.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Automatic database connection teardown per request
    app.teardown_appcontext(close_db_connection)

    # Basic CORS support for API responses
    @app.after_request
    def set_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
        return response

    # Register application blueprints
    from app.routes import main_bp
    app.register_blueprint(main_bp)

    return app


# Default app instance for simple module imports
app = create_app()

__all__ = ['create_app', 'app', 'get_db_connection', 'get_db_cursor']
