"""CRUD operations for notes management in the database."""
from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.db_note import Note
from ..database import USE_FIRESTORE

def get_note_by_id(db: Session, note_id: int) -> Optional[Note]:
    """Retrieve a note by its ID."""
    if USE_FIRESTORE:
        return None
    return db.query(Note).filter(Note.id == note_id).first()

def get_notes_by_chapter(
    db: Session, 
    course_id: int, 
    chapter_id: int, 
    user_id: str
) -> List[Note]:
    """Retrieve all notes for a specific chapter and user."""
    if USE_FIRESTORE:
        return db.get_user_notes(str(user_id), str(course_id))
    return db.query(Note).filter(
        Note.course_id == course_id,
        Note.chapter_id == chapter_id,
        Note.user_id == user_id
    ).all()

def create_note(
    db: Session,
    course_id: int,
    chapter_id: int,
    user_id: str,
    text: str
) -> Note:
    """Create a new note in the database."""
    if USE_FIRESTORE:
        note_id = db.create_note({
            'course_id': str(course_id),
            'chapter_id': str(chapter_id),
            'user_id': str(user_id),
            'text': text,
        })
        return {'id': note_id, 'course_id': str(course_id), 'chapter_id': str(chapter_id),
                'user_id': str(user_id), 'text': text}
    db_note = Note(
        course_id=course_id,
        chapter_id=chapter_id,
        user_id=user_id,
        text=text
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note

def update_note(
    db: Session,
    db_note: Note,
    text: str
) -> Note:
    """Update an existing note's text."""
    if USE_FIRESTORE:
        db.update_note(str(db_note['id']), {'text': text})
        db_note['text'] = text
        return db_note
    db_note.text = text
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note

def delete_note(
    db: Session,
    db_note: Note
) -> None:
    """Delete a note from the database."""
    if USE_FIRESTORE:
        note_id = db_note['id'] if isinstance(db_note, dict) else db_note.id
        db.delete_note(str(note_id))
        return None
    db.delete(db_note)
    db.commit()
    return None
