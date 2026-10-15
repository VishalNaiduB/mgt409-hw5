"""The shared gpt-6-luna model, reached through the Portkey gateway."""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
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


def build_model() -> OpenAIChatModel:
    """gpt-6-luna via Portkey. Don't set max_tokens: the model rejects it (it wants max_completion_tokens)."""
    key = portkey_api_key()
    client = AsyncOpenAI(base_url=PORTKEY_BASE_URL, api_key=key, default_headers={"x-portkey-api-key": key})
    return OpenAIChatModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
