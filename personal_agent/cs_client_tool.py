"""Tool that lets the personal agent talk to the bank's customer service
agent over A2A, propagating the current session's contextId so both agents
(and the env) share one conversation identity."""

import os
import uuid

import httpx
from a2a.client import ClientConfig, ClientFactory, minimal_agent_card
from a2a.client.errors import A2AClientError, A2AClientHTTPError
from a2a.types import Message, Part, Role, Task, TextPart
from google.adk.tools import ToolContext

from env_toolset import session_id

CS_AGENT_URL = os.environ["CS_AGENT_URL"]

_TIMEOUT_S = 300.0


def _text_of_message(message: Message) -> str:
    texts = []
    for part in message.parts or []:
        root = getattr(part, "root", part)
        if isinstance(root, TextPart) and root.text:
            texts.append(root.text)
    return "\n".join(texts)


def _text_of_task(task: Task) -> str:
    texts = []
    for artifact in task.artifacts or []:
        for part in artifact.parts or []:
            root = getattr(part, "root", part)
            if isinstance(root, TextPart) and root.text:
                texts.append(root.text)
    if task.status is not None and task.status.message is not None:
        text = _text_of_message(task.status.message)
        if text:
            texts.append(text)
    return "\n".join(texts)


async def ask_customer_service_with_context(message: str, context_id: str) -> str:
    """Send a message to CS using an explicit contextId."""
    outgoing = Message(
        message_id=uuid.uuid4().hex,
        role=Role.user,
        parts=[Part(root=TextPart(text=message))],
        context_id=context_id,
    )
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as http_client:
            client = ClientFactory(
                ClientConfig(streaming=False, httpx_client=http_client)
            ).create(minimal_agent_card(CS_AGENT_URL, ["JSONRPC"]))
            reply = ""
            async for event in client.send_message(outgoing):
                if isinstance(event, Message):
                    reply = _text_of_message(event) or reply
                elif isinstance(event, tuple) and isinstance(event[0], Task):
                    reply = _text_of_task(event[0]) or reply
    except (A2AClientError, A2AClientHTTPError, httpx.HTTPError) as e:
        return (
            "DECISION: UNKNOWN\n"
            "ACTION_OWNER: personal-agent\n"
            "VERIFICATION: unknown\n"
            "REQUIRED_FIELDS: none\n"
            "RECOMMENDED_TOOL: none\n"
            f"POLICY_BASIS: Customer service transport failed: {type(e).__name__}.\n"
            "NEXT_STEP_FOR_PERSONAL: Briefly apologize, ask for one retry or collect any missing identity details, and do not claim a bank-side action completed.\n"
            "USER_SAFE_SUMMARY: I could not reach customer service cleanly; please try that request once more."
        )
    return reply or "[no response from customer service]"


async def ask_customer_service(message: str, tool_context: ToolContext) -> str:
    """Send a message to the bank's customer service agent and return its reply.

    The conversation with customer service persists for this whole session,
    so you can ask follow-up questions and they will remember the context.
    """
    return await ask_customer_service_with_context(message, session_id(tool_context))


async def call_customer_service(message: str, tool_context: ToolContext) -> str:
    """Alias for model/tool-call stability; sends the message to CS."""
    return await ask_customer_service(message, tool_context)
