"""
Firestore Database Adapter
Replaces MySQL/SQLAlchemy with Google Cloud Firestore
"""
from google.cloud import firestore
from typing import Optional, List, Dict, Any
from datetime import datetime
import os


class FirestoreAdapter:
    """Adapter to replace MySQL with Firestore"""
    
    def __init__(self):
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        database_id = os.getenv('FIRESTORE_DATABASE', '(default)')
        
        self.db = firestore.Client(
            project=project_id,
            database=database_id
        )
        
        # Collection names
        self.USERS = 'users'
        self.COURSES = 'courses'
        self.NOTES = 'notes'
        self.FLASHCARDS = 'flashcards'
        self.QUESTIONS = 'questions'
        self.CHAT_MESSAGES = 'chat_messages'
        self.SESSIONS = 'sessions'
    
    # ==================== USER OPERATIONS ====================
    
    def create_user(self, user_data: Dict[str, Any]) -> str:
        """Create a new user"""
        user_ref = self.db.collection(self.USERS).document()
        user_data['created_at'] = firestore.SERVER_TIMESTAMP
        user_data['updated_at'] = firestore.SERVER_TIMESTAMP
        user_ref.set(user_data)
        return user_ref.id
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        users = self.db.collection(self.USERS)\
            .where('email', '==', email)\
            .limit(1)\
            .get()
        
        if users:
            doc = users[0]
            return {**doc.to_dict(), 'id': doc.id}
        return None
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        doc = self.db.collection(self.USERS).document(str(user_id)).get()
        if doc.exists:
            return {**doc.to_dict(), 'id': doc.id}
        return None
    
    def get_user_by_oauth(self, provider: str, oauth_id: str) -> Optional[Dict[str, Any]]:
        """Get user by OAuth provider and ID"""
        users = self.db.collection(self.USERS)\
            .where('oauth_provider', '==', provider)\
            .where('oauth_id', '==', oauth_id)\
            .limit(1)\
            .get()
        
        if users:
            doc = users[0]
            return {**doc.to_dict(), 'id': doc.id}
        return None
    
    def update_user(self, user_id: str, update_data: Dict[str, Any]):
        """Update user data"""
        update_data['updated_at'] = firestore.SERVER_TIMESTAMP
        self.db.collection(self.USERS).document(str(user_id)).update(update_data)
    
    def delete_user(self, user_id: str):
        """Delete user"""
        self.db.collection(self.USERS).document(str(user_id)).delete()
    
    def get_all_users(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all users with pagination"""
        users = self.db.collection(self.USERS)\
            .order_by('created_at', direction=firestore.Query.DESCENDING)\
            .limit(limit)\
            .offset(offset)\
            .get()
        
        return [{**doc.to_dict(), 'id': doc.id} for doc in users]
    
    # ==================== COURSE OPERATIONS ====================
    
    def create_course(self, course_data: Dict[str, Any]) -> str:
        """Create a new course"""
        course_ref = self.db.collection(self.COURSES).document()
        course_data['created_at'] = firestore.SERVER_TIMESTAMP
        course_data['updated_at'] = firestore.SERVER_TIMESTAMP
        course_ref.set(course_data)
        
        # Increment user's course count
        if 'user_id' in course_data:
            self._increment_user_course_count(course_data['user_id'])
        
        return course_ref.id
    
    def get_course(self, course_id: str) -> Optional[Dict[str, Any]]:
        """Get course by ID"""
        doc = self.db.collection(self.COURSES).document(str(course_id)).get()
        if doc.exists:
            course = {**doc.to_dict(), 'id': doc.id}
            # Load chapters
            course['chapters'] = self.get_course_chapters(course_id)
            return course
        return None
    
    def get_user_courses(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all courses for a user"""
        courses = self.db.collection(self.COURSES)\
            .where('user_id', '==', str(user_id))\
            .order_by('created_at', direction=firestore.Query.DESCENDING)\
            .limit(limit)\
            .get()
        
        result = []
        for doc in courses:
            course = {**doc.to_dict(), 'id': doc.id}
            # Optionally load chapter count
            chapters = self.db.collection(self.COURSES)\
                .document(doc.id)\
                .collection('chapters')\
                .count()\
                .get()
            course['chapter_count'] = chapters[0][0].value if chapters else 0
            result.append(course)
        
        return result
    
    def update_course(self, course_id: str, update_data: Dict[str, Any]):
        """Update course"""
        update_data['updated_at'] = firestore.SERVER_TIMESTAMP
        self.db.collection(self.COURSES).document(str(course_id)).update(update_data)
    
    def delete_course(self, course_id: str):
        """Delete course and all its chapters"""
        course_ref = self.db.collection(self.COURSES).document(str(course_id))
        
        # Delete all chapters
        chapters = course_ref.collection('chapters').get()
        batch = self.db.batch()
        for chapter in chapters:
            batch.delete(chapter.reference)
        batch.commit()
        
        # Get user_id before deleting
        course_doc = course_ref.get()
        user_id = course_doc.to_dict().get('user_id') if course_doc.exists else None
        
        # Delete course
        course_ref.delete()
        
        # Decrement user's course count
        if user_id:
            self._decrement_user_course_count(user_id)
    
    # ==================== CHAPTER OPERATIONS ====================
    
    def create_chapter(self, course_id: str, chapter_data: Dict[str, Any]) -> str:
        """Create a new chapter in a course"""
        chapter_ref = self.db.collection(self.COURSES)\
            .document(str(course_id))\
            .collection('chapters')\
            .document()
        
        chapter_data['created_at'] = firestore.SERVER_TIMESTAMP
        chapter_data['updated_at'] = firestore.SERVER_TIMESTAMP
        chapter_ref.set(chapter_data)
        
        return chapter_ref.id
    
    def get_chapter(self, course_id: str, chapter_id: str) -> Optional[Dict[str, Any]]:
        """Get specific chapter"""
        doc = self.db.collection(self.COURSES)\
            .document(str(course_id))\
            .collection('chapters')\
            .document(str(chapter_id))\
            .get()
        
        if doc.exists:
            return {**doc.to_dict(), 'id': doc.id}
        return None
    
    def get_course_chapters(self, course_id: str) -> List[Dict[str, Any]]:
        """Get all chapters for a course"""
        chapters = self.db.collection(self.COURSES)\
            .document(str(course_id))\
            .collection('chapters')\
            .order_by('order', direction=firestore.Query.ASCENDING)\
            .get()
        
        return [{**doc.to_dict(), 'id': doc.id} for doc in chapters]
    
    def update_chapter(self, course_id: str, chapter_id: str, update_data: Dict[str, Any]):
        """Update chapter"""
        update_data['updated_at'] = firestore.SERVER_TIMESTAMP
        self.db.collection(self.COURSES)\
            .document(str(course_id))\
            .collection('chapters')\
            .document(str(chapter_id))\
            .update(update_data)
    
    def delete_chapter(self, course_id: str, chapter_id: str):
        """Delete chapter"""
        self.db.collection(self.COURSES)\
            .document(str(course_id))\
            .collection('chapters')\
            .document(str(chapter_id))\
            .delete()
    
    # ==================== NOTES OPERATIONS ====================
    
    def create_note(self, note_data: Dict[str, Any]) -> str:
        """Create a new note"""
        note_ref = self.db.collection(self.NOTES).document()
        note_data['created_at'] = firestore.SERVER_TIMESTAMP
        note_data['updated_at'] = firestore.SERVER_TIMESTAMP
        note_ref.set(note_data)
        return note_ref.id
    
    def get_user_notes(self, user_id: str, course_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get notes for a user, optionally filtered by course"""
        query = self.db.collection(self.NOTES).where('user_id', '==', str(user_id))
        
        if course_id:
            query = query.where('course_id', '==', str(course_id))
        
        notes = query.order_by('created_at', direction=firestore.Query.DESCENDING).get()
        return [{**doc.to_dict(), 'id': doc.id} for doc in notes]
    
    def update_note(self, note_id: str, update_data: Dict[str, Any]):
        """Update note"""
        update_data['updated_at'] = firestore.SERVER_TIMESTAMP
        self.db.collection(self.NOTES).document(str(note_id)).update(update_data)
    
    def delete_note(self, note_id: str):
        """Delete note"""
        self.db.collection(self.NOTES).document(str(note_id)).delete()
    
    # ==================== CHAT OPERATIONS ====================
    
    def create_chat_message(self, message_data: Dict[str, Any]) -> str:
        """Create a chat message"""
        msg_ref = self.db.collection(self.CHAT_MESSAGES).document()
        message_data['created_at'] = firestore.SERVER_TIMESTAMP
        msg_ref.set(message_data)
        return msg_ref.id
    
    def get_chat_history(self, user_id: str, chapter_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get chat history for a user and chapter"""
        messages = self.db.collection(self.CHAT_MESSAGES)\
            .where('user_id', '==', str(user_id))\
            .where('chapter_id', '==', str(chapter_id))\
            .order_by('created_at', direction=firestore.Query.ASCENDING)\
            .limit(limit)\
            .get()
        
        return [{**doc.to_dict(), 'id': doc.id} for doc in messages]
    
    def delete_chat_history(self, user_id: str, chapter_id: str):
        """Delete all chat messages for a user and chapter"""
        messages = self.db.collection(self.CHAT_MESSAGES)\
            .where('user_id', '==', str(user_id))\
            .where('chapter_id', '==', str(chapter_id))\
            .get()
        
        batch = self.db.batch()
        for msg in messages:
            batch.delete(msg.reference)
        batch.commit()
    
    # ==================== FLASHCARD OPERATIONS ====================
    
    def create_flashcard(self, flashcard_data: Dict[str, Any]) -> str:
        """Create a flashcard"""
        card_ref = self.db.collection(self.FLASHCARDS).document()
        flashcard_data['created_at'] = firestore.SERVER_TIMESTAMP
        card_ref.set(flashcard_data)
        return card_ref.id
    
    def get_course_flashcards(self, course_id: str) -> List[Dict[str, Any]]:
        """Get all flashcards for a course"""
        cards = self.db.collection(self.FLASHCARDS)\
            .where('course_id', '==', str(course_id))\
            .get()
        
        return [{**doc.to_dict(), 'id': doc.id} for doc in cards]
    
    # ==================== BATCH OPERATIONS ====================
    
    def batch_write(self, operations: List[Dict[str, Any]]):
        """Execute multiple write operations atomically"""
        batch = self.db.batch()
        
        for op in operations:
            op_type = op['type']
            collection = op['collection']
            doc_id = op.get('doc_id')
            data = op.get('data', {})
            
            if op_type == 'set':
                ref = self.db.collection(collection).document(doc_id) if doc_id \
                    else self.db.collection(collection).document()
                batch.set(ref, data)
            elif op_type == 'update':
                ref = self.db.collection(collection).document(doc_id)
                batch.update(ref, data)
            elif op_type == 'delete':
                ref = self.db.collection(collection).document(doc_id)
                batch.delete(ref)
        
        batch.commit()
    
    # ==================== HELPER METHODS ====================
    
    def _increment_user_course_count(self, user_id: str):
        """Increment user's course count"""
        user_ref = self.db.collection(self.USERS).document(str(user_id))
        user_ref.update({
            'course_count': firestore.Increment(1),
            'updated_at': firestore.SERVER_TIMESTAMP
        })
    
    def _decrement_user_course_count(self, user_id: str):
        """Decrement user's course count"""
        user_ref = self.db.collection(self.USERS).document(str(user_id))
        user_ref.update({
            'course_count': firestore.Increment(-1),
            'updated_at': firestore.SERVER_TIMESTAMP
        })
    
    # ==================== TRANSACTION SUPPORT ====================
    
    @firestore.transactional
    def transactional_update(self, transaction, doc_ref, update_data):
        """Perform transactional update"""
        snapshot = doc_ref.get(transaction=transaction)
        if snapshot.exists:
            transaction.update(doc_ref, update_data)
    
    # ==================== QUERY HELPERS ====================
    
    def query_courses_by_status(self, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Query courses by status"""
        courses = self.db.collection(self.COURSES)\
            .where('status', '==', status)\
            .limit(limit)\
            .get()
        
        return [{**doc.to_dict(), 'id': doc.id} for doc in courses]
    
    def search_courses(self, user_id: str, search_term: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search courses by title (basic text search)"""
        # Note: Firestore doesn't have full-text search
        # This is a basic implementation - consider using Algolia or Elastic for production
        courses = self.db.collection(self.COURSES)\
            .where('user_id', '==', str(user_id))\
            .order_by('title')\
            .start_at([search_term])\
            .end_at([search_term + '\uf8ff'])\
            .limit(limit)\
            .get()
        
        return [{**doc.to_dict(), 'id': doc.id} for doc in courses]
