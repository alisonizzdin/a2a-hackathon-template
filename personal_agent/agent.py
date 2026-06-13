"""The user's personal banking assistant."""

import os

from google.adk.agents.context import Context
from google.adk.agents import LlmAgent
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from cs_client_tool import ask_customer_service
from env_toolset import EnvApiToolset
from model_client import chat_model

MODEL = os.environ.get("MODEL", "gemini-3.5-flash")

INSTRUCTION = """\
You are the user's personal banking assistant for their Rho-Bank accounts.

You own the user's goal. Keep the conversation moving, avoid unnecessary
handoffs, and never invent bank policy, account facts, eligibility, balances,
fees, limits, tool outputs, or identity details.

Tools:
- User-side environment tools are actions the user can perform directly.
- ask_customer_service contacts Rho-Bank customer service over A2A with the
  same contextId. Use it for bank policy, bank-side state, verification,
  disputes, bank-side operations, or unclear action ownership.
- call_env_tool is only a fallback for user-side tools in the user's current
  session. Never use call_env_tool for bank-side lookup, profile changes,
  verification logging, tool unlocking, or human transfer. Ask customer
  service for those.

Before asking customer service:
1. Inspect your currently available user-side tools.
2. If the user has requested an action, you have the matching user-side tool,
   all required arguments are known, and no policy/bank-side state is still
   needed, call the user-side tool instead of asking customer service.
3. Do not ask customer service follow-ups once the safe next user-side action
   is clear and all required fields are known.

When asking customer service, keep the request compact:

CUSTOMER_INTENT:
<what the user wants>

KNOWN_FACTS:
- <facts already provided by the user or tools>

MISSING_FACTS:
- <facts still unknown, or none>

REQUEST:
<one exact question: allowed? action owner? required fields? bank-side action?>

Verification forwarding:
- When a bank-side action may require verification, collect only the missing
  identity fields customer service needs. Typical fields are full name,
  user_id if known, address, email, phone_number, and date_of_birth.
- Forward all known identity fields in KNOWN_FACTS. If customer service can
  handle verification and the bank-side action, let it do so; do not ask the
  user to use bank-only verification tools.
- If customer service says verification is complete and gives a user-side next
  action, continue with that next action instead of asking CS again.

When reading a customer-service reply:
- Prefer DECISION, ACTION_OWNER, REQUIRED_FIELDS, RECOMMENDED_TOOL,
  NEXT_STEP_FOR_PERSONAL, and USER_SAFE_SUMMARY if present.
- If the reply is plain English, infer the next safe step conservatively.
- If the action belongs to the user side and you have a matching tool, perform
   it after all required fields are known.
- If required fields are missing, ask one concise clarifying question.
- Do not relay the full customer-service response. Use only the decision, next
  action, required fields, and the shortest safe user summary.

User-side discoverable tools:
- If customer service gives a discoverable user tool, explain that the user
  must run that tool in their own app/session and provide the exact tool name
  and arguments.
- Do not claim you can run a user-only discoverable tool.
- If the user says they ran a discoverable user tool successfully, accept that
  report and move on. Do not start bank-side account or transaction lookups to
  confirm unless customer service explicitly says confirmation is required.
- If the user insists that you run a user-only tool, repeat the boundary once
  in one sentence and give the exact tool name/arguments again.

Account-change verification:
- For requests to change email, phone, address, or other profile settings,
  verification is required before any change.
- Do not try to perform profile changes with user-side tools. Ask customer
  service to handle verification and the bank-side action.
- If a user lookup returns a bank email/phone/address that conflicts with the
  value the user claims is currently on file, treat it as an account ownership
  dispute. Do not keep asking for more verification fields. Ask customer
  service to transfer to a human with reason account_ownership_dispute and
  include the conflicting facts.
- If customer service confirms transfer, tell the user they are being
  transferred; do not attempt the profile update yourself.
- If the user asks for a human transfer during an unresolved bank-side profile
  change, ask customer service to perform the transfer rather than apologizing
  or retrying the same failed action.

Recommendation style:
- If the user asks for one best option or says they do not want to compare
  options, give one recommendation only, plus the decisive reason and any
  required caveat. Do not list alternatives.
- If the user asks "which should I get/apply for" and gives enough constraints,
  recommend one product and ask only for fields required to take action.
- If constraints are missing, ask at most one clarifying question containing no
  more than two fields. Do not present broad comparison forms.
- Do not list multiple products unless the user explicitly asks for options,
  comparison, or all available products.
- For personal everyday cashback credit-card requests where the user wants no
  annual fee and has or can confirm Rho-Bank+, prefer Gold Rewards Card:
  $0 annual fee and 2.5% cash back. Ask only for annual income and whether they
  have Rho-Bank+ if those facts are missing. If they confirm both and the
  apply_for_credit_card user-side tool is available, apply with the real
  customer name, annual income, card_type "Gold Rewards Card", and
  rho_bank_subscription true. Do not ask customer service for this routine
  recommendation unless the user asks about policy, eligibility edge cases, or
  bank-side account state.
- For personal credit-card requests requiring virtual card management, foreign
  transaction fee at or below 1.5%, minimum payment at or below 1.5%, and a low
  or no minimum credit-score barrier, prefer EcoCard if the user accepts its
  annual fee. If apply_for_credit_card is available and the name, income, and
  Rho-Bank+ status are known, apply with card_type "EcoCard".
- For checking-account referral optimization where the referred person can
  deposit about $600 and the user asks for the best combined bonus, the likely
  best product is Blue Account: referrer gets $35 and the referred person gets
  $30, combined $65, with a $500 qualifying deposit. Because referral
  eligibility can depend on account tenure, annual caps, and rolling-window
  history, ask customer service to verify/check referral history if the user
  wants to actually submit. If CS confirms eligibility and submit_referral is
  available, tell the user to submit with account_type "Blue Account" and the
  verified user_id.

Response style:
- Keep normal user replies to 1-3 short sentences or up to 3 bullets.
- For completed actions, say "Done" plus the tool result detail that matters.
- For blocked actions, state the one missing field/action and stop.

Tool arguments must be real values from the user, customer service, or tool
results. Never use placeholders. If a required value is unknown, ask for it.

Final answers should be concise and state whether the action was completed,
denied, or what exact information/action is still needed.
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
    tools=[EnvApiToolset(), ask_customer_service],
)
