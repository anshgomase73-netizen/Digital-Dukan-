import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file if present
load_dotenv(BASE_DIR / '.env')


class Config:
    """Application configuration loaded from environment variables."""
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'default-dev-secret-key')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')

    # SQLite database configuration
    DB_FILE = os.getenv('DB_FILE', 'digital_dukan.db')
    DB_PATH = Path(os.getenv('DB_PATH', str(BASE_DIR / DB_FILE)))

    # Legacy configuration for backwards compatibility
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    try:
        DB_PORT = int(os.getenv('DB_PORT', '3306'))
    except (ValueError, TypeError):
        DB_PORT = 3306

    try:
        DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '5'))
    except (ValueError, TypeError):
        DB_POOL_SIZE = 5

    @classmethod
    def get_db_config(cls, include_db=True):
        """Return database connection parameters as a dictionary."""
        config = {
            'host': cls.DB_HOST,
            'port': cls.DB_PORT,
            'user': cls.DB_USER,
            'password': cls.DB_PASSWORD,
            'database': cls.DB_NAME if include_db else None,
            'db_path': str(cls.DB_PATH)
        }
        return config
