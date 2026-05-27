from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from ..models.db_course import PracticeQuestion
from ..database import USE_FIRESTORE


############### MULTIPLE CHOICE QUESTIONS
def get_question_by_id(db: Session, question_id: int) -> Optional[PracticeQuestion]:
    """Get question by ID"""
    if USE_FIRESTORE:
        return db.get_question(str(question_id))
    return db.query(PracticeQuestion).filter(PracticeQuestion.id == question_id).first()


def get_questions_by_chapter_id(db: Session, chapter_id: int) -> List[PracticeQuestion]:
    """Get all questions for a specific chapter"""
    if USE_FIRESTORE:
        return db.get_questions_by_chapter(str(chapter_id))
    return db.query(PracticeQuestion).filter(PracticeQuestion.chapter_id == chapter_id).all()


def create_mc_question(db: Session, chapter_id: int, question: str, answer_a: str,
                    answer_b: str, answer_c: str, answer_d: str, correct_answer: str,
                    explanation: str) -> PracticeQuestion:
    """Create a new question"""
    if USE_FIRESTORE:
        q_id = db.create_question({
            'chapter_id': str(chapter_id),
            'type': 'MC',
            'question': question,
            'answer_a': answer_a,
            'answer_b': answer_b,
            'answer_c': answer_c,
            'answer_d': answer_d,
            'correct_answer': correct_answer,
            'explanation': explanation,
        })
        return {'id': q_id, 'chapter_id': str(chapter_id), 'type': 'MC', 'question': question,
                'answer_a': answer_a, 'answer_b': answer_b, 'answer_c': answer_c, 'answer_d': answer_d,
                'correct_answer': correct_answer, 'explanation': explanation}
    db_question = PracticeQuestion(
        chapter_id=chapter_id,
        type='MC',
        question=question,
        answer_a=answer_a,
        answer_b=answer_b,
        answer_c=answer_c,
        answer_d=answer_d,
        correct_answer=correct_answer,
        explanation=explanation
    )
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return db_question

def create_ot_question(db: Session, chapter_id: int, question: str, correct_answer: str) -> PracticeQuestion:
    """Create a new question"""
    if USE_FIRESTORE:
        q_id = db.create_question({
            'chapter_id': str(chapter_id),
            'type': 'OT',
            'question': question,
            'correct_answer': correct_answer,
        })
        return {'id': q_id, 'chapter_id': str(chapter_id), 'type': 'OT', 'question': question,
                'correct_answer': correct_answer}
    db_question = PracticeQuestion(
        chapter_id=chapter_id,
        type='OT',
        question=question,
        correct_answer=correct_answer,
    )
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return db_question


def create_multiple_questions(db: Session, chapter_id: int, questions_data: List[dict]) -> List[
    PracticeQuestion]:
    """Create multiple questions for a chapter at once"""
    if USE_FIRESTORE:
        result = []
        for q_data in questions_data:
            q_id = db.create_question({
                'chapter_id': str(chapter_id),
                'type': q_data['type'],
                'question': q_data['question'],
                'answer_a': q_data.get('answer_a'),
                'answer_b': q_data.get('answer_b'),
                'answer_c': q_data.get('answer_c'),
                'answer_d': q_data.get('answer_d'),
                'correct_answer': q_data['correct_answer'],
                'explanation': q_data.get('explanation'),
            })
            result.append({**q_data, 'id': q_id, 'chapter_id': str(chapter_id)})
        return result
    db_questions = []
    for q_data in questions_data:
        if q_data['type'] == 'MC':
            db_question = PracticeQuestion(
                chapter_id=chapter_id,
                type='MC',
                question=q_data['question'],
                answer_a=q_data['answer_a'],
                answer_b=q_data['answer_b'],
                answer_c=q_data['answer_c'],
                answer_d=q_data['answer_d'],
                correct_answer=q_data['correct_answer'],
                explanation=q_data['explanation']
            )
        else:
            db_question = PracticeQuestion(
                chapter_id=chapter_id,
                type='OT',
                question=q_data['question'],
                correct_answer=q_data['correct_answer']
            )
        db_questions.append(db_question)
        db.add(db_question)

    db.commit()
    for question in db_questions:
        db.refresh(question)
    return db_questions


def update_question(db: Session, question_id: int, **kwargs) -> Optional[PracticeQuestion]:
    """Update question with provided fields"""
    if USE_FIRESTORE:
        db.update_question(str(question_id), kwargs)
        return db.get_question(str(question_id))
    question = db.query(PracticeQuestion).filter(PracticeQuestion.id == question_id).first()
    if question:
        for key, value in kwargs.items():
            if hasattr(question, key):
                setattr(question, key, value)
        db.commit()
        db.refresh(question)
    return question


def delete_question(db: Session, question_id: int) -> bool:
    """Delete question by ID"""
    if USE_FIRESTORE:
        db.delete_question(str(question_id))
        return True
    question = db.query(PracticeQuestion).filter(PracticeQuestion.id == question_id).first()
    if question:
        db.delete(question)
        db.commit()
        return True
    return False


def delete_questions_by_chapter(db: Session, chapter_id: int) -> int:
    """Delete all questions for a specific chapter. Returns number of deleted questions."""
    if USE_FIRESTORE:
        questions = db.get_questions_by_chapter(str(chapter_id))
        db.delete_questions_by_chapter(str(chapter_id))
        return len(questions)
    deleted_count = db.query(PracticeQuestion).filter(
        PracticeQuestion.chapter_id == chapter_id
    ).delete()
    db.commit()
    return deleted_count
