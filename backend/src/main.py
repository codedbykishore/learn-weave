import asyncio
import atexit
import logging
import secrets
from typing import Optional
import os

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from pathlib import Path
import os

from .api.routers import auth as auth_router
from .api.routers import courses, files, users, statistics, questions
from .api.routers import notes
#from .api.routers import notifications
from .api.routers import chat
from .api.routers import search as search_router
from .api.routers import flashcard
from .api.schemas import user as user_schema
from .db.database import engine, SessionLocal, USE_FIRESTORE
from .db.models import db_user as user_model
from .utils import auth

from .core.routines import update_stuck_courses
from .config.settings import SESSION_SECRET_KEY
from .core.lifespan import lifespan

import time

# Create database tables (only for MySQL mode)
# Retry logic handles Cloud SQL proxy sidecar startup delay on Cloud Run
if not USE_FIRESTORE and engine is not None:
    for _attempt in range(5):
        try:
            user_model.Base.metadata.create_all(bind=engine)
            break
        except Exception as e:
            if _attempt < 4:
                logging.warning(f"DB connection attempt {_attempt+1}/5 failed: {e}. Retrying in 3s...")
                time.sleep(3)
            else:
                logging.error(f"Failed to connect to database after 5 attempts: {e}")
                raise

# Create output directory for flashcard files
output_dir = Path("/tmp/anki_output") if os.path.exists("/tmp") else Path("./anki_output")
output_dir.mkdir(exist_ok=True)

# Create persistent directory for AI-generated course/chapter images
generated_images_dir = Path(__file__).parent.parent / "generated_images"
generated_images_dir.mkdir(parents=True, exist_ok=True)

# Create the main app instance
app = FastAPI(
    title="User Management API",
    root_path="/api",
    lifespan=lifespan  # Use the lifespan context manager
)


app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY
)


# CORS Configuration - Dynamic origins
from .config.settings import CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define /users/me BEFORE including users.router to ensure correct route matching
@app.get("/users/me", response_model=Optional[user_schema.User], tags=["users"])
async def read_users_me(current_user: Optional[user_model.User] = Depends(auth.get_current_user_optional)):
    """Get the current logged-in user's details."""
    return current_user

# Include your existing routers under this api_router
app.include_router(users.router)
app.include_router(courses.router)
app.include_router(files.router)
app.include_router(search_router.router)  # Add search router
app.include_router(statistics.router)
app.include_router(auth_router.api_router)
app.include_router(notes.router)
#app.include_router(notifications.router)
app.include_router(questions.router)
app.include_router(chat.router)
app.include_router(flashcard.router)

# Mount static files for flashcard downloads
app.mount("/output", StaticFiles(directory=str(output_dir)), name="output")

# Mount static files for AI-generated course/chapter cover images
app.mount("/generated_images", StaticFiles(directory=str(generated_images_dir)), name="generated_images")


# The root path "/" is now outside the /api prefix
@app.get("/")
async def root():
    """Status endpoint for the API."""
    return {"message": "Welcome to the User Management API. API endpoints are under /api"}
