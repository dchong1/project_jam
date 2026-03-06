"""LLM analyst functions for brainstorming and critiquing investment ideas."""

from openai import APIConnectionError, APIError, OpenAI, RateLimitError

from .config import (
    GROK_API_KEY,
    GROK_BASE_URL,
    GROK_MODEL,
    brainstorm_prompt_template,
    critic_prompt_template,
)


def _get_client() -> OpenAI:
    """Create OpenAI-compatible client for Grok API."""
    return OpenAI(api_key=GROK_API_KEY, base_url=GROK_BASE_URL)


def brainstorm_ideas(theme: str) -> str:
    """Generate 3-5 investment ideas for the given theme using the brainstormer LLM."""
    prompt = brainstorm_prompt_template.format(theme=theme)
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


def critique_ideas(brainstorm_text: str) -> str:
    """Critique brainstormed ideas using the critic LLM."""
    prompt = critic_prompt_template.format(brainstorm_text=brainstorm_text)
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
