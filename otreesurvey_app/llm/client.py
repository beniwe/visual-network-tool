"""
Unified LLM client — supports OpenAI, Aqueduct, and any OpenAI-compatible API.

Reads provider/model/key settings from study_config.json.
Provides both sync `call_llm()` and async `async_call_llm()` with:
  - instructor-based structured output (Pydantic response models)
  - rate limiting (token bucket, configurable)
  - retries with backoff
"""

import os
import time
import asyncio
import threading
from collections import deque
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, AsyncOpenAI
import instructor
from tenacity import retry, stop_after_attempt, wait_fixed, AsyncRetrying

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


# -- Rate limiter (shared across sync + async) --------------------------------

_MAX_RPM = 50
_REQUEST_TIMES = deque()
_LOCK = threading.Lock()


def _acquire_slot():
    """Reserve a request slot. Returns seconds to wait before firing."""
    with _LOCK:
        now = time.time()
        while _REQUEST_TIMES and _REQUEST_TIMES[0] <= now - 60:
            _REQUEST_TIMES.popleft()

        if len(_REQUEST_TIMES) < _MAX_RPM:
            start = max(now, _REQUEST_TIMES[-1] + 0.5) if _REQUEST_TIMES else now
            _REQUEST_TIMES.append(start)
            return max(0.0, start - now)

        oldest = _REQUEST_TIMES.popleft()
        slot_opens = oldest + 60
        start = max(slot_opens, _REQUEST_TIMES[-1] + 2.0)
        _REQUEST_TIMES.append(start)
        return max(0.0, start - now)


# -- Client construction ------------------------------------------------------

def _get_llm_config():
    from ..config_loader import get_config
    return get_config().get("llm", {})


def _build_client_kwargs(cfg):
    """Build kwargs for OpenAI/AsyncOpenAI from config."""
    kwargs = {}

    api_key_env = cfg.get("api_key_env", "OPENAI_API_KEY")
    api_key = os.getenv(api_key_env)
    if api_key:
        kwargs["api_key"] = api_key

    base_url_env = cfg.get("base_url_env")
    if base_url_env:
        base_url = os.getenv(base_url_env)
        if base_url:
            kwargs["base_url"] = base_url

    return kwargs


def _build_call_kwargs(cfg, response_model, prompt, temp_override=None):
    """Build kwargs for the chat.completions.create call."""
    model = cfg.get("model", "gpt-4.1-2025-04-14")
    temp = temp_override if temp_override is not None else cfg.get("temperature", 0.7)

    kwargs = dict(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_model=response_model,
    )

    # reasoning models don't support temperature
    if model not in ('o3', 'o3-mini', 'o4-mini'):
        kwargs["temperature"] = temp

    # aqueduct-specific: disable thinking for non-thinking models
    provider = cfg.get("provider", "openai")
    if provider == "aqueduct":
        kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
        kwargs["timeout"] = 29

    return kwargs


# -- Sync interface ------------------------------------------------------------

def call_llm(response_model, prompt, temp=None):
    """
    Synchronous LLM call with structured output.
    Returns the parsed response model instance.
    """
    cfg = _get_llm_config()
    max_retries = cfg.get("max_retries", 5)
    delay = cfg.get("retry_delay_seconds", 2)

    client = OpenAI(**_build_client_kwargs(cfg))
    client = instructor.from_openai(client, mode=instructor.Mode.TOOLS)

    call_kwargs = _build_call_kwargs(cfg, response_model, prompt, temp)

    @retry(stop=stop_after_attempt(max_retries), wait=wait_fixed(delay), reraise=True)
    def _do_call():
        wait = _acquire_slot()
        if wait > 0:
            time.sleep(wait)
        return client.chat.completions.create(**call_kwargs)

    return _do_call()


# -- Async interface -----------------------------------------------------------

async def async_call_llm(response_model, prompt, temp=None):
    """
    Async LLM call with structured output.
    Returns the parsed response model instance.
    """
    cfg = _get_llm_config()
    max_retries = cfg.get("max_retries", 5)
    delay = cfg.get("retry_delay_seconds", 2)

    client = AsyncOpenAI(**_build_client_kwargs(cfg))
    client = instructor.from_openai(client, mode=instructor.Mode.TOOLS)

    call_kwargs = _build_call_kwargs(cfg, response_model, prompt, temp)

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(max_retries),
        wait=wait_fixed(delay),
        reraise=True,
    ):
        with attempt:
            wait = _acquire_slot()
            if wait > 0:
                await asyncio.sleep(wait)
            return await client.chat.completions.create(**call_kwargs)


# -- Raw async (no instructor, for backward compat with ConversationFeedback) --

async def async_call_llm_raw(prompt, temp=None):
    """
    Async LLM call returning raw completion text (no structured output).
    Used by ConversationFeedback's live_method which parses JSON manually.
    """
    cfg = _get_llm_config()
    max_retries = cfg.get("max_retries", 5)
    delay = cfg.get("retry_delay_seconds", 2)
    model = cfg.get("model", "gpt-4.1-2025-04-14")
    temperature = temp if temp is not None else cfg.get("temperature", 0.7)

    client = AsyncOpenAI(**_build_client_kwargs(cfg))

    extra = {}
    if cfg.get("provider") == "aqueduct":
        extra["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
        extra["timeout"] = 29

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(max_retries),
        wait=wait_fixed(delay),
        reraise=True,
    ):
        with attempt:
            wait = _acquire_slot()
            if wait > 0:
                await asyncio.sleep(wait)
            completion = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                stream=False,
                **extra,
            )
            return completion.choices[0].message.content.strip()
