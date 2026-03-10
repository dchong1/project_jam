"""LLM analyst functions for brainstorming and critiquing investment ideas."""

import re
from collections.abc import Generator

from openai import APIConnectionError, APIError, OpenAI, RateLimitError

from .config import (
    ANALYST_ARCHETYPES,
    GROK_API_KEY,
    GROK_BASE_URL,
    GROK_MODEL_FAST,
    brainstorm_prompt_template,
    combined_prompt_template,
    critic_prompt_template,
    resolve_archetype,
)

# Extended timeout for reasoning models (xAI recommendation)
REASONING_TIMEOUT = 3600.0


def _get_client() -> OpenAI:
    """Create OpenAI-compatible client for Grok API."""
    return OpenAI(
        api_key=GROK_API_KEY,
        base_url=GROK_BASE_URL,
        timeout=REASONING_TIMEOUT,
    )


def _build_archetype_instruction(archetype: str | None) -> str:
    """Build archetype instruction for prompts. Returns empty string if no archetype."""
    resolved = resolve_archetype(archetype) if archetype else None
    if not resolved or resolved not in ANALYST_ARCHETYPES:
        return ""
    data = ANALYST_ARCHETYPES[resolved]
    return f"Adopt the thinking style of a {data['display_name']} analyst: {data['description']} "


def brainstorm_ideas(
    theme: str,
    archetype: str | None = None,
    stream: bool = False,
) -> str | Generator[str, None, None]:
    """Generate 2-4 investment ideas for the given theme using the brainstormer LLM."""
    archetype_instruction = _build_archetype_instruction(archetype)
    prompt = brainstorm_prompt_template.format(
        theme=theme,
        archetype_instruction=archetype_instruction,
    )
    try:
        client = _get_client()
        if stream:
            response = client.chat.completions.create(
                model=GROK_MODEL_FAST,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )
            return _stream_generator(response)
        response = client.chat.completions.create(
            model=GROK_MODEL_FAST,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""
    except APIError as e:
        raise RuntimeError(f"Grok API error: {e}") from e
    except APIConnectionError as e:
        raise RuntimeError(f"Failed to connect to Grok API: {e}") from e
    except RateLimitError as e:
        raise RuntimeError(f"Grok API rate limit exceeded: {e}") from e


def critique_ideas(
    brainstorm_text: str,
    archetype: str | None = None,
    stream: bool = False,
) -> str | Generator[str, None, None]:
    """Critique brainstormed ideas using the critic LLM."""
    archetype_instruction = _build_archetype_instruction(archetype)
    prompt = critic_prompt_template.format(
        brainstorm_text=brainstorm_text,
        archetype_instruction=archetype_instruction,
    )
    try:
        client = _get_client()
        if stream:
            response = client.chat.completions.create(
                model=GROK_MODEL_FAST,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )
            return _stream_generator(response)
        response = client.chat.completions.create(
            model=GROK_MODEL_FAST,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""
    except APIError as e:
        raise RuntimeError(f"Grok API error: {e}") from e
    except APIConnectionError as e:
        raise RuntimeError(f"Failed to connect to Grok API: {e}") from e
    except RateLimitError as e:
        raise RuntimeError(f"Grok API rate limit exceeded: {e}") from e


def _stream_generator(stream) -> Generator[str, None, None]:
    """Yield content chunks from a streaming API response."""
    for chunk in stream:
        content = chunk.choices[0].delta.content if chunk.choices else None
        if content:
            yield content


def generate_keywords_for_ideas(idea_summaries: list[str]) -> list[list[str]]:
    """Generate 2-3 broad keywords per idea for sorting/referencing. Returns list of keyword lists."""
    if not idea_summaries:
        return []
    numbered = "\n\n".join(
        f"Idea {i + 1}:\n{s[:500]}" for i, s in enumerate(idea_summaries)
    )
    prompt = (
        "Given these investment ideas, output exactly 2-3 broad keywords per idea "
        "(comma-separated, one line per idea). Keywords should be useful for future "
        "sorting and cross-referencing (e.g., sector, theme, asset class). "
        "Output ONLY the keyword lines, no numbering or labels.\n\n"
        f"{numbered}"
    )
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=GROK_MODEL_FAST,
            messages=[{"role": "user", "content": prompt}],
        )
        text = (response.choices[0].message.content or "").strip()
        result: list[list[str]] = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Remove leading "Idea N:" or "N." if present
            line = re.sub(r"^(?:Idea\s+\d+[\.\:\s]+|\d+[\.\)]\s*)", "", line, flags=re.IGNORECASE)
            keywords = [k.strip() for k in line.split(",") if k.strip()][:3]
            result.append(keywords)
        # Pad to match input length
        while len(result) < len(idea_summaries):
            result.append([])
        return result[: len(idea_summaries)]
    except (APIError, APIConnectionError, RateLimitError):
        return [[] for _ in idea_summaries]


def generate_ideas_combined(
    theme: str,
    archetype: str | None = None,
    stream: bool = False,
) -> tuple[str, str] | Generator[str, None, None]:
    """Generate brainstorm and critique in a single API call. Returns (brainstorm, critic) or a streaming generator."""
    archetype_instruction = _build_archetype_instruction(archetype)
    prompt = combined_prompt_template.format(
        theme=theme,
        archetype_instruction=archetype_instruction,
    )
    try:
        client = _get_client()
        if stream:
            response = client.chat.completions.create(
                model=GROK_MODEL_FAST,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )
            return _stream_generator(response)
        response = client.chat.completions.create(
            model=GROK_MODEL_FAST,
            messages=[{"role": "user", "content": prompt}],
        )
        full_text = response.choices[0].message.content or ""
        parts = full_text.split("===CRITIC===", 1)
        brainstorm = parts[0].strip() if parts else ""
        critic = parts[1].strip() if len(parts) > 1 else ""
        return (brainstorm, critic)
    except APIError as e:
        raise RuntimeError(f"Grok API error: {e}") from e
    except APIConnectionError as e:
        raise RuntimeError(f"Failed to connect to Grok API: {e}") from e
    except RateLimitError as e:
        raise RuntimeError(f"Grok API rate limit exceeded: {e}") from e
