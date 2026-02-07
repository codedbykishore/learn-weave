"""
This file defines the service that coordinates the interaction between all the agents
"""
import json
import asyncio
import traceback
import time
from typing import List
from logging import getLogger


from google.adk.sessions import InMemorySessionService

from ..services import vector_service
from ..services.course_content_service import CourseContentService

from .query_service import QueryService
from .state_service import StateService, CourseState
from ..agents.explainer_agent.agent import ExplainerAgent
from ..agents.grader_agent.agent import GraderAgent
from ..db.crud import chapters_crud, documents_crud, images_crud, questions_crud, courses_crud


from google.adk.sessions import InMemorySessionService

from ..agents.planner_retriever_agent import PlannerRetrieverAgent
from ..agents.image_agent.agent import ImageAgent

from ..agents.tester_agent import TesterAgent
from ..agents.utils import create_text_query
from ..db.models.db_course import CourseStatus
from ..api.schemas.course import CourseRequest
from ..config.settings import DEFAULT_COURSE_IMAGE
from ..agents.retry_handler import retry_async_call
#from ..services.notification_service import WebSocketConnectionManager
from ..db.models.db_course import Course
from ..db.database import get_db_context
from google.genai import types

#from .data_processors.pdf_processor import PDFProcessor

from ..db.models.db_file import Document, Image
from ..db.crud import usage_crud



logger = getLogger(__name__)


class AgentService:
    def __init__(self):
        
        # session
        self.session_service = InMemorySessionService()
        self.app_name = "LearnWeave"
        self.state_manager = StateService()
        self.query_service = QueryService(self.state_manager)
        
        # define agents
        self.planner_retriever_agent = PlannerRetrieverAgent(self.app_name, self.session_service)
        self.coding_agent = ExplainerAgent(self.app_name, self.session_service)
        self.tester_agent = TesterAgent(self.app_name, self.session_service)
        self.image_agent = ImageAgent(self.app_name, self.session_service)
        self.grader_agent = GraderAgent(self.app_name, self.session_service)

        # define Rag service
        self.vector_service = vector_service.VectorService()
        self.contentService = CourseContentService()


    @staticmethod
    async def save_questions(db, questions, chapter_id):
        """ Save questions to database."""
        for q_data in questions:
            if 'answer_a' in q_data.keys():
                questions_crud.create_mc_question(
                    db=db,
                    chapter_id=chapter_id,
                    question=q_data['question'],
                    answer_a=q_data['answer_a'],
                    answer_b=q_data['answer_b'],
                    answer_c=q_data['answer_c'],
                    answer_d=q_data['answer_d'],
                    correct_answer=q_data['correct_answer'],
                    explanation=q_data['explanation']
                )
            else:
                questions_crud.create_ot_question(
                    db=db,
                    chapter_id=chapter_id,
                    question=q_data['question'],
                    correct_answer=q_data['correct_answer']
                )


    async def create_course(self, user_id: str, course_id: int, request: CourseRequest, task_id: str):#, ws_manager: WebSocketConnectionManager):
        """
        Main function for handling the course creation logic. Uses WebSocket for progress.

        Parameters:
        user_id (str): The unique identifier of the user who is creating the course.
        request (CourseRequest): A CourseRequest object containing all necessary details for creating a new course.
        db (Session): The SQLAlchemy database session.
        task_id (str): The unique ID for this course creation task, used for WebSocket communication.
        #ws_manager (WebSocketConnectionManager): Manager to send messages over WebSockets.
        """
        course_db = None
        start_time = time.time()  # Start timing the course creation
        try:
            logger.info("[%s] Starting course creation for user %s", task_id, user_id)

            # Log at the beginning of the task -> prevent over usage of limit
            with get_db_context() as db:
                usage_crud.log_course_creation(
                    db=db,
                    user_id=user_id,
                    course_id=course_id,
                    detail=json.dumps(request.model_dump())
                )
                logger.info("[%s] Usage logged for course creation by user %s", task_id, user_id)



            # Create a memory session for the course creation
            session = await self.session_service.create_session(
                app_name=self.app_name,
                user_id=user_id,
                state={}
            )
            session_id = session.id
            logger.info("[%s] Session created: %s", task_id, session_id)

            # Retrieve documents from database
            with get_db_context() as db:
                all_docs: List[Document] = documents_crud.get_documents_by_ids(db, request.document_ids)
                images: List[Image] = images_crud.get_images_by_ids(db, request.picture_ids)
            
            # Filter to only PDF documents (Gemini doesn't support .docx, .txt, etc.)
            docs = [doc for doc in all_docs if doc.content_type == 'application/pdf']
            logger.info("[%s] Retrieved %d documents (%d PDFs) and %d images.", 
                       task_id, len(all_docs), len(docs), len(images))

            #Add Data to ChromaDB for RAG
            self.contentService.process_course_documents(
                course_id=course_id,
                documents=docs
            )

            # Call combined PlannerRetrieverAgent - gets course info AND learning path in one call
            logger.info("[%s] Calling PlannerRetrieverAgent for course info + learning path...", task_id)
            planner_response = await retry_async_call(
                self.planner_retriever_agent.run,
                user_id=user_id,
                state={},
                content=self.query_service.get_planner_retriever_query(request, docs, images),
                debug=True,
                max_retries=3,
                initial_delay=5,
                backoff_factor=2
            )
            
            if not planner_response or "title" not in planner_response or "chapters" not in planner_response:
                raise ValueError(f"PlannerRetrieverAgent did not return valid response for user {user_id} with course_id {course_id}")
            
            logger.info("[%s] PlannerRetrieverAgent responded with title: %s, %d chapters", 
                       task_id, planner_response['title'], len(planner_response.get('chapters', [])))

            # Generate AI course cover image (optional - skip if fails)
            image_url = DEFAULT_COURSE_IMAGE  # Default placeholder
            try:
                image_response = await self.image_agent.run(
                    user_id=user_id,
                    state={},
                    content="",
                    image_type="course",
                    title=planner_response['title'],
                    description=planner_response['description'],
                )
                if image_response and image_response.get('url'):
                    image_url = image_response.get('url')
                logger.info("[%s] Course cover image URL: %s", task_id, image_url)
            except Exception as e:
                logger.warning("[%s] Failed to generate course cover image, using default: %s", task_id, str(e))

            # Update course in database with info from PlannerRetrieverAgent
            with get_db_context() as db:
                course_db = courses_crud.update_course(
                    db=db,
                    course_id=course_id,
                    session_id=session_id,
                    title=planner_response['title'],
                    description=planner_response['description'],
                    image_url=image_url,
                    total_time_hours=request.time_hours,
                    chapter_count=len(planner_response["chapters"])
                )
                if not course_db:
                    raise ValueError(f"Failed to update course in DB for user {user_id} with course_id {course_id}")
            logger.info("[%s] Course updated in DB with ID: %s", task_id, course_id)

            init_state = CourseState(
                query=request.query,
                time_hours=request.time_hours,
                language=request.language,
                difficulty=request.difficulty,
            )
            # Create initial state for the course
            self.state_manager.create_state(user_id, course_id, init_state)
            logger.info("[%s] Initial state created for course %s", task_id, course_id)

            # Bind documents to this course (bind ALL docs, including non-PDFs)
            with get_db_context() as db:
                for doc in all_docs:
                    documents_crud.update_document(db, int(doc.id), course_id=course_id)
                for img in images:
                    images_crud.update_image(db, int(img.id), course_id=course_id)
            logger.info("[%s] Documents and images bound to course", task_id)

            # Save chapters to state (from combined response)
            self.state_manager.save_chapters(user_id, course_id, planner_response["chapters"])

            async def process_chapter(idx: int, topic: dict):
                try:
                    logger.info("[%s] Processing chapter %d: %s", task_id, idx + 1, topic['caption'])

                    # Get RAG infos for the topic
                    ragInfos = self.contentService.get_rag_infos(course_id, topic)

                    # Get code explanation from coding agent with retry
                    logger.info("[%s] Chapter %d: Calling coding agent...", task_id, idx + 1)
                    response_code = await retry_async_call(
                        self.coding_agent.run,
                        user_id=user_id,
                        state=self.state_manager.get_state(user_id, course_id),
                        content=self.query_service.get_explainer_query(user_id, course_id, idx, request.language, request.difficulty, ragInfos),
                        max_retries=3,
                        initial_delay=5,
                        backoff_factor=2
                    )
                    logger.info("[%s] Chapter %d: Coding agent completed", task_id, idx + 1)

                    # Generate AI chapter cover image (optional)
                    chapter_image_url = DEFAULT_COURSE_IMAGE  # Default placeholder
                    try:
                        chapter_content_summary = "\n".join(topic.get('content', [])[:5])
                        image_response = await self.image_agent.run(
                            user_id=user_id,
                            state={},
                            content=chapter_content_summary,
                            image_type="chapter",
                            chapter_caption=topic['caption'],
                            chapter_content=chapter_content_summary,
                            course_title=planner_response.get('title', ''),
                        )
                        if image_response and image_response.get('url'):
                            chapter_image_url = image_response.get('url')
                        logger.info("[%s] Chapter %d image URL: %s", task_id, idx + 1, chapter_image_url)
                    except Exception as e:
                        logger.warning("[%s] Failed to generate image for chapter %d, using default: %s", task_id, idx + 1, str(e))

                    summary = "\n".join(topic['content'][:3])

                    # Save the chapter in db first
                    logger.info("[%s] Chapter %d: Saving chapter to database...", task_id, idx + 1)
                    with get_db_context() as db:
                        chapter_db = chapters_crud.create_chapter(
                            db=db,
                            course_id=course_id,
                            index=idx + 1,
                            caption=topic['caption'],
                            summary=summary,
                            content=response_code['explanation'] if 'explanation' in response_code else "() => {<p>Something went wrong</p>}",
                            time_minutes=topic['time'],
                            image_url=chapter_image_url,
                        )
                    logger.info("[%s] Chapter %d: Saved to database", task_id, idx + 1)

                    # Get response from tester agent with retry
                    logger.info("[%s] Chapter %d: Calling tester agent...", task_id, idx + 1)
                    
                    # Check if explanation exists before using it
                    if 'explanation' not in response_code:
                        logger.error("[%s] Chapter %d: Missing 'explanation' in coding agent response", task_id, idx + 1)
                        raise ValueError(f"Coding agent response missing 'explanation' field for chapter {idx + 1}")
                    
                    response_tester = await retry_async_call(
                        self.tester_agent.run,
                        user_id=user_id,
                        state=self.state_manager.get_state(user_id=user_id, course_id=course_id),
                        content=self.query_service.get_tester_query(user_id, course_id, idx, response_code["explanation"], request.language, request.difficulty),
                        max_retries=3,
                        initial_delay=5,
                        backoff_factor=2
                    )
                    logger.info("[%s] Chapter %d: Tester agent completed", task_id, idx + 1)

                    # Save questions in db
                    logger.info("[%s] Chapter %d: Saving questions to database...", task_id, idx + 1)
                    with get_db_context() as db:
                        await self.save_questions(db, response_tester['questions'], chapter_db.id)
                    
                    logger.info("[%s] Chapter %d: COMPLETED SUCCESSFULLY", task_id, idx + 1)
                    return chapter_db
                    
                except Exception as e:
                    logger.error("[%s] Chapter %d FAILED: %s", task_id, idx + 1, str(e))
                    logger.error("[%s] Chapter %d traceback: %s", task_id, idx + 1, traceback.format_exc())
                    raise  # Re-raise so gather can catch it

            # Process all chapters in parallel
            chapter_tasks = [
                process_chapter(idx, topic) 
                for idx, topic in enumerate(planner_response["chapters"])
            ]
            
            # Wait for all chapters to be processed
            # Use return_exceptions=True to prevent one chapter failure from failing entire course
            chapter_results = await asyncio.gather(*chapter_tasks, return_exceptions=True)
            
            # Log any chapter failures but continue
            for idx, result in enumerate(chapter_results):
                if isinstance(result, Exception):
                    logger.error("[%s] Chapter %d failed: %s", task_id, idx + 1, str(result))

            # Update course status to finished
            with get_db_context() as db:
                courses_crud.update_course_status(db, course_id, CourseStatus.FINISHED)

            # Calculate and log total time taken
            end_time = time.time()
            total_time = end_time - start_time
            logger.info("[%s] ✅ COURSE CREATION COMPLETED in %.2f seconds (%.2f minutes)", 
                       task_id, total_time, total_time / 60)

            # Send completion signal
            #await ws_manager.send_json_message(task_id, {
            #    "type": "complete",
            #    "data": {"course_id": course_id, "message": "Course created successfully"}
            #})
            print(f"[{task_id}] Sent completion signal.")

        except Exception as _:
            
            error_message = f"Course creation failed: {str(traceback.format_exc())}"
            print(f"[{task_id}] Error during course creation: {error_message}")
            # Log detailed error traceback here if possible, e.g., import traceback; traceback.print_exc()
            if course_db:
                try:
                    with get_db_context() as db:
                        courses_crud.update_course_status(db, course_id, CourseStatus.FAILED)
                        courses_crud.update_course(db, course_id, error_msg=error_message)
                    print(f"[{task_id}] Course {course_id} status updated to FAILED due to error.")
                except Exception as db_error:
                    print(f"[{task_id}] Additionally, failed to update course status to FAILED: {db_error}")
            else:
                print(f"[{task_id}] No course_db to update status, error occurred before course creation.")
            #raise e
        
            #await ws_manager.send_json_message(task_id, {
            #    "type": "error",
            #    "data": {"message": error_message, "course_id": course_id if course_db else None}
            #})
            # Re-raise the exception if you want the background task to show as 'failed' in FastAPI logs
            # or if something upstream needs to handle it. For now, we handle it and inform client.
            # raise e

        finally:
            print(f"[{task_id}] Finished processing create_course background task.")
            # Ensure the database session is closed if it was passed specifically for this task
            # and not managed by FastAPI's Depends. For now, assuming Depends handles it.
            # db.close() # If db session is task-specific and not managed by Depends.

    async def grade_question(self, user_id: str, course_id: int, question: str, correct_answer: str, users_answer: str, 
                             chapter_id: int, db):
        """ Receives an open text question plus answer from the user and returns received points and short feedback """
        query = self.query_service.get_grader_query(question, correct_answer, users_answer)
        grader_response = await self.grader_agent.run(
            user_id=user_id,
            state=self.state_manager.get_state(user_id=user_id, course_id=course_id),
            content=query
        )

        # Log usage of grading
        usage_crud.log_usage(
            db=db,
            user_id=user_id,
            action="grade_question",
            course_id=course_id,
            chapter_id=chapter_id,
            details=json.dumps({
                "course_id": course_id,
                "question": question,
                "correct_answer": correct_answer,
                "users_answer": users_answer,
                "points": grader_response['points'],
                "explanation": grader_response['explanation']
            })
        )

        return grader_response['points'], grader_response['explanation']

