"""Utilities for selecting the default LLM model at runtime."""

import os

from google.adk.models.lite_llm import LiteLlm


def get_llm_model():
    """
    Return the model object/name expected by ADK's LlmAgent.

    - LLM_PROVIDER=bedrock|aws: returns LiteLlm configured for AWS Bedrock
    - otherwise: returns Gemini model name string
    """
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

    if provider in {"bedrock", "aws"}:
        bedrock_region = os.getenv("BEDROCK_REGION")
        if bedrock_region and not os.getenv("AWS_REGION"):
            os.environ["AWS_REGION"] = bedrock_region

        model_name = os.getenv(
            "LITELLM_MODEL",
            os.getenv(
                "BEDROCK_MODEL_ID",
                "bedrock/us.anthropic.claude-3-5-sonnet-20240620-v1:0",
            ),
        )
        return LiteLlm(model=model_name)

    return os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash")
