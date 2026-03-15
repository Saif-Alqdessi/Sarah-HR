"""
Multi-Provider LLM Manager with Automatic Fallback
Supports: OpenAI (GPT-4o-mini), Groq (Llama 3.3 70B)
"""

import os
import logging
from typing import List, Dict, Optional
from datetime import datetime

from tenacity import retry, stop_after_attempt, wait_exponential

import openai
from groq import Groq

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker for LLM providers"""

    def __init__(self, max_failures: int = 3, timeout_seconds: int = 300):
        self.max_failures = max_failures
        self.timeout_seconds = timeout_seconds
        self.failures: Dict[str, int] = {}
        self.opened_at: Dict[str, Optional[datetime]] = {}

    def record_failure(self, provider: str):
        """Record a failure for a provider"""
        self.failures[provider] = self.failures.get(provider, 0) + 1

        if self.failures[provider] >= self.max_failures:
            self.opened_at[provider] = datetime.now()
            logger.critical(f"Circuit breaker OPENED for {provider}")

    def record_success(self, provider: str):
        """Record a success - reset failures"""
        self.failures[provider] = 0
        self.opened_at[provider] = None

    def is_open(self, provider: str) -> bool:
        """Check if circuit breaker is open for a provider"""
        if provider not in self.opened_at or self.opened_at[provider] is None:
            return False

        time_since_opened = datetime.now() - self.opened_at[provider]
        if time_since_opened.total_seconds() > self.timeout_seconds:
            logger.info(f"Circuit breaker RESET for {provider} (timeout expired)")
            self.failures[provider] = 0
            self.opened_at[provider] = None
            return False

        return True


class MultiProviderLLM:
    """
    Intelligent LLM router with automatic fallback.
    Primary: Groq (FREE, fast - Llama 3.3 70B)
    Fallback: OpenAI (paid, when Groq fails)
    """

    def __init__(self):
        # Initialize clients
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        # Provider configuration
        primary = os.getenv("PRIMARY_LLM_PROVIDER", "groq")
        fallback = os.getenv("FALLBACK_LLM_PROVIDER", "openai")

        # Provider priority order
        self.providers = [
            (primary, self._get_provider_func(primary)),
            (fallback, self._get_provider_func(fallback)),
        ]

        # Circuit breaker
        max_failures = int(os.getenv("MAX_LLM_FAILURES", "3"))
        timeout = int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "300"))
        self.circuit_breaker = CircuitBreaker(max_failures, timeout)

        logger.info(f"MultiProviderLLM initialized: Primary={primary}, Fallback={fallback}")

    def _get_provider_func(self, provider_name: str):
        """Get the provider function by name"""
        if provider_name == "openai":
            return self._call_openai
        elif provider_name == "groq":
            return self._call_groq
        else:
            raise ValueError(f"Unknown provider: {provider_name}")

    # Max conversation turns to send — keeps context window within Groq's limit.
    # System prompt (~400 tokens) + 6 turns (~600 tokens) + 80 response = ~1080 tokens.
    MAX_HISTORY_TURNS = 6

    # Hard cap on total chars across all messages before we trim aggressively.
    # Groq llama-3.3-70b context limit is 32k tokens; 1 token ≈ 4 chars → 28k chars safe.
    MAX_TOTAL_CHARS = 20_000

    @staticmethod
    def _trim_messages(messages: List[Dict[str, str]], max_turns: int = 6) -> List[Dict[str, str]]:
        """
        Keep the system prompt + the last `max_turns` user/assistant pairs.
        This prevents Groq 400 errors as conversation history grows.

        Args:
            messages:  Full message list (system + history + latest user)
            max_turns: Max non-system messages to keep (default 6)

        Returns:
            Trimmed message list, always starting with the system message.
        """
        if not messages:
            return messages

        # Separate system message from the rest
        system_msgs = [m for m in messages if m.get("role") == "system"]
        conv_msgs   = [m for m in messages if m.get("role") != "system"]

        # Keep only the last max_turns turns
        if len(conv_msgs) > max_turns:
            trimmed_count = len(conv_msgs) - max_turns
            conv_msgs = conv_msgs[-max_turns:]
            logger.debug("Trimmed %d old message(s) from context window", trimmed_count)

        trimmed = system_msgs + conv_msgs

        # Secondary safety: if total chars still too high, strip oldest conv turns one by one
        total_chars = sum(len(m.get("content", "")) for m in trimmed)
        while total_chars > MultiProviderLLM.MAX_TOTAL_CHARS and len(conv_msgs) > 2:
            conv_msgs = conv_msgs[1:]  # drop oldest non-system turn
            trimmed = system_msgs + conv_msgs
            total_chars = sum(len(m.get("content", "")) for m in trimmed)
            logger.warning("Char cap: aggressively trimmed to %d conv turns", len(conv_msgs))

        return trimmed

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 80,   # Sarah's replies are always < 20 words per the prompt rule
        model: Optional[str] = None,
    ) -> str:
        """
        Generate text using LLM with automatic fallback.

        Returns:
            Generated text string

        Raises:
            Exception: If all providers fail
        """
        # Trim history before sending — prevents Groq 400 "message too long"
        messages = self._trim_messages(messages, self.MAX_HISTORY_TURNS)
        logger.debug("Sending %d message(s) to LLM", len(messages))

        last_error = None

        for provider_name, provider_func in self.providers:
            # Skip if circuit breaker is open
            if self.circuit_breaker.is_open(provider_name):
                logger.warning(f"{provider_name} circuit breaker OPEN, skipping")
                continue

            try:
                logger.info(f"Attempting generation with {provider_name}...")

                response = await provider_func(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=model,
                )

                self.circuit_breaker.record_success(provider_name)
                logger.info(f"{provider_name} generation succeeded")
                return response

            except openai.RateLimitError as e:
                logger.error(f"{provider_name} rate limit (429): {e}")
                self.circuit_breaker.record_failure(provider_name)
                last_error = e
                continue

            except Exception as e:
                logger.error(f"{provider_name} error: {e}")
                self.circuit_breaker.record_failure(provider_name)
                last_error = e
                continue

        # All providers failed
        error_msg = f"All LLM providers failed. Last error: {last_error}"
        logger.critical(error_msg)
        raise Exception(error_msg)

    async def _call_openai(
        self,
        messages: List[Dict],
        temperature: float,
        max_tokens: int,
        model: Optional[str] = None,
    ) -> str:
        """Call OpenAI API"""
        model = model or "gpt-4o-mini"

        response = self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content.strip()

    async def _call_groq(
        self,
        messages: List[Dict],
        temperature: float,
        max_tokens: int,
        model: Optional[str] = None,
    ) -> str:
        """Call Groq API (Llama 3.3 70B)"""
        model = model or "llama-3.3-70b-versatile"

        response = self.groq_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content.strip()

    def get_status(self) -> Dict:
        """Get current status of all providers"""
        status = {}
        for provider_name, _ in self.providers:
            status[provider_name] = {
                "circuit_open": self.circuit_breaker.is_open(provider_name),
                "failure_count": self.circuit_breaker.failures.get(provider_name, 0),
            }
        return status
