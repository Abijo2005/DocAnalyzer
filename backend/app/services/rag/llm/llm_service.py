from typing import Dict, List
from openai import OpenAI
from app.config.settings import settings
from app.core.logging_config import llm_logger


class LLMService:
    """Interfaces with OpenAI-compatible APIs or local Ollama instances to generate answers."""

    def __init__(self) -> None:
        self.provider = settings.LLM_PROVIDER
        self.model = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS

        llm_logger.info(
            f"Initializing LLMService: provider={self.provider}, model={self.model}, base_url={settings.LLM_BASE_URL}"
        )

        # Initialize the OpenAI client wrapper
        # For Ollama, the base_url points to http://localhost:11434/v1 and api_key can be anything
        self.client = OpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
        )

    def generate_chat_response(self, messages: List[Dict[str, str]]) -> str:
        """Sends chat messages to the configured LLM and returns the text response."""
        try:
            llm_logger.info(
                f"Requesting chat completion from {self.provider}/{self.model}. Temperature={self.temperature}"
            )
            llm_logger.debug(f"Prompt Messages: {messages}")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            answer = response.choices[0].message.content or ""
            llm_logger.info("Successfully received response from LLM")
            llm_logger.debug(f"Response content: {answer[:200]}...")
            return answer.strip()

        except Exception as e:
            llm_logger.error(f"Error calling LLM provider '{self.provider}': {e}")
            raise RuntimeError(f"LLM generation failed: {e}")

    def generate_simple_completion(self, system_prompt: str, user_prompt: str) -> str:
        """Helper to run simple prompt completions (e.g. for rewriting queries)."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self.generate_chat_response(messages)
