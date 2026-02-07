"""
This defines a ExplainerAgent class which wraps the event handling,
runner from adk and calls to visualizer agent into a simple run() method
"""
import json
import os
from typing import AsyncGenerator, Optional, Dict, Any

from google.adk.agents import LlmAgent, BaseAgent, LoopAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.genai import types
from litellm import max_tokens

from ..code_checker.code_checker import ESLintValidator, clean_up_response
from ..agent import StandardAgent
from ..utils import load_instructions_from_files, create_text_query
from ..validated_agent import ValidatedCodeAgent


class CodingExplainer(StandardAgent):
    def __init__(self, app_name: str, session_service):
        files = ["explainer_agent/instructions.txt"]
        files.extend([f"explainer_agent/plugin_docs/{filename}" for filename in os.listdir(os.path.join(os.path.dirname(__file__), "plugin_docs"))])
        full_instructions = load_instructions_from_files(sorted(files))

        dynamic_instructions = """
END OF INSTRUCTIONS
- - - - - -
## Current course creation state
Initial Interaction:
LearnWeave: "What do you want to learn today?"
User: "{query}"

All chapters, created by the Planner Agent:
{chapters_str}

Please only include content about the chapter that is assigned to you in the following query.
        """

        # LiteLlm("openai/gpt-4.1-2025-04-14")
        # gemini-2.5-pro
        # gemini-2.5-flash
        # gemini-2.5-flash-lite-preview-06-17
        """LiteLlm(
                model="anthropic/claude-sonnet-4-20250514",
                reasoning_effort="low",
                max_tokens=8100,
            )"""
        explainer_agent = LlmAgent(
            name="explainer_agent",
            model="gemini-2.5-flash",
            description="Agent for creating engaging visual explanations using react",
            global_instruction=lambda _: full_instructions,
            instruction=dynamic_instructions,
            
        )

        # Assign attributes
        self.app_name = app_name
        self.session_service = session_service
        self.runner = Runner(
            agent=explainer_agent,
            app_name=self.app_name,
            session_service=self.session_service,
        )


class ExplainerAgent(StandardAgent):
    """
    Custom loop agent to provide a feedback loop between the explainer and the react parser.
    Uses ValidatedCodeAgent for shared validation logic.
    """
    def __init__(self, app_name: str, session_service, iterations = 3):
        self.explainer = CodingExplainer(app_name=app_name, session_service=session_service)
        self.validated_agent = ValidatedCodeAgent(
            inner_agent=self.explainer,
            validator=ESLintValidator(),
            max_iterations=iterations
        )

    async def run(self, user_id: str, state: dict, content: types.Content, debug: bool = False) -> Dict[str, Any]:
        """
        Run the explainer agent with automatic code validation.
        
        :param user_id: id of the user
        :param state: the state created from the StateService
        :param content: the user query as a type.Content object
        :param debug: if true the method will print auxiliary outputs (all events)
        :return: the parsed dictionary response from the agent
        """
        return await self.validated_agent.run_with_validation(
            user_id=user_id,
            state=state,
            content=content,
            debug=debug
        )
