"""
PlannerRetrieverAgent: Merges InfoAgent and PlannerAgent functionality
Generates both course info (title, description) and learning path (chapters) in one call
"""
from typing import Dict, Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner

from ..agent import StructuredAgent
from ..utils import load_instruction_from_file
from .schema import CourseInfoWithPath


class PlannerRetrieverAgent(StructuredAgent):
    """
    Combined agent that retrieves course information AND plans the learning path.
    This eliminates redundant LLM calls by doing both tasks in a single invocation.
    """
    
    def __init__(self, app_name: str, session_service):
        # Create the combined planner-retriever agent
        planner_retriever_agent = LlmAgent(
            name="planner_retriever_agent",
            model="gemini-2.5-flash",
            output_schema=CourseInfoWithPath,
            description="Agent for generating course info and planning learning paths",
            instruction=load_instruction_from_file("planner_retriever_agent/instructions.txt"),
            disallow_transfer_to_parent=True,
            disallow_transfer_to_peers=True,
        )

        # Initialize runner
        self.app_name = app_name
        self.session_service = session_service
        self.runner = Runner(
            agent=planner_retriever_agent,
            app_name=self.app_name,
            session_service=self.session_service,
        )
