"""The shared gpt-6-luna model, reached through the Portkey gateway's Responses API.

gpt-6-luna rejects function tools on /v1/chat/completions while reasoning is
on, so the agents use /v1/responses, which supports tools with reasoning.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"


def portkey_api_key() -> str:
    """PORTKEY_API_KEY from the project's .env, falling back to the parent directory's .env."""
    for env_file in (PROJECT_ROOT / ".env", PROJECT_ROOT.parent / ".env"):
        load_dotenv(env_file)
        if key := os.environ.get("PORTKEY_API_KEY"):
            return key
    raise RuntimeError("PORTKEY_API_KEY is not set in .env (project root or parent directory).")


def build_model() -> OpenAIResponsesModel:
    """gpt-6-luna via Portkey's Responses API, with the model's default reasoning left on."""
    key = portkey_api_key()
    client = AsyncOpenAI(base_url=PORTKEY_BASE_URL, api_key=key, default_headers={"x-portkey-api-key": key})
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
