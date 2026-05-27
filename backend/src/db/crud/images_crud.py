from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from ..models.db_file import Image
from ..database import USE_FIRESTORE


############### IMAGES
def get_image_by_id(db: Session, image_id: int) -> Optional[Image]:
    """Get image by ID"""
    if USE_FIRESTORE:
        return db.get_image(str(image_id))
    return db.query(Image).filter(Image.id == image_id).first()

def get_images_by_ids(db: Session, image_ids: List[int]) -> List[Image]:
    """Get multiple images by their IDs"""
    if USE_FIRESTORE:
        return []
    if not image_ids:
        return []
    return db.query(Image).filter(Image.id.in_(image_ids)).all()


def get_images_by_user_id(db: Session, user_id: str) -> List[Image]:
    """Get all images for a specific user"""
    if USE_FIRESTORE:
        return db.get_images_by_user(str(user_id))
    return db.query(Image).filter(Image.user_id == user_id).all()


def get_images_by_course_id(db: Session, course_id: int) -> List[Image]:
    """Get all images for a specific course"""
    if USE_FIRESTORE:
        return db.get_images_by_user('', str(course_id))
    return db.query(Image).filter(Image.course_id == course_id).all()


def get_images_by_user_and_course(db: Session, user_id: str, course_id: int) -> List[Image]:
    """Get all images for a specific user and course"""
    if USE_FIRESTORE:
        return db.get_images_by_user(str(user_id), str(course_id))
    return db.query(Image).filter(
        and_(Image.user_id == user_id, Image.course_id == course_id)
    ).all()


def get_image_by_filename(db: Session, user_id: str, course_id: int, filename: str) -> Optional[Image]:
    """Get image by filename for a specific user and course"""
    if USE_FIRESTORE:
        return None
    return db.query(Image).filter(
        and_(
            Image.user_id == user_id,
            Image.course_id == course_id,
            Image.filename == filename
        )
    ).first()


def create_image(db: Session, course_id: int, user_id: str, filename: str,
                 content_type: str, image_data: bytes) -> Image:
    """Create a new image"""
    if USE_FIRESTORE:
        img_id = db.create_image({
            'course_id': str(course_id) if course_id else None,
            'user_id': str(user_id),
            'filename': filename,
            'content_type': content_type,
            'image_data': image_data,
        })
        return {'id': img_id, 'course_id': str(course_id), 'user_id': str(user_id),
                'filename': filename, 'content_type': content_type, 'image_data': image_data}
    db_image = Image(
        course_id=course_id,
        user_id=user_id,
        filename=filename,
        content_type=content_type,
        image_data=image_data,
    )
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    return db_image


def update_image(db: Session, image_id: int, **kwargs) -> Optional[Image]:
    """Update image with provided fields"""
    if USE_FIRESTORE:
        db.update_image(str(image_id), kwargs)
        return db.get_image(str(image_id))
    image = db.query(Image).filter(Image.id == image_id).first()
    if image:
        for key, value in kwargs.items():
            if hasattr(image, key):
                setattr(image, key, value)
        db.commit()
        db.refresh(image)
    return image


def update_image_data(db: Session, image_id: int, image_data: bytes,
                      content_type: str = None, filename: str = None) -> Optional[Image]:
    """Update image data and optionally filename/content_type"""
    update_fields = {"image_data": image_data}
    if content_type:
        update_fields["content_type"] = content_type
    if filename:
        update_fields["filename"] = filename

    return update_image(db, image_id, **update_fields)


def delete_image(db: Session, image_id: int) -> bool:
    """Delete image by ID"""
    if USE_FIRESTORE:
        db.delete_image(str(image_id))
        return True
    image = db.query(Image).filter(Image.id == image_id).first()
    if image:
        db.delete(image)
        db.commit()
        return True
    return False


def delete_images_by_course(db: Session, course_id: int) -> int:
    """Delete all images for a specific course. Returns number of deleted images."""
    if USE_FIRESTORE:
        return 0
    deleted_count = db.query(Image).filter(Image.course_id == course_id).delete()
    db.commit()
    return deleted_count


def delete_images_by_user(db: Session, user_id: str) -> int:
    """Delete all images for a specific user. Returns number of deleted images."""
    if USE_FIRESTORE:
        return 0
    deleted_count = db.query(Image).filter(Image.user_id == user_id).delete()
    db.commit()
    return deleted_count


def get_image_count_by_course(db: Session, course_id: int) -> int:
    """Get total number of images in a course"""
    if USE_FIRESTORE:
        return db.get_image_count_by_course(str(course_id))
    return db.query(Image).filter(Image.course_id == course_id).count()


def get_image_count_by_user(db: Session, user_id: str) -> int:
    """Get total number of images for a user"""
    if USE_FIRESTORE:
        return len(db.get_images_by_user(str(user_id)))
    return db.query(Image).filter(Image.user_id == user_id).count()


def get_images_by_content_type(db: Session, user_id: str, content_type: str) -> List[Image]:
    """Get all images of a specific content type for a user"""
    if USE_FIRESTORE:
        return []
    return db.query(Image).filter(
        and_(Image.user_id == user_id, Image.content_type == content_type)
    ).all()
