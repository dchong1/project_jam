"""LLM analyst functions for brainstorming and critiquing investment ideas."""

from openai import APIConnectionError, APIError, OpenAI, RateLimitError

from .config import (
    ANALYST_ARCHETYPES,
    GROK_API_KEY,
    GROK_BASE_URL,
    GROK_MODEL,
    brainstorm_prompt_template,
    critic_prompt_template,
    resolve_archetype,
)


def _get_client() -> OpenAI:
    """Create OpenAI-compatible client for Grok API."""
    return OpenAI(api_key=GROK_API_KEY, base_url=GROK_BASE_URL)


def _build_archetype_instruction(archetype: str | None) -> str:
    """Build archetype instruction for prompts. Returns empty string if no archetype."""
    resolved = resolve_archetype(archetype) if archetype else None
    if not resolved or resolved not in ANALYST_ARCHETYPES:
        return ""
    data = ANALYST_ARCHETYPES[resolved]
    return f"Adopt the thinking style of a {data['display_name']} analyst: {data['description']} "


def brainstorm_ideas(theme: str, archetype: str | None = None) -> str:
    """Generate 2-4 investment ideas for the given theme using the brainstormer LLM."""
    archetype_instruction = _build_archetype_instruction(archetype)
    prompt = brainstorm_prompt_template.format(
        theme=theme,
        archetype_instruction=archetype_instruction,
    )
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=GROK_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""
    except APIError as e:
        raise RuntimeError(f"Grok API error: {e}") from e
    except APIConnectionError as e:
        raise RuntimeError(f"Failed to connect to Grok API: {e}") from e
    except RateLimitError as e:
        raise RuntimeError(f"Grok API rate limit exceeded: {e}") from e


def critique_ideas(brainstorm_text: str, archetype: str | None = None) -> str:
    """Critique brainstormed ideas using the critic LLM."""
    archetype_instruction = _build_archetype_instruction(archetype)
    prompt = critic_prompt_template.format(
        brainstorm_text=brainstorm_text,
        archetype_instruction=archetype_instruction,
    )
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=GROK_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""
    except APIError as e:
        raise RuntimeError(f"Grok API error: {e}") from e
    except APIConnectionError as e:
        raise RuntimeError(f"Failed to connect to Grok API: {e}") from e
    except RateLimitError as e:
        raise RuntimeError(f"Grok API rate limit exceeded: {e}") from e
