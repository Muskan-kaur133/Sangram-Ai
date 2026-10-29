"""AI Provider Gateway Interface (Developer 3 Boundary).

Defines the protocol Developer 3 must implement to bridge model profiles
to live LLM providers (OpenAI, Google, Anthropic, Meta/Groq, Mistral, xAI).
"""

from typing import AsyncGenerator, Dict, List, Protocol, runtime_checkable
from app.schemas.model import ModelProfile


@runtime_checkable
class IModelGatewayService(Protocol):
    """Orchestrates streaming LLM inference across multi-model providers."""

    async def stream_argument(
        self,
        model_id: str,
        system_prompt: str,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """Streams text chunks directly from the underlying AI model provider.
        
        Yields:
            Token or text chunk strings.
        
        Raises:
            AppException(TIMEOUT): On provider timeout.
            AppException(RATE_LIMIT): On upstream rate limiting.
            AppException(API_FAILURE): On provider error.
        """
        ...

    async def check_provider_health(self, provider: str) -> bool:
        """Pings provider API to check if upstream credentials and quota are valid."""
        ...

    async def estimate_token_cost(
        self, model_id: str, input_tokens: int, estimated_output_tokens: int
    ) -> int:
        """Estimates total provider cost in integer minor units (cents)."""
        ...

    async def get_active_models(self) -> List[ModelProfile]:
        """Returns the list of active combatant models and their availability status."""
        ...
