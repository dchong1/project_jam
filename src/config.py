"""Configuration for the investment idea generation app."""

import os

from dotenv import load_dotenv

load_dotenv()

GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_BASE_URL = "https://api.x.ai/v1"
GROK_MODEL = "grok-4"
GROK_MODEL_FAST = "grok-4-1-fast-reasoning"

if not GROK_API_KEY:
    raise ValueError(
        "GROK_API_KEY is not set. Create a .env file with GROK_API_KEY=your_xai_api_key"
    )

ANALYST_ARCHETYPES = {
    "logical": {
        "display_name": "Logical",
        "aliases": ["spock", "logical"],
        "description": "Evidence-first, deductive, avoids speculation. Focus on measurable catalysts and clear inference chains.",
    },
    "visionary": {
        "display_name": "Visionary",
        "aliases": ["bluesky", "star-gazer", "dream-weaver", "visionary"],
        "description": "Long-horizon, creative, contrarian. Willing to explore blue-sky scenarios and non-obvious second-order effects.",
    },
    "conservative": {
        "display_name": "Old-Guard",
        "aliases": ["safe-player", "old-guard", "conservative"],
        "description": "Risk-averse, proven catalysts, lower conviction bar. Prefer established patterns and defensive positioning.",
    },
    "sherlock": {
        "display_name": "Sherlock",
        "aliases": ["top-down", "dot-connector", "sherlock"],
        "description": "Pattern-finding, connects disparate signals, narrative-driven. Top-down reasoning from macro to specific.",
    },
    "root_seeker": {
        "display_name": "Root-Seeker",
        "aliases": ["first-principle", "first-principle-thinker", "root-seeker"],
        "description": "Bottom-up, fundamentals, physics of the market. First-principles reasoning from base truths.",
    },
}


def resolve_archetype(user_input: str | None) -> str | None:
    """Map user input (or alias) to canonical archetype key. Returns None if invalid/empty."""
    if not user_input or not user_input.strip():
        return None
    normalized = user_input.strip().lower().replace(" ", "-").replace("_", "-")
    for key, data in ANALYST_ARCHETYPES.items():
        key_normalized = key.replace("_", "-")
        if normalized == key_normalized:
            return key
        for alias in data["aliases"]:
            if normalized == alias.replace(" ", "-").replace("_", "-"):
                return key
    return None


# Shared prompt building blocks (compose brainstorm/critic/combined templates)

_BRAINSTORM_STRUCTURE = '''Think like a hedge-fund analyst writing a 1-page memo. Zero filler. Every idea: real ticker, timeline (6–12 months), measurable catalyst. Include 1st-order + 2nd-order effects (supply chain, consolidation, regime shift). Max 4–6 ideas, each < 200 words.

Format each idea as:
**Idea N — [Archetype]**
- Idea: [Brief description with 1st + 2nd order effects]
- Actionable Opportunity: Long [ticker] equity for [X–Y months] until [exact catalyst event]
- Underwritten Catalyst: [Trackable event: earnings date, FDA/SEC filing, regulatory decision, verifiable metric in 10-Q]
- Supporting Arguments: [Fact-based reasons; no generic language]

Example:
**Idea 1 — Spock**
- Idea: AI diagnostics disrupting radiology + 2nd-order hospital cost compression.
- Actionable Opportunity: Long GEHC for 9–12 months until Q4 2026 earnings.
- Underwritten Catalyst: FDA clearance of GE's AI imaging suite + >18% YoY revenue in AI segment (verifiable in 10-Q).
- Supporting Arguments: ...'''



_CRITIC_STRUCTURE = '''Enhance, don't dismiss. One focused counterargument and one key tweak per idea. Quantify where possible (e.g., "30% historical failure rate"). Draw on empirical data or case studies to strengthen critiques.

For each idea:
- Counterarguments: [Fact-based risks to idea, action, catalyst]
- Constructive Tweaks: [Improvements or mitigations; propose hedges if useful]
- Revised Action: [Only if original has clear flaws; otherwise affirm. Format: Long [ticker] for [X–Y months] until [refined catalyst]]'''




brainstorm_prompt_template = (
    'You are an investment analyst in a top-tier buyside firm, tasked with generating investment ideas for the firm, reporting to the Chief Investment Officer. Brainstorm specific, actionable opportunities for the theme: "{theme}".\n'
    "{archetype_instruction}"
    + _BRAINSTORM_STRUCTURE
)

critic_prompt_template = (
    'Act as a constructive investment critic reviewing the following brainstormed ideas: "{brainstorm_text}".\n'
    "{archetype_instruction}"
    + _CRITIC_STRUCTURE
)

combined_prompt_template = (
    'Act as an investment analyst. Perform BOTH tasks below in a single response.\n\n'
    'PART 1 - BRAINSTORM:\n'
    'Brainstorm specific, actionable opportunities for the theme: "{theme}".\n'
    "{archetype_instruction}"
    + _BRAINSTORM_STRUCTURE
    + """

Then output exactly this separator on its own line:
===CRITIC===

PART 2 - CRITIQUE:
Act as a constructive critic reviewing the brainstormed ideas you just produced.
"""
    + "{archetype_instruction}"
    + _CRITIC_STRUCTURE
)
