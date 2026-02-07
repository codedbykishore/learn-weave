import logging
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

# Load environment variables from .env file
load_dotenv()

# CRITICAL: Set Google Cloud environment variables IMMEDIATELY for Vertex AI
# These must be set before any Google imports happen
GOOGLE_GENAI_USE_VERTEXAI = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

if GOOGLE_GENAI_USE_VERTEXAI:
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = GOOGLE_GENAI_USE_VERTEXAI
if GOOGLE_CLOUD_PROJECT:
    os.environ["GOOGLE_CLOUD_PROJECT"] = GOOGLE_CLOUD_PROJECT
if GOOGLE_CLOUD_LOCATION:
    os.environ["GOOGLE_CLOUD_LOCATION"] = GOOGLE_CLOUD_LOCATION


# Configuration for the application
# Password policy
# These settings are used to enforce password complexity requirements
MIN_PASSWORD_LENGTH = 3
REQUIRE_UPPERCASE = False
REQUIRE_LOWERCASE = False
REQUIRE_DIGIT = False
REQUIRE_SPECIAL_CHAR = False
SPECIAL_CHARACTERS_REGEX_PATTERN = r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?~`]"

# FREE TEER SETTINGS

MAX_COURSE_CREATIONS = 10
MAX_CHAT_USAGE = 100
MAX_PRESENT_COURSES = 5



# JWT settings
ALGORITHM = "HS256"
SECRET_KEY = os.getenv("SECRET_KEY", "a_very_secret_key_please_change_me")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "fallback-key-for-dev")


######
#ALGORITHM: str = "RS256"
#### Private Key (zum Signieren)
# openssl genrsa -out private.pem 2048
#### Public Key (zum Verifizieren)
# openssl rsa -in private.pem -pubout -out public.pem
PUBLIC_KEY: str = os.getenv("PUBLIC_KEY", "")
PRIVATE_KEY: str =  os.getenv("PRIVATE_KEY", "")
######


ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "20"))
REFRESH_TOKEN_EXPIRE_MINUTES = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "360000")) # 100h
SECURE_COOKIE = os.getenv("SECURE_COOKIE", "true").lower() == "true"


# Database settings (MySQL)
DB_USER = os.getenv("DB_USER", "learnweave_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "your_db_password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306") # Default MySQL port
DB_NAME = os.getenv("DB_NAME", "learnweave_db")

# Use MySQL with pymysql (synchronous driver) for standard SQLAlchemy - URL encode password to handle special characters
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Use MySQL with aiomysql (async driver) for Google ADK DatabaseSessionService
SQLALCHEMY_ASYNC_DATABASE_URL = f"mysql+aiomysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
# For SQLite (testing): # SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

# DB Pooling Settings
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", 3600))
DB_POOL_PRE_PING = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 5))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", 10))
DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", 10))  # Optional


# Google OAuth settings
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "https://www.learnweave.ai/api/google/callback")
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "https://www.learnweave.ai/google/callback")

# Note: GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION are set at the top of this file

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "https://www.learnweave.ai/api/github/callback")

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "https://www.learnweave.ai/api/discord/callback")


CHROMA_DB_URL = os.getenv("CHROMA_DB_URL", "http://localhost:8001")

# Default fallback image for courses/chapters when generation fails
DEFAULT_COURSE_IMAGE = "https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8?w=800&q=80"

AGENT_DEBUG_MODE = os.getenv("AGENT_DEBUG_MODE", "true").lower() == "true"