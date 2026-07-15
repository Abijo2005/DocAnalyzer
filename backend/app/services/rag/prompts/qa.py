# Context Q&A Prompt Template

QA_PROMPT_TEMPLATE = """Below is the retrieved context from the uploaded documents. Use it to answer the question at the end.

<context>
{context_str}
</context>

Question: {question}

Answer:"""


def format_context_block(chunks: list) -> str:
    """Formats a list of retrieved chunks/citations into a readable context block for the LLM."""
    formatted_blocks = []
    for idx, citation in enumerate(chunks):
        formatted_blocks.append(
            f"--- Context Block {idx + 1} ---\n"
            f"Source Document: {citation.document_name}\n"
            f"Page Number: {citation.page if citation.page else 'N/A'}\n"
            f"Content: {citation.text}\n"
        )
    return "\n".join(formatted_blocks)
