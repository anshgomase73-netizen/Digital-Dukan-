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

    # MySQL database connection parameters
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_NAME = os.getenv('DB_NAME', 'digital_dukan')

    # Connection pooling configuration
    DB_POOL_NAME = os.getenv('DB_POOL_NAME', 'digital_dukan_pool')
    DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', 5))

    @classmethod
    def get_db_config(cls, include_db=True):
        """Return database connection parameters as a dictionary."""
        config = {
            'host': cls.DB_HOST,
            'port': cls.DB_PORT,
            'user': cls.DB_USER,
            'password': cls.DB_PASSWORD,
        }
        if include_db and cls.DB_NAME:
            config['database'] = cls.DB_NAME
        return config
