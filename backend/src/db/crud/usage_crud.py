from sqlalchemy.orm import Session
from typing import List, Optional
from ..models.db_usage import Usage
from ...api.schemas.statistics import UsagePost
from ..database import USE_FIRESTORE

def log_usage(db, user_id: str, action: str, course_id: int = None, chapter_id: int = None, details: str = None) -> Optional[dict]:
    """
    Log a user action in the database.
    """
    if USE_FIRESTORE:
        db.create_usage_log(user_id, action, details)
        return None

    usage = Usage(
        user_id=user_id,
        action=action,
        course_id=course_id,
        chapter_id=chapter_id,
        details=details
    )
    
    db.add(usage)
    db.commit()
    db.refresh(usage)
    
    return usage


def get_user_usages(db, user_id: str) -> List:
    """
    Get all usage records for a specific user.
    """
    if USE_FIRESTORE:
        return db.get_usage_logs(user_id)
    return db.query(Usage).filter(Usage.user_id == user_id).all()


def get_usage_by_action(db, user_id: str, action: str) -> List:
    """
    Get all usage records for a specific user filtered by action.
    """
    if USE_FIRESTORE:
        return db.get_usage_logs(user_id, action)
    return db.query(Usage).filter(Usage.user_id == user_id, Usage.action == action).all()


def log_chat_usage(db, user_id: str, course_id: int, chapter_id: int, message: str):
    """
    Log a chat message sent by a user.
    """
    return log_usage(db, user_id, action="chat", course_id=course_id, chapter_id=chapter_id, details=message)


def get_total_chat_usages(db, user_id: str) -> int:
    """
    Get the total number of chat messages sent by a user.
    """
    if USE_FIRESTORE:
        return db.count_usage_logs(user_id, "chat")
    return db.query(Usage).filter(Usage.user_id == user_id, Usage.action == "chat").count()


def get_total_created_courses(db, user_id: str) -> int:
    """
    Get the total number of courses created by a user.
    """
    if USE_FIRESTORE:
        return db.count_usage_logs(user_id, "create_course")
    return db.query(Usage).filter(Usage.user_id == user_id, Usage.action == "create_course").count()

def log_course_creation(db, user_id: str, course_id: int, detail: str):
    """
    Log the creation of a course by a user.
    
    :param db: Database session
    :param user_id: ID of the user creating the course
    :param course_id: ID of the created course
    :return: The created Usage object
    """
    return log_usage(db, user_id, action="create_course", course_id=course_id, details=detail)

def log_chapter_completion(db, user_id: str, course_id: int, chapter_id: int):
    """
    Log the completion of a chapter by a user.
    
    :param db: Database session
    :param user_id: ID of the user completing the chapter
    :param course_id: ID of the course containing the chapter
    :param chapter_id: ID of the completed chapter
    :return: The created Usage object
    """
    return log_usage(db, user_id, action="complete_chapter", course_id=course_id, chapter_id=chapter_id)

def get_total_time_spent_on_chapters(db, user_id: str) -> int:
    """
    Get the total time spent by a user on chapters.
    """
    if USE_FIRESTORE:
        return db.count_usage_logs(user_id, "site_visible")
    usages = (
        db.query(Usage)
        .filter(Usage.user_id == user_id, Usage.action == "site_visible", Usage.course_id != None, Usage.chapter_id != None)
        .count()
    )

    return usages * 10


def get_user_with_total_usage_time(db: Session, offset: int = 0, limit: int = 200):
    """
    Get users with their total usage time in minutes.
    """
    if USE_FIRESTORE:
        return []
    from sqlalchemy import func
    from ..models.db_user import User
    
    usage_counts = (
        db.query(
            Usage.user_id,
            func.count('*').label('usage_count')
        )
        .filter(
            Usage.action == "site_visible",
            Usage.course_id != None,
            Usage.chapter_id != None
        )
        .group_by(Usage.user_id)
        .subquery()
    )
    
    user_usages = (
        db.query(
            User,
            (func.coalesce(usage_counts.c.usage_count, 0) * 10).label('total_usage_time')
        )
        .outerjoin(
            usage_counts,
            User.id == usage_counts.c.user_id
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    return [
        {
            'user': user,
            'total_usage_time': total_usage_time
        }
        for user, total_usage_time in user_usages
    ]


def log_site_usage(db, usage: UsagePost):
    """
    Log a user action on the site.
    
    :param db: Database session
    :param usage: UsagePost object containing user_id, course_id, chapter_id, and url
    :return: The created Usage object
    """
    return log_usage(db,
        user_id=usage.user_id,
        action="site" + ("_visible" if usage.visible else "_hidden"),
        course_id=usage.course_id,
        chapter_id=usage.chapter_id,
        details=usage.url)

def log_login(db, user_id: str):
    """
    Log a user login action.
    
    :param db: Database session
    :param user_id: ID of the user logging in
    :return: The created Usage object
    """
    return log_usage(db, user_id, action="login")

def log_admin_login_as(db, user_who: str, user_as: str):
    """
    Log an admin login-as action.
    
    :param db: Database session
    :param user_who: ID of the admin logging in as
    :param user_as: ID of the user being logged in as
    :return: The created Usage object
    """
    return log_usage(db, user_who, action="admin_login_as", details="Admin logged in as user: " + user_as)


def log_refresh(db, user_id: str):
    """
    Log a user refresh action.
    
    :param db: Database session
    :param user_id: ID of the user refreshing their session
    :return: The created Usage object
    """
    return log_usage(db, user_id, action="refresh")

def log_logout(db, user_id: str):
    """
    Log a user logout action.
    
    :param db: Database session
    :param user_id: ID of the user logging out
    :return: The created Usage object
    """
    return log_usage(db, user_id, action="logout")

def get_login_count(db, user_id: str) -> int:
    """
    Get the total number of login actions for a user.
    """
    if USE_FIRESTORE:
        return db.count_usage_logs(user_id, "login")
    return db.query(Usage).filter(Usage.user_id == user_id, Usage.action == "login").count()



def log_search(db, user_id: str, query: str):
    """
    Log a search action performed by a user.
    
    :param db: Database session
    :param user_id: ID of the user performing the search
    :param query: The search query string
    :return: The created Usage object
    """
    return log_usage(db, user_id, action="search", details=query)