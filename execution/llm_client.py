"""Shared LLM client: reusable AsyncOpenAI client, retry logic, JSON parsing.

All extraction scripts delegate their LLM calls through this module.
"""

import asyncio
import json
import re
import time
from contextvars import ContextVar

import structlog
from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError

from config import settings

log = structlog.get_logger()

# Module-level singleton — created lazily on first call.
_client: AsyncOpenAI | None = None

# Per-pipeline-invocation token aggregator. Set by run_pipeline at the start of
# each record; read at the end to persist totals to the run ledger. Remains None
# outside a pipeline context (e.g. standalone extraction scripts).
run_token_totals: ContextVar[dict | None] = ContextVar("run_token_totals", default=None)


def get_client() -> AsyncOpenAI:
    """Return a reusable AsyncOpenAI client."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
            timeout=settings.LLM_REQUEST_TIMEOUT,
        )
    return _client


# ---------------------------------------------------------------------------
# JSON parsing (shared across all extractors)
# ---------------------------------------------------------------------------

def parse_json_response(text: str):
    """Parse JSON from LLM response, extracting from markdown fences if needed."""
    text = text.strip()
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Extract JSON from ```json ... ``` fences anywhere in the response
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Last resort: find the last { or [ that starts a valid JSON block
    for start_char in ('{', '['):
        idx = text.rfind(start_char)
        while idx >= 0:
            try:
                return json.loads(text[idx:])
            except json.JSONDecodeError:
                idx = text.rfind(start_char, 0, idx)
    log.warning("json_parse_failed",
                first_300=text[:300], last_300=text[-300:])
    raise json.JSONDecodeError("No valid JSON found in LLM response", text, 0)


# ---------------------------------------------------------------------------
# LLM call with retry, timeout, error handling, and token tracking
# ---------------------------------------------------------------------------

async def call_llm(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str,
    temperature: float,
    task: str = "extraction",
    validate_fn=None,
) -> str:
    """Call the LLM with retry, timeout, and structured logging.

    Args:
        system_prompt: System-level instructions.
        user_prompt:   User message (typically the source document).
        model:         OpenRouter model identifier.
        temperature:   Sampling temperature.
        task:          Label for logging (e.g. "committees", "directors").
        validate_fn:   Optional callable(raw: str) -> None. Called after a
                       successful non-empty response. If it raises any exception
                       the response is treated as invalid and retried (up to
                       max_retries total attempts). Use this to retry on schema
                       validation failures without duplicating retry logic in
                       each extractor.

    Returns:
        The raw text content from the LLM response.

    Raises:
        RuntimeError: After all retries are exhausted.
    """
    client = get_client()
    max_retries = settings.LLM_MAX_RETRIES
    backoff_base = settings.LLM_BACKOFF_BASE

    for attempt in range(1, max_retries + 1):
        t0 = time.monotonic()
        try:
            response = await client.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=settings.LLM_MAX_TOKENS,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except (APIConnectionError, APIError, RateLimitError) as exc:
            elapsed = time.monotonic() - t0
            if attempt < max_retries:
                wait = backoff_base ** attempt
                log.warning("llm_api_error",
                            task=task, attempt=attempt, error=str(exc),
                            elapsed_s=round(elapsed, 2), retry_in_s=wait)
                await asyncio.sleep(wait)
                continue
            log.error("llm_api_error_exhausted",
                      task=task, attempts=max_retries, error=str(exc))
            raise RuntimeError(
                f"{task}: LLM API error after {max_retries} attempts: {exc}"
            ) from exc

        elapsed = time.monotonic() - t0
        raw = response.choices[0].message.content
        finish_reason = response.choices[0].finish_reason

        # Log token usage if available
        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        if raw:
            log.info("llm_response",
                     task=task, chars=len(raw), finish_reason=finish_reason,
                     elapsed_s=round(elapsed, 2), attempt=attempt, **usage)
            totals = run_token_totals.get()
            if totals is not None and usage:
                totals["prompt_tokens"] += usage["prompt_tokens"]
                totals["completion_tokens"] += usage["completion_tokens"]
                totals["total_tokens"] += usage["total_tokens"]
                totals["models"].add(model)
            if finish_reason != "stop":
                log.error("llm_truncated",
                          task=task, finish_reason=finish_reason,
                          last_200=raw[-200:])
                raise RuntimeError(
                    f"{task}: LLM output truncated (finish_reason={finish_reason}). "
                    "Refusing to persist possibly incomplete data."
                )
            # Run caller-supplied validation; retry if it rejects the response
            if validate_fn is not None:
                try:
                    validate_fn(raw)
                except Exception as exc:
                    if attempt < max_retries:
                        wait = backoff_base ** attempt
                        log.warning("llm_validation_failed",
                                    task=task, attempt=attempt, error=str(exc),
                                    retry_in_s=wait)
                        await asyncio.sleep(wait)
                        continue
                    log.error("llm_validation_failed_exhausted",
                              task=task, attempts=max_retries, error=str(exc))
                    raise RuntimeError(
                        f"{task}: LLM response failed validation after {max_retries} attempts: {exc}"
                    ) from exc
            return raw

        # Empty response — retry
        if attempt < max_retries:
            wait = backoff_base ** attempt
            log.warning("llm_empty_response",
                        task=task, attempt=attempt, finish_reason=finish_reason,
                        retry_in_s=wait)
            await asyncio.sleep(wait)
        else:
            log.error("llm_empty_response_exhausted",
                      task=task, attempts=max_retries, finish_reason=finish_reason)
            raise RuntimeError(
                f"{task}: LLM returned empty response after {max_retries} attempts. "
                f"finish_reason={finish_reason}"
            )

    # Should be unreachable, but satisfies type checker
    raise RuntimeError(f"{task}: LLM call loop exited unexpectedly")
