# Query Condensation Prompt (Conversational Context Search)

CONVERSATION_REWRITE_PROMPT = """Given the following conversation history and a follow-up question, rewrite the follow-up question to be a standalone question that can be understood without the context of the conversation history.

Do NOT answer the question. Just output the rewritten standalone question.

Chat History:
{chat_history}

Follow-up Question: {question}

Standalone Question:"""


def format_chat_history(messages: list) -> str:
    """Formats list of message schemas or DB models into a text log for prompt rewriting."""
    formatted = []
    for msg in messages:
        role_label = "User" if msg.role == "user" else "Assistant"
        formatted.append(f"{role_label}: {msg.content}")
    return "\n".join(formatted)
