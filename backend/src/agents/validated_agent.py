"""
Validated Code Agent - Shared logic for agents that generate code requiring validation.
Extracts the common feedback loop pattern used by ExplainerAgent and TesterAgent.
"""
import json
from typing import Dict, Any
from logging import getLogger

from google.genai import types

from .agent import StandardAgent
from .code_checker.code_checker import ESLintValidator, clean_up_response
from .utils import create_text_query

logger = getLogger(__name__)


class ValidatedCodeAgent:
    """
    Wrapper for agents that generate code requiring validation.
    Implements an automatic feedback loop with ESLint validation.
    """
    
    def __init__(
        self, 
        inner_agent: StandardAgent, 
        validator: ESLintValidator = None,
        max_iterations: int = 5,
        error_message_template: str = None
    ):
        """
        Initialize the validated code agent.
        
        Args:
            inner_agent: The underlying agent that generates code
            validator: ESLint validator instance (creates new one if None)
            max_iterations: Maximum number of validation attempts
            error_message_template: Custom error feedback template (optional)
        """
        self.inner_agent = inner_agent
        self.validator = validator or ESLintValidator()
        self.max_iterations = max_iterations
        self.error_message_template = error_message_template or self._default_error_template()
    
    def _default_error_template(self) -> str:
        """Default error feedback template"""
        return """
You were prompted before, but the code that you output did not pass the syntax validation check.
Your previous code:
{code}

Your code generated the following errors:
{errors}

Please try again and rewrite your code from scratch, without explanation.
Your response should start with () => and end with a curly brace.
"""
    
    def _build_error_feedback(self, code: str, errors: list) -> types.Content:
        """Build feedback content for the agent based on validation errors"""
        error_text = self.error_message_template.format(
            code=code,
            errors=json.dumps(errors, indent=2)
        )
        return create_text_query(error_text)
    
    def _build_failure_response(self, errors: list) -> Dict[str, Any]:
        """Build response when all validation attempts fail"""
        return {
            "success": False,
            "explanation": "return (<div className='p-8 text-center'><div className='bg-red-50 border-2 border-red-300 rounded-lg p-6 max-w-2xl mx-auto'><h3 className='text-xl font-bold text-red-700 mb-2'>⚠️ Content Generation Error</h3><p className='text-gray-700'>Failed to generate valid content after multiple attempts. Please try refreshing or rephrasing your request.</p></div></div>);",
            "message": f"Code did not pass syntax check after {self.max_iterations} iterations. Errors: \n{json.dumps(errors, indent=2)}",
        }
    
    async def run_with_validation(
        self, 
        user_id: str, 
        state: dict, 
        content: types.Content,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Run the agent with automatic code validation and correction loop.
        
        Args:
            user_id: The user ID
            state: Agent state dictionary
            content: Initial content/query for the agent
            debug: Enable debug logging
        
        Returns:
            Dictionary with 'success' bool and 'explanation' (code) or 'message' (error)
        """
        validation_check = {"errors": []}
        
        for iteration in range(self.max_iterations):
            if debug:
                logger.info(f"Validation iteration {iteration + 1}/{self.max_iterations}")
            
            # Run the inner agent
            output = (await self.inner_agent.run(
                user_id=user_id, 
                state=state, 
                content=content
            ))['explanation']
            
            # Validate the generated code
            validation_check = self.validator.validate_jsx(output)
            
            if validation_check['valid']:
                logger.info("Code validation passed")
                return {
                    "success": True,
                    "explanation": clean_up_response(output),
                }
            
            # Code failed validation - build feedback for next iteration
            logger.warning(
                f"Code validation failed (iteration {iteration + 1}/{self.max_iterations}). "
                f"Errors: {json.dumps(validation_check['errors'], indent=2)}"
            )
            content = self._build_error_feedback(output, validation_check['errors'])
        
        # All iterations exhausted without success
        logger.error(f"Code validation failed after {self.max_iterations} iterations")
        return self._build_failure_response(validation_check['errors'])
