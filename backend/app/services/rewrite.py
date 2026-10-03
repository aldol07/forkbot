"""Follow-up questions → standalone search queries.

"why is that?" or "and the second one?" match nothing on their own, so before retrieval the LLM
rewrites the latest message using the conversation (references resolved, names/ids/numbers kept).
Only runs when the conversation has earlier turns. The original message is still what the
answering model sees; the rewrite is only used for searching (and stored for debugging).
"""
from ..config import get_settings
from ..llm.providers import ProviderSpec, complete

PROMPT = (
    "You turn the user's latest message into ONE standalone search query for searching their documents. "
    "Use the conversation only to resolve references such as it, that, they, why, the second one, or "
    "'what about X'. Keep names, numbers, ids and key terms exactly. If the latest message is already "
    "standalone, return it unchanged. If it is small talk or about the conversation itself, return it unchanged. "
    "Reply with the query only: no quotes, no explanation."
)


def rewrite_query(spec: ProviderSpec, chat_model: str, history, message: str) -> str:
    """Raises ProviderError on failure; the caller falls back to a simpler query."""
    model = get_settings().rewrite_model if spec.name == "groq" and get_settings().rewrite_model else chat_model
    convo = "\n".join(f"{m.role}: {m.content[:600]}" for m in history[-6:])
    out = complete(spec, model, [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": f"Conversation:\n{convo}\n\nLatest message: {message}"},
    ]).strip().strip('"').strip()
    return out if 0 < len(out) <= 400 else message
