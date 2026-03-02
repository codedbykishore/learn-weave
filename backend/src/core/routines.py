"""
Core routines
"""
import logging
from datetime import datetime, timedelta, timezone

from ..db.database import get_db, USE_FIRESTORE


def update_stuck_courses():
    """
    Check for courses that are stuck in 'creating' status for more than 2 hours
    and mark them as 'error'.
    """
    if USE_FIRESTORE:
        # Firestore mode: use Firestore adapter to query stuck courses
        try:
            from ..db.firestore_adapter import FirestoreAdapter
            adapter = FirestoreAdapter()
            threshold = datetime.now(timezone.utc) - timedelta(hours=2)
            
            courses_ref = adapter.db.collection("courses")
            stuck = courses_ref.where("status", "==", "creating").where("created_at", "<", threshold).stream()
            
            count = 0
            for doc in stuck:
                doc.reference.update({
                    "status": "failed",
                    "error_msg": "Course creation timed out."
                })
                count += 1
            logging.info("Marked %s stuck courses as error (Firestore).", count)
        except Exception as e:
            logging.error("Scheduler error (Firestore): %s", e)
        return
    
    # MySQL/SQLAlchemy mode
    from sqlalchemy.orm import Session
    from sqlalchemy.exc import SQLAlchemyError
    from ..db.models.db_course import Course, CourseStatus

    db_gen = get_db()
    db: Session = next(db_gen)

    logging.info("Checking for stuck courses...")

    try:
        threshold = datetime.now(timezone.utc) - timedelta(hours=2)

        stuck_courses = db.query(Course).filter(
            Course.status == "creating",
            Course.created_at < threshold
        ).all()

        for course in stuck_courses:
            logging.info("Marking course %s as error due to timeout.", course.id)
            course.status = CourseStatus.FAILED
            course.error_msg = "Course creation timed out."
        db.commit()
        logging.info("Marked %s stuck courses as error.", len(stuck_courses))

    except SQLAlchemyError as e:
        logging.error("Scheduler error: %s", e)
    finally:
        next(db_gen, None)

