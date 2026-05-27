"""CRUD operations for user management in the database."""
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.sql import text
from ..models.db_user import User
from datetime import datetime, timezone, timedelta
from ..database import USE_FIRESTORE

def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """Retrieve a user by their ID."""
    if USE_FIRESTORE:
        return db.get_user_by_id(str(user_id))
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Retrieve a user by their username."""
    if USE_FIRESTORE:
        return db.get_user_by_username(username)
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Retrieve a user by their email."""
    if USE_FIRESTORE:
        return db.get_user_by_email(email)
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session,
                user_id: str,
                username: str,
                email: str, hashed_password: str,
                is_active=True, is_admin=False,
                profile_image_base64=None):
    """Create a new user in the database."""
    if USE_FIRESTORE:
        user_data = {
            'username': username,
            'email': email,
            'hashed_password': hashed_password,
            'is_active': is_active,
            'is_admin': is_admin,
        }
        if profile_image_base64:
            user_data['profile_image_base64'] = profile_image_base64
        doc_id = db.create_user(user_data, doc_id=str(user_id))
        return {'id': doc_id, **user_data}
    user = User(
        id=user_id,
        username=username,
        email=email,
        hashed_password=hashed_password,
        is_active=is_active,
        is_admin=is_admin,
        
    )
    if profile_image_base64:
        user.profile_image_base64 = profile_image_base64
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def update_user_last_login(db: Session, user_id: str) -> Optional[User]:
    """Update the last_login time for a user."""
    if USE_FIRESTORE:
        now = datetime.now(timezone.utc)
        db.update_user(str(user_id), {'last_login': now.isoformat()})
        return db.get_user_by_id(str(user_id))
    user = get_user_by_id(db, user_id)
    if user:
        if not user.last_login:
            user.login_streak = 1
        else:
            time_diff: timedelta = datetime.now(timezone.utc).date() - user.last_login.date()
            days_since_last_login = time_diff.days
            
            if days_since_last_login == 0:
                pass
            elif days_since_last_login == 1:
                user.login_streak += 1
            else:
                user.login_streak = 1

        user.last_login = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user)
    return user

def update_user_profile_image(db: Session, user: User, profile_image_base64: str):
    """Update the profile image of an existing user."""
    if USE_FIRESTORE:
        user_id = user['id'] if isinstance(user, dict) else user.id
        db.update_user(str(user_id), {'profile_image_base64': profile_image_base64})
        return user
    user.profile_image_base64 = profile_image_base64
    db.commit()
    db.refresh(user)
    return user

def get_users(db: Session, skip: int = 0, limit: int = 200):
    """Retrieve users with pagination."""
    if USE_FIRESTORE:
        return db.get_all_users(limit=limit, offset=skip)
    return db.query(User).offset(skip).limit(limit).all()

def update_user(db: Session, db_user: User, update_data: dict):
    """Update an existing user's information."""
    if USE_FIRESTORE:
        user_id = db_user['id'] if isinstance(db_user, dict) else db_user.id
        db.update_user(str(user_id), update_data)
        return db.get_user_by_id(str(user_id))
    for key, value in update_data.items():
        setattr(db_user, key, value)
    db.commit()
    db.refresh(db_user)
    return db_user

def change_user_password(db: Session, db_user: User, hashed_password: str):
    """Change an existing user's password."""
    if USE_FIRESTORE:
        user_id = db_user['id'] if isinstance(db_user, dict) else db_user.id
        db.update_user(str(user_id), {'hashed_password': hashed_password})
        return db.get_user_by_id(str(user_id))
    setattr(db_user, "hashed_password", hashed_password)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_active_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """Retrieve an active user by their ID."""
    if USE_FIRESTORE:
        user = db.get_user_by_id(str(user_id))
        if user and user.get('is_active'):
            return user
        return None
    return db.query(User).filter(User.id == user_id, User.is_active ==  True).first()

def delete_user(db: Session, db_user: User):
    """
    Delete a user from the database, including all associated data.
    """
    if USE_FIRESTORE:
        user_id = db_user['id'] if isinstance(db_user, dict) else db_user.id
        db.delete_user(str(user_id))
        return db_user
    user_id = db_user.id

    db.execute(text("DELETE FROM notes WHERE user_id = :user_id"), {"user_id": user_id})

    courses = db.execute(text("SELECT id FROM courses WHERE user_id = :user_id"), {"user_id": user_id}).fetchall()
    course_ids = [course[0] for course in courses]
    
    if course_ids:
        if len(course_ids) == 1:
            course_ids_placeholder = f"(:course_id_0)"
            params = {"course_id_0": course_ids[0]}
        else:
            course_ids_placeholder = ", ".join([f":course_id_{i}" for i in range(len(course_ids))])
            course_ids_placeholder = f"({course_ids_placeholder})"
            params = {f"course_id_{i}": course_id for i, course_id in enumerate(course_ids)}

        db.execute(text(f"DELETE FROM images WHERE course_id IN {course_ids_placeholder}"), params)
        
        db.execute(text(f"DELETE FROM practice_questions WHERE chapter_id IN "
                      f"(SELECT id FROM chapters WHERE course_id IN {course_ids_placeholder})"), params)
        
        db.execute(text(f"DELETE FROM documents WHERE course_id IN {course_ids_placeholder}"), params)
        
        db.execute(text(f"DELETE FROM notes WHERE chapter_id IN (SELECT id FROM chapters WHERE course_id IN {course_ids_placeholder})"), params)

        db.execute(text(f"DELETE FROM chapters WHERE course_id IN {course_ids_placeholder}"), params)
        
        db.execute(text(f"DELETE FROM courses WHERE id IN {course_ids_placeholder}"), params)
    
    db.execute(text("DELETE FROM documents WHERE user_id = :user_id AND course_id IS NULL"), {"user_id": user_id})
    
    db.execute(text("DELETE FROM images WHERE user_id = :user_id"), {"user_id": user_id})
    
    db.delete(db_user)
    db.commit()
    
    return db_user
