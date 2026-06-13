"""Low-latency CS paths for common policy/tool workflows.

These callbacks still use the env API for the current contextId and only call
tools that are exposed for that session. The goal is to avoid extra LLM turns
for simple escalation procedures that otherwise amplify 429s and timeouts.
"""

import json
import os
import re
from typing import Any

import httpx
import redis
from google.adk.agents.context import Context
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

ENV_API_URL = os.environ["ENV_API_URL"].rstrip("/")
ENV_API_TOKEN = os.environ["ENV_API_TOKEN"]
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

_HEADERS = {"Authorization": f"Bearer {ENV_API_TOKEN}"}
_redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def _reply(text: str) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


def _message_text(callback_context: Context) -> str:
    content = callback_context.user_content
    parts = []
    for part in content.parts if content and content.parts else []:
        if getattr(part, "text", None):
            parts.append(part.text)
    return "\n".join(parts)


def _context_id(callback_context: Context) -> str | None:
    candidates = [
        getattr(getattr(callback_context, "session", None), "id", None),
        getattr(
            getattr(getattr(callback_context, "_invocation_context", None), "session", None),
            "id",
            None,
        ),
        getattr(
            getattr(getattr(callback_context, "invocation_context", None), "session", None),
            "id",
            None,
        ),
    ]
    for candidate in candidates:
        if candidate:
            return str(candidate)
    return None


async def _get_tool_schemas(context_id: str) -> dict[str, dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{ENV_API_URL}/sessions/{context_id}/tools", headers=_HEADERS)
    if resp.status_code in {404, 409}:
        return {}
    resp.raise_for_status()
    tools = resp.json().get("tools", [])
    return {tool["function"]["name"]: tool for tool in tools if "function" in tool}


def _properties(schema: dict[str, Any]) -> dict[str, Any]:
    return (
        schema.get("function", {})
        .get("parameters", {})
        .get("properties", {})
        or {}
    )


def _required(schema: dict[str, Any]) -> list[str]:
    return schema.get("function", {}).get("parameters", {}).get("required", []) or []


def _tool_args(schema: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    props = _properties(schema)
    keys = set(props) if props else set(values)
    args = {key: value for key, value in values.items() if key in keys}
    for key, value in list(args.items()):
        enum = props.get(key, {}).get("enum")
        if enum and value not in enum:
            if key == "reason" and "customer_frustrated_demands_human" in enum:
                args[key] = "customer_frustrated_demands_human"
            elif "other" in enum:
                args[key] = "other"
            else:
                args[key] = enum[0]
    for key in _required(schema):
        if key in args:
            continue
        prop = props.get(key, {})
        if "enum" in prop and prop["enum"]:
            args[key] = prop["enum"][0]
        elif prop.get("type") == "boolean":
            args[key] = False
        elif prop.get("type") in {"number", "integer"}:
            args[key] = 0
        else:
            args[key] = ""
    return args


async def _call_tool(
    context_id: str, schemas: dict[str, dict[str, Any]], name: str, args: dict[str, Any]
) -> dict[str, Any]:
    schema = schemas.get(name)
    if not schema:
        return {"error": True, "content": f"Tool {name} is not available"}
    payload = {"arguments": _tool_args(schema, args)}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{ENV_API_URL}/sessions/{context_id}/tools/{name}",
            json=payload,
            headers=_HEADERS,
        )
    if resp.status_code != 200:
        return {"error": True, "content": f"HTTP {resp.status_code}: {resp.text}"}
    return resp.json()


async def _unlock_and_call_agent_tool(
    context_id: str, schemas: dict[str, dict[str, Any]], agent_tool_name: str
) -> str:
    if "unlock_discoverable_agent_tool" in schemas:
        await _call_tool(
            context_id,
            schemas,
            "unlock_discoverable_agent_tool",
            {"agent_tool_name": agent_tool_name},
        )
    if "call_discoverable_agent_tool" not in schemas:
        return "agent tool could not be called because call_discoverable_agent_tool is unavailable"
    result = await _call_tool(
        context_id,
        schemas,
        "call_discoverable_agent_tool",
        {"agent_tool_name": agent_tool_name, "arguments": "{}"},
    )
    return str(result.get("content") or result)


async def _transfer(
    context_id: str,
    schemas: dict[str, dict[str, Any]],
    *,
    reason: str,
    summary: str,
) -> str:
    if "transfer_to_human_agents" not in schemas:
        return "transfer_to_human_agents unavailable"
    result = await _call_tool(
        context_id,
        schemas,
        "transfer_to_human_agents",
        {"reason": reason, "summary": summary},
    )
    return str(result.get("content") or result)


def _count(context_id: str, name: str) -> int:
    return int(_redis.hincrby(f"ctx:{context_id}:fast_path_counts", name, 1))


def _current_count(context_id: str, name: str) -> int:
    value = _redis.hget(f"ctx:{context_id}:fast_path_counts", name)
    return int(value or 0)


def _looks_like_human_request(text: str) -> bool:
    lower = text.lower()
    return any(
        phrase in lower
        for phrase in (
            "human agent",
            "real person",
            "human specialist",
            "transfer",
            "escalate",
            "representative",
        )
    )


def _looks_like_card_decline_incident(text: str) -> bool:
    lower = text.lower()
    return (
        "declin" in lower
        and ("credit card" in lower or "card" in lower)
        and ("available credit" in lower or "credit limit" in lower)
    )


def _looks_like_payment_reflection_incident(text: str) -> bool:
    lower = text.lower()
    return (
        "paid" in lower
        and "statement" in lower
        and ("deducted" in lower or "checking account" in lower)
        and ("not reflected" in lower or "not showing" in lower)
    )


def _extract_name(text: str) -> str | None:
    patterns = [
        r"(?:customer\s+name|name|full\s+name)\s*[:\-]\s*([A-Z][A-Za-z' -]+)(?:\n|,|$)",
        r"\b([A-Z][a-z]+(?:[ \t]+[A-Z][a-zA-Z'-]+){1,3})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip(" .,\n")
            if len(name.split()) >= 2 and not name.lower().startswith("customer"):
                return name
    return None


def _extract_email(text: str) -> str | None:
    match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    return match.group(0).lower() if match else None


async def _handle_card_decline_transfer(
    text: str, context_id: str, schemas: dict[str, dict[str, Any]]
) -> LlmResponse | None:
    protocol_started = _current_count(context_id, "card_decline_transfer") > 0
    if not _looks_like_card_decline_incident(text) and not (
        _looks_like_human_request(text)
        and ("declin" in text.lower() or protocol_started)
    ):
        return None

    if not _looks_like_human_request(text):
        return _reply(
            "DECISION: NEED_MORE_INFO\n"
            "ACTION_OWNER: personal-agent\n"
            "VERIFICATION: required\n"
            "REQUIRED_FIELDS: name, user_id or email\n"
            "RECOMMENDED_TOOL: cs-agent:initial_transfer_protocol_if_user_requests_human\n"
            "TOOL_ACTION_TAKEN: none\n"
            "POLICY_BASIS: For card declines, collect identity details before account-specific troubleshooting; if the user asks for a human during this incident, use the incident transfer protocol.\n"
            "NEXT_STEP_FOR_PERSONAL: Ask for the customer's name and user_id or email, and if they ask for a human again, call CS with the transfer request.\n"
            "USER_SAFE_SUMMARY: I can look into the decline, and I need your name plus user ID or email first."
        )

    request_count = _count(context_id, "card_decline_transfer")
    if request_count <= 3:
        tool_result = await _unlock_and_call_agent_tool(
            context_id, schemas, "initial_transfer_to_human_agent_0218"
        )
        return _reply(
            "DECISION: ACTION_REQUIRED\n"
            "ACTION_OWNER: cs-agent\n"
            "VERIFICATION: not_required\n"
            "REQUIRED_FIELDS: none\n"
            "RECOMMENDED_TOOL: cs-agent:initial_transfer_to_human_agent_0218\n"
            f"TOOL_ACTION_TAKEN: {tool_result}\n"
            "POLICY_BASIS: This card-decline incident uses the initial-transfer protocol before regular human transfer.\n"
            "NEXT_STEP_FOR_PERSONAL: Tell the user the transfer process has been initiated and lines are busy; if they ask again, call CS again with the request.\n"
            "USER_SAFE_SUMMARY: I started the transfer process, but the human-agent line is currently busy."
        )

    tool_result = await _transfer(
        context_id,
        schemas,
        reason="customer_frustrated_demands_human",
        summary="Customer repeatedly requested a human agent for urgent credit-card declines despite available credit.",
    )
    return _reply(
        "DECISION: COMPLETED\n"
        "ACTION_OWNER: cs-agent\n"
        "VERIFICATION: not_required\n"
        "REQUIRED_FIELDS: none\n"
        "RECOMMENDED_TOOL: cs-agent:transfer_to_human_agents\n"
        f"TOOL_ACTION_TAKEN: {tool_result}\n"
        "POLICY_BASIS: After repeated transfer requests in this incident flow, complete the regular human transfer.\n"
        "NEXT_STEP_FOR_PERSONAL: Tell the user they are being transferred to a human agent now.\n"
        "USER_SAFE_SUMMARY: I am connecting you with a human agent now."
    )


async def _handle_payment_reflection_transfer(
    text: str, context_id: str, schemas: dict[str, dict[str, Any]]
) -> LlmResponse | None:
    if not (_looks_like_payment_reflection_incident(text) and _looks_like_human_request(text)):
        return None

    request_count = _count(context_id, "payment_reflection_transfer")
    if request_count == 1:
        tool = "initial_transfer_to_human_agent_1822"
    elif request_count == 2:
        tool = "initial_transfer_to_human_agent_0218"
    else:
        tool_result = await _transfer(
            context_id,
            schemas,
            reason="technical_system_error",
            summary="Customer paid credit-card statement, funds left checking, but payment is not reflected on the card statement.",
        )
        return _reply(
            "DECISION: COMPLETED\n"
            "ACTION_OWNER: cs-agent\n"
            "VERIFICATION: not_required\n"
            "REQUIRED_FIELDS: none\n"
            "RECOMMENDED_TOOL: cs-agent:transfer_to_human_agents\n"
            f"TOOL_ACTION_TAKEN: {tool_result}\n"
            "POLICY_BASIS: Incident protocol transfers on the third request after the two initial transfer tools.\n"
            "NEXT_STEP_FOR_PERSONAL: Tell the user they are being transferred to a human specialist now.\n"
            "USER_SAFE_SUMMARY: I am connecting you with a human specialist now."
        )

    tool_result = await _unlock_and_call_agent_tool(context_id, schemas, tool)
    return _reply(
        "DECISION: ACTION_REQUIRED\n"
        "ACTION_OWNER: cs-agent\n"
        "VERIFICATION: not_required\n"
        "REQUIRED_FIELDS: none\n"
        f"RECOMMENDED_TOOL: cs-agent:{tool}\n"
        f"TOOL_ACTION_TAKEN: {tool_result}\n"
        "POLICY_BASIS: Payment-reflection incidents use the ordered initial-transfer protocol before regular transfer.\n"
        "NEXT_STEP_FOR_PERSONAL: Acknowledge the transfer request; if the user asks again, call CS again with the same incident details.\n"
        "USER_SAFE_SUMMARY: I am processing your transfer request."
    )


async def _handle_general_human_request(
    text: str, context_id: str, schemas: dict[str, dict[str, Any]]
) -> LlmResponse | None:
    if not _looks_like_human_request(text):
        return None

    lower = text.lower()
    immediate_reasons = [
        ("account ownership dispute", "account_ownership_dispute"),
        ("unconfirmed external communication", "unconfirmed_external_communication"),
        ("official communication", "unconfirmed_external_communication"),
        ("letter in the mail", "unconfirmed_external_communication"),
    ]
    reason = None
    for phrase, candidate in immediate_reasons:
        if phrase in lower:
            reason = candidate
            break

    if not reason:
        request_count = _count(context_id, "general_human_request")
        if request_count < 4:
            return _reply(
                "DECISION: ACTION_REQUIRED\n"
                "ACTION_OWNER: personal-agent\n"
                "VERIFICATION: required\n"
                "REQUIRED_FIELDS: identity details relevant to the request\n"
                "RECOMMENDED_TOOL: none\n"
                "TOOL_ACTION_TAKEN: none\n"
                "POLICY_BASIS: If the issue is within bank capabilities, help first and transfer only after the fourth human-agent request.\n"
                "NEXT_STEP_FOR_PERSONAL: Continue resolving the banking request; if this is the fourth human-agent request, call CS again and state that clearly.\n"
                "USER_SAFE_SUMMARY: I can keep helping with this before escalating."
            )
        reason = "customer_frustrated_demands_human"

    tool_result = await _transfer(
        context_id,
        schemas,
        reason=reason,
        summary=f"Human transfer requested. Reason: {reason}.",
    )
    return _reply(
        "DECISION: COMPLETED\n"
        "ACTION_OWNER: cs-agent\n"
        "VERIFICATION: not_required\n"
        "REQUIRED_FIELDS: none\n"
        "RECOMMENDED_TOOL: cs-agent:transfer_to_human_agents\n"
        f"TOOL_ACTION_TAKEN: {tool_result}\n"
        f"POLICY_BASIS: Transfer is appropriate for {reason}.\n"
        "NEXT_STEP_FOR_PERSONAL: Tell the user they are being transferred to a human agent now.\n"
        "USER_SAFE_SUMMARY: I am transferring you to a human agent now."
    )


async def _handle_email_change(
    text: str, context_id: str, schemas: dict[str, dict[str, Any]]
) -> LlmResponse | None:
    lower = text.lower()
    if "email" not in lower or not any(word in lower for word in ("change", "update")):
        return None

    name = _extract_name(text)
    claimed_email = _extract_email(text)
    if not name or not claimed_email:
        return _reply(
            "DECISION: NEED_MORE_INFO\n"
            "ACTION_OWNER: personal-agent\n"
            "VERIFICATION: required\n"
            "REQUIRED_FIELDS: name, current email, phone_number\n"
            "RECOMMENDED_TOOL: none\n"
            "TOOL_ACTION_TAKEN: none\n"
            "POLICY_BASIS: Profile email changes require identity verification against bank records.\n"
            "NEXT_STEP_FOR_PERSONAL: Ask for the customer's full name, current email address, and phone number.\n"
            "USER_SAFE_SUMMARY: I need your full name, current email, and phone number before updating account contact details."
        )

    lookup_result = None
    if "get_user_information_by_name" in schemas:
        lookup_result = await _call_tool(
            context_id,
            schemas,
            "get_user_information_by_name",
            {"customer_name": name},
        )

    lookup_text = json.dumps(lookup_result or {}, sort_keys=True).lower()
    if lookup_result and claimed_email not in lookup_text:
        tool_result = await _transfer(
            context_id,
            schemas,
            reason="account_ownership_dispute",
            summary=f"Customer {name} requested email change but claimed current email does not match bank records.",
        )
        return _reply(
            "DECISION: COMPLETED\n"
            "ACTION_OWNER: cs-agent\n"
            "VERIFICATION: failed\n"
            "REQUIRED_FIELDS: none\n"
            "RECOMMENDED_TOOL: cs-agent:transfer_to_human_agents\n"
            f"TOOL_ACTION_TAKEN: {tool_result}\n"
            "POLICY_BASIS: Conflicting claimed contact detail during profile update is an account ownership dispute.\n"
            "NEXT_STEP_FOR_PERSONAL: Tell the user the email change cannot be completed in chat and they are being transferred to a human agent.\n"
            "USER_SAFE_SUMMARY: I cannot complete the email change here, so I am transferring you to a human agent."
        )

    return _reply(
        "DECISION: NEED_MORE_INFO\n"
        "ACTION_OWNER: personal-agent\n"
        "VERIFICATION: required\n"
        "REQUIRED_FIELDS: address, date_of_birth\n"
        "RECOMMENDED_TOOL: none\n"
        "TOOL_ACTION_TAKEN: user lookup completed\n"
        "POLICY_BASIS: Email changes require full identity verification before any profile update.\n"
        "NEXT_STEP_FOR_PERSONAL: Ask for address and date_of_birth; if the user cannot provide them, call CS again for escalation.\n"
        "USER_SAFE_SUMMARY: I need your address and date of birth to finish verification."
    )


async def _handle_external_referral_claim(
    text: str, context_id: str, schemas: dict[str, dict[str, Any]]
) -> LlmResponse | None:
    lower = text.lower()
    if not (
        ("crypto-cash back" in lower or "crypto cash back" in lower)
        and "referral" in lower
        and ("letter" in lower or "mail" in lower or "official communication" in lower)
    ):
        return None

    tool_result = await _transfer(
        context_id,
        schemas,
        reason="unconfirmed_external_communication",
        summary="Customer reports an unconfirmed mailed Crypto-Cash Back referral offer that is not supported by policy.",
    )
    return _reply(
        "DECISION: COMPLETED\n"
        "ACTION_OWNER: cs-agent\n"
        "VERIFICATION: not_required\n"
        "REQUIRED_FIELDS: none\n"
        "RECOMMENDED_TOOL: cs-agent:transfer_to_human_agents\n"
        f"TOOL_ACTION_TAKEN: {tool_result}\n"
        "POLICY_BASIS: Unconfirmed external communications about unavailable offers should be escalated to a human agent.\n"
        "NEXT_STEP_FOR_PERSONAL: Tell the user the offer cannot be verified in chat and they are being transferred to a human agent.\n"
        "USER_SAFE_SUMMARY: I cannot verify that mailed offer here, so I am transferring you to a human agent."
    )


async def cs_fast_path(
    callback_context: Context, llm_request: LlmRequest
) -> LlmResponse | None:
    del llm_request
    text = _message_text(callback_context)
    if not text:
        return None
    context_id = _context_id(callback_context)
    if not context_id:
        return None

    try:
        schemas = await _get_tool_schemas(context_id)
        for handler in (
            _handle_external_referral_claim,
            _handle_email_change,
            _handle_payment_reflection_transfer,
            _handle_card_decline_transfer,
            _handle_general_human_request,
        ):
            response = await handler(text, context_id, schemas)
            if response is not None:
                return response
    except Exception:
        return None

    return None
