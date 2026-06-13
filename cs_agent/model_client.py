"""ADK Gemini client setup for the hackathon runtime."""

import os
from functools import cached_property

from google.adk.models.google_llm import Gemini
from google.genai import Client, types

MODEL = os.environ.get("MODEL", "gemini-3.5-flash")
VERTEX_BASE_URL = "https://aiplatform.googleapis.com"


class ApiKeyVertexGemini(Gemini):
    """Force Vertex Express API-key auth when GOOGLE_API_KEY is present."""

    @cached_property
    def api_client(self) -> Client:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return super().api_client

        return Client(
            vertexai=True,
            api_key=api_key,
            http_options=types.HttpOptions(
                api_version="v1",
                base_url=VERTEX_BASE_URL,
            ),
        )


def chat_model() -> Gemini:
    return ApiKeyVertexGemini(model=MODEL)
