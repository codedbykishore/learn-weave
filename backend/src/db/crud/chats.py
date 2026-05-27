from sqlalchemy.orm import Session
from typing import List
from ..models.db_chat import Chat
from ..database import USE_FIRESTORE



def get_last_n_messages_by_course_id(db: Session, course_id: int, n: int = 10) -> List[Chat]:
    """Get the last n messages for a given course by its ID"""
    if USE_FIRESTORE:
        return []
    return db.query(Chat).filter(Chat.course_id == course_id).order_by(Chat.created_at.desc()).limit(n).all()

def save_chat_message(db: Session, chat: Chat) -> Chat:
    """Save a chat message to the database"""
    if USE_FIRESTORE:
        db.create_chat_message({
            'course_id': str(chat.course_id) if chat.course_id else None,
            'user_id': str(chat.user_id) if chat.user_id else None,
            'role': chat.role,
            'content': chat.content,
        })
        return chat
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat
