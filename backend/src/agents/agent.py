"""
This file defines the base class for all agents.
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

from google.genai import types

from ..config import settings
from .retry_handler import RetryConfig, with_retry

if not settings.AGENT_DEBUG_MODE:
    logging.getLogger("google_adk.google.adk.models.google_llm").setLevel(logging.WARNING)



class StandardAgent(ABC):
    """ This is the standard agent without structured output """
    @abstractmethod
    def __init__(self, app_name: str, session_service):
        self.app_name = app_name
        self.session_service = session_service

    async def run(self, user_id: str, state: dict, content: types.Content, debug: bool = False) -> Dict[str, Any]:
        """
        Wraps the event handling and runner from adk into a simple run() method.
        
        :param user_id: id of the user
        :param state: the state created from the StateService
        :param content: the user query as a type.Content object
        :param debug: if true the method will print auxiliary outputs (all events)
        :return: the parsed dictionary response from the agent
        """
        
        @with_retry(RetryConfig(max_retries=1, retry_delay=2.0))
        async def _run_with_retry():
            if debug:
                print(f"[Debug] Running agent with state: {json.dumps(state, indent=2)}")

            # Create session
            session = await self.session_service.create_session(
                app_name=self.app_name,
                user_id=user_id,
                state=state
            )
            session_id = session.id

            # We iterate through events to find the final answer
            async for event in self.runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
                if debug:
                    print(f"  [Event] Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()}, Content: {event.content}")

                # is_final_response() marks the concluding message for the turn
                if event.is_final_response():
                    if event.content and event.content.parts:
                        # Assuming text response in the first part
                        return {
                            "status": "success",
                            "explanation": event.content.parts[0].text
                        }
                    elif event.actions and event.actions.escalate:  # Handle potential errors/escalations
                        error_msg = f"Agent escalated: {event.error_message or 'No specific message.'}"
                        return {"status": "error", "message": error_msg}
            
            # If we get here, no final response was received
            return {"status": "error", "message": "Agent did not give a final response. Unknown error occurred."}
        
        try:
            return await _run_with_retry()
        except Exception as e:
            return {"status": "error", "message": str(e)}


class StructuredAgent(ABC):
    """ This is an agent that returns structured output. """
    @abstractmethod
    def __init__(self, app_name: str, session_service):
        self.app_name = app_name
        self.session_service = session_service

    async def run(self, user_id: str, state: dict, content: types.Content, debug: bool = False, max_retries: int = 1, retry_delay: float = 2.0) -> Dict[str, Any]:
        """
        Wraps the event handling and runner from adk into a simple run() method.
        
        :param user_id: id of the user
        :param state: the state created from the StateService
        :param content: the user query as a type.Content object
        :param debug: if true the method will print auxiliary outputs (all events)
        :return: the parsed dictionary response from the agent
        """
        
        @with_retry(RetryConfig(max_retries=max_retries, retry_delay=retry_delay))
        async def _run_with_retry():
            session = await self.session_service.create_session(
                app_name=self.app_name,
                user_id=user_id,
                state=state
            )
            session_id = session.id

            async for event in self.runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=content
            ):
                if debug:
                    print(f"[Event] Author: {event.author}, Type: {type(event).__name__}, "
                          f"Final: {event.is_final_response()}")

                if event.is_final_response():
                    if event.content and event.content.parts:
                        # Get the text from the Part object
                        json_text = event.content.parts[0].text

                        # Try parsing the json response into a dictionary
                        dict_response = json.loads(json_text)
                        dict_response['status'] = 'success'
                        return dict_response
                            
                    elif event.actions and event.actions.escalate:  # Handle potential errors/escalations
                        error_msg = f"Agent escalated: {event.error_message or 'No specific message.'}"
                        return {"status": "error", "message": error_msg}
            
            # If we get here, no final response was received
            return {"status": "error", "message": "Agent did not give a final response. Unknown error occurred."}
        
        try:
            return await _run_with_retry()
        except json.JSONDecodeError as e:
            if debug:
                print(f"Error parsing JSON response: {e}")
            return {"status": "error", "message": f"Error parsing JSON response: {e}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}