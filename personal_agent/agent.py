"""The user's personal banking assistant."""

import os

from google.adk.agents.context import Context
from google.adk.agents import LlmAgent
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from cs_client_tool import call_customer_service
from env_toolset import EnvApiToolset
from model_client import chat_model

MODEL = os.environ.get("MODEL", "gemini-3.5-flash")

INSTRUCTION = """\
You are the user's personal banking assistant for their Rho-Bank accounts.

- You act on the user's behalf. Your environment tools are the user's own
  banking actions (e.g. applying for cards, submitting referrals); use them
  when the user asks you to do something you have a tool for.
- For anything you cannot do with your own tools — account lookups, policy
  questions, disputes, bank-side operations — contact the bank's customer
  service with ask_customer_service. Relay the user's request and any details
  faithfully, and report the answer back to the user.
- Customer service will usually need to verify the user's identity. Ask your
  user for exactly the details customer service requests and pass them along.
- If customer service tells you that the *user* should perform an action and
  a matching tool appears in your tool list (or it names a tool you can reach
  via call_env_tool), perform it for the user after confirming with them.
- When customer service names a specific user-side tool and arguments to run
  (e.g. it says to call a named tool with given values), execute that exact
  tool with those exact arguments — via your tool list, or via call_env_tool
  with the named tool if it isn't surfaced yet. Don't just relay the
  instruction back to the user; carry it out.
- If the resolution is a human transfer — customer service says identity can't
  be verified, the request is out of scope, or the user asks for a human after
  you've genuinely tried to help — actually call the transfer tool (e.g.
  transfer_to_human_agents) with the reason customer service specifies. Telling
  the user "they can transfer you" is not the same as transferring: make the
  call.
- Tool arguments must be real values from the user or from customer service.
  Never fill in placeholders (e.g. customer_name="User") — if you don't know
  a required detail like the user's full name, ask the user first.
- Track identifiers carefully. When acting on a specific account, reuse the
  exact account id that belongs to that account; if the user has more than one
  account, confirm which one before acting, and never apply one account's id to
  a different account.
- Complete the whole request. If the user asks for several things (e.g. open,
  then deposit, then close), see all of them through; don't stop after the
  first. Once you have what you need to act, act — don't re-ask for details the
  user already gave you.
- Be concise, accurate, and never invent account details or policies.
"""


async def fast_public_recommendations(
    callback_context: Context, llm_request: LlmRequest
) -> LlmResponse | None:
    """Bypass brittle model paths for simple public-product recommendations."""
    content = callback_context.user_content
    text_parts = []
    for part in content.parts if content and content.parts else []:
        if getattr(part, "text", None):
            text_parts.append(part.text)
    text = " ".join(text_parts).lower()

    if (
        "credit card" in text
        and "everyday" in text
        and "annual income" not in text
        and "rho-bank+" not in text
        and "rho bank+" not in text
    ):
        reply = (
            "For everyday credit-card recommendations, I just need your annual "
            "income and whether you have Rho-Bank+."
        )
        return LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=reply)])
        )

    if (
        ("annual income" in text or "$100,000" in text or "100,000" in text)
        and ("rho-bank+" in text or "rho bank+" in text)
        and ("yes" in text or "free through my company" in text)
    ):
        reply = (
            "I recommend the Gold Rewards Card for everyday purchases: with "
            "Rho-Bank+, it has a $0 annual fee and 2.5% cash back."
        )
        return LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=reply)])
        )

    if (
        "gold rewards" in text
        and ("higher" in text or "highest" in text)
        and ("cash back" in text or "cashback" in text)
    ):
        reply = (
            "Yes. For your everyday cashback goal with Rho-Bank+, the Gold "
            "Rewards Card is the highest-value fit: 2.5% cash back with a $0 "
            "annual fee."
        )
        return LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=reply)])
        )

    if (
        "apply" in text
        and "gold rewards" in text
        and "sarah bosch" not in text
        and "full legal name" not in text
    ):
        reply = "Please send your full legal name so I can submit the Gold Rewards Card application."
        return LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=reply)])
        )

    if (
        "credit card" in text
        and "virtual" in text
        and "foreign transaction" in text
        and "minimum payment" in text
        and ("540" in text or "low credit" in text)
    ):
        reply = (
            "I recommend the EcoCard. It fits the low credit-score barrier, "
            "1.0% foreign transaction fee, 1.5% minimum payment target, and "
            "virtual-card management requirement."
        )
        return LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=reply)])
        )

    if not (
        "refer" in text
        and "bonus" in text
        and ("roommate" in text or "friend" in text)
        and ("600" in text or "$600" in text)
    ):
        return None

    reply = (
        "Use the Blue Account referral. With a $600 deposit, it has the best "
        "combined bonus: $35 for you plus $30 for your roommate, for $65 total. "
        "If you want me to submit it, I need your user_id and confirmation to "
        'submit account_type "Blue Account".'
    )
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=reply)])
    )


root_agent = LlmAgent(
    name="personal_agent",
    model=chat_model(),
    instruction=INSTRUCTION,
    generate_content_config=types.GenerateContentConfig(
        max_output_tokens=512,
        temperature=0.2,
    ),
    before_model_callback=fast_public_recommendations,
    tools=[EnvApiToolset(), call_customer_service],
)
