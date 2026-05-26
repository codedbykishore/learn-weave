import logging
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

# Load environment variables from .env file
load_dotenv()

# LLM provider configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

# CRITICAL: Set Google Cloud environment variables IMMEDIATELY for Vertex AI
# These must be set before any Google imports happen when using Gemini/Vertex.
GOOGLE_GENAI_USE_VERTEXAI = os.getenv(
    "GOOGLE_GENAI_USE_VERTEXAI",
    "true" if LLM_PROVIDER in {"gemini", "google", "vertex"} else "false",
)
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

if LLM_PROVIDER in {"gemini", "google", "vertex"} and GOOGLE_GENAI_USE_VERTEXAI.lower() == "true":
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = GOOGLE_GENAI_USE_VERTEXAI
if GOOGLE_CLOUD_PROJECT:
    os.environ["GOOGLE_CLOUD_PROJECT"] = GOOGLE_CLOUD_PROJECT
if GOOGLE_CLOUD_LOCATION:
    os.environ["GOOGLE_CLOUD_LOCATION"] = GOOGLE_CLOUD_LOCATION

# AWS region defaults for Bedrock/S3 deployments.
AWS_REGION = os.getenv("AWS_REGION", os.getenv("BEDROCK_REGION", "us-east-1"))


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


# Detect Cloud Run environment
CLOUD_RUN_SERVICE = os.getenv("K_SERVICE")  # Set by Cloud Run
IS_CLOUD_RUN = CLOUD_RUN_SERVICE is not None
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")
PUBLIC_FRONTEND_URL = os.getenv("PUBLIC_FRONTEND_URL")

# Database Configuration - Use Firestore in Cloud Run, MySQL for local dev
USE_FIRESTORE = os.getenv("USE_FIRESTORE", "false").lower() == "true"

if USE_FIRESTORE:
    # Firestore configuration
    FIRESTORE_DATABASE = os.getenv("FIRESTORE_DATABASE", "(default)")
    SQLALCHEMY_DATABASE_URL = None
    SQLALCHEMY_ASYNC_DATABASE_URL = None
    print(f"Using Firestore database: {FIRESTORE_DATABASE}")
else:
    # MySQL configuration
    DB_USER = os.getenv("DB_USER", "learnweave_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "your_db_password")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "learnweave_db")
    
    # Cloud SQL proxy uses Unix socket on Cloud Run
    CLOUD_SQL_CONNECTION_NAME = os.getenv("CLOUD_SQL_CONNECTION_NAME")  # e.g. project:region:instance
    
    if CLOUD_SQL_CONNECTION_NAME:
        # Cloud Run connects via Unix socket through the Cloud SQL Auth Proxy
        unix_socket = f"/cloudsql/{CLOUD_SQL_CONNECTION_NAME}"
        SQLALCHEMY_DATABASE_URL = (
            f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@/{DB_NAME}"
            f"?unix_socket={unix_socket}"
        )
        SQLALCHEMY_ASYNC_DATABASE_URL = (
            f"mysql+aiomysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@/{DB_NAME}"
            f"?unix_socket={unix_socket}"
        )
        print(f"Using Cloud SQL: {CLOUD_SQL_CONNECTION_NAME} / {DB_NAME}")
    else:
        # Local development: TCP connection
        SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        SQLALCHEMY_ASYNC_DATABASE_URL = f"mysql+aiomysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        print(f"Using MySQL database: {DB_NAME}")

# DB Pooling Settings
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", 3600))
DB_POOL_PRE_PING = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 5))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", 10))
DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", 10))  # Optional


# Google OAuth settings - Dynamic URLs based on environment
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

if IS_CLOUD_RUN:
    # Production: Use Cloud Run URL or custom domain
    CLOUD_RUN_SERVICE_URL = os.getenv("CLOUD_RUN_SERVICE_URL")
    BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", CLOUD_RUN_SERVICE_URL or "https://www.learnweave.ai")
    GOOGLE_REDIRECT_URI = os.getenv(
        "GOOGLE_REDIRECT_URI",
        f"{BACKEND_BASE_URL}/api/auth/google/callback"
    )
    FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "https://www.learnweave.ai")
else:
    # Development/other deployments (e.g. EC2): allow explicit public base URLs
    BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", PUBLIC_BASE_URL or "http://localhost:8000")
    GOOGLE_REDIRECT_URI = os.getenv(
        "GOOGLE_REDIRECT_URI",
        f"{BACKEND_BASE_URL}/api/auth/google/callback"
    )
    FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", PUBLIC_FRONTEND_URL or "http://localhost:3000")

# Note: GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION are set at the top of this file

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
if IS_CLOUD_RUN:
    GITHUB_REDIRECT_URI = os.getenv(
        "GITHUB_REDIRECT_URI",
        f"{BACKEND_BASE_URL}/api/auth/github/callback"
    )
else:
    GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", f"{BACKEND_BASE_URL}/api/auth/github/callback")

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
if IS_CLOUD_RUN:
    DISCORD_REDIRECT_URI = os.getenv(
        "DISCORD_REDIRECT_URI",
        f"{BACKEND_BASE_URL}/api/auth/discord/callback"
    )
else:
    DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", f"{BACKEND_BASE_URL}/api/auth/discord/callback")

# Cloud Storage Configuration
USE_CLOUD_STORAGE = os.getenv("USE_CLOUD_STORAGE", str(IS_CLOUD_RUN)).lower() == "true"
USE_S3_STORAGE = os.getenv("USE_S3_STORAGE", "false").lower() == "true"
GCS_BUCKET_IMAGES = os.getenv("GCS_BUCKET_IMAGES")
GCS_BUCKET_UPLOADS = os.getenv("GCS_BUCKET_UPLOADS")
GCS_BUCKET_EXPORTS = os.getenv("GCS_BUCKET_EXPORTS")
S3_BUCKET_IMAGES = os.getenv("S3_BUCKET_IMAGES")
S3_BUCKET_UPLOADS = os.getenv("S3_BUCKET_UPLOADS")
S3_BUCKET_EXPORTS = os.getenv("S3_BUCKET_EXPORTS")

CHROMA_DB_URL = os.getenv("CHROMA_DB_URL", "http://localhost:8001")

# Default fallback image for courses/chapters when generation fails
DEFAULT_COURSE_IMAGE = "https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8?w=800&q=80"

# Parse CORS list from env values like: "https://a.com,https://b.com"
def _parse_csv_env(var_name: str) -> list[str]:
    raw_value = os.getenv(var_name, "")
    if not raw_value.strip():
        return []
    return [part.strip() for part in raw_value.split(",") if part.strip()]


# CORS Origins - Dynamic based on environment
configured_origins = _parse_csv_env("CORS_ORIGINS")

if configured_origins:
    CORS_ORIGINS = configured_origins
elif IS_CLOUD_RUN:
    CORS_ORIGINS = [
        "https://www.learnweave.ai",
        "https://learnweave.ai",
        os.getenv("FRONTEND_URL", ""),
        FRONTEND_BASE_URL,
    ]
else:
    CORS_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        FRONTEND_BASE_URL,
        PUBLIC_FRONTEND_URL or "",
    ]

# Keep order while removing empty/duplicate origins.
CORS_ORIGINS = list(dict.fromkeys([origin for origin in CORS_ORIGINS if origin]))

AGENT_DEBUG_MODE = os.getenv("AGENT_DEBUG_MODE", "true").lower() == "true"