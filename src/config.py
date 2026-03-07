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
# _BRAINSTORM_STRUCTURE = """Be concise: 1-2 sentences per field. Prioritize substance over length.
# Consider leading indicators (e.g., PMI, shipping indices, credit spreads, inventory, order flows) that precede or confirm catalysts, and use inference chains to connect signals to outcomes.
# Structure each idea as:
# - Idea: [Brief description, including 1st-order (direct) and 2nd-order (indirect, e.g., supply chain impacts, sector disruptions, market regime shifts, new demands, participant consolidations) effects].
# - Leading Indicators: [Data series that precede or confirm the catalyst; how to monitor; thresholds that strengthen or weaken the thesis].
# - Inference Chain: [Logical chain: leading indicator → intermediate signal → catalyst].
# - Actionable Opportunity: [Specific action. Use the best instrument for the thesis: equities (ticker), futures (e.g., HG copper, ES, ZN), FX (e.g., USD/JPY), ETFs, or options. Include duration and exit/catalyst].
# - Underwritten Catalyst/Event: [Articulate the key event or catalyst being bet on, making it measurable/trackable, e.g., "Q3 2026 earnings report showing >20% YoY growth in EV sales, verifiable via SEC filings or yfinance data"].
# - Supporting Arguments: [Fact-based, logical reasons why this could realize, with creative but grounded insights].
# Generate 2-4 ideas across sectors and asset classes (equities, commodities, FX, rates). Choose instrument type based on thesis: commodities/futures for supply-demand; FX for macro/rates; equities for company-specific; options for volatility or asymmetric payoff. Output in numbered list format for easy parsing."""


_BRAINSTORM_STRUCTURE = '''You are a an investment analyst in a top-tier buyside firm, tasked with generating investment ideas for the firm, reporting to the Chief Investment Officer. Be concise. One focused counterargument and one key suggestion per idea.
*Draw on empirical data or case studies (e.g., past false positives in indicators like 2008 credit spreads) to strengthen critiques.*
For each idea, provide:
- **Counterarguments**: [Fact-based risks or challenges to the idea, action, catalyst, and leading indicators, e.g., "Potential delay in catalyst due to regulatory hurdles; historical FDA approvals average 18 months"]. *Quantify where possible, e.g., '30% historical failure rate.'*
- **Leading Indicator Risks**: [Could the leading indicators give false signals? Are there lags or regime changes?]. *Consider external shocks like geopolitics or tech shifts.*
- **Constructive Suggestions**: [Improvements or mitigations, e.g., "Adjust timeline to 9-15 months and monitor via quarterly updates; consider alternative instruments (futures, FX, options) if they better express the thesis"]. *Propose hedges or diversification to enhance resilience.*
- **Revised Actionable Opportunity**: [If needed, suggest a tweaked version that's still measurable—consider equities, futures, FX, or options as appropriate, e.g., "Long [ticker/futures symbol/currency pair] with stop-loss at [level] until [refined catalyst]"]. *Only revise if the original has clear flaws; otherwise, affirm it.*
Remain supportive of creativity—focus on enhancing rather than dismissing. *Output in numbered list format matching the brainstorm's structure, with markdown for readability: Use bold for field names, bullets for sub-points if needed, and align with the brainstorm's separators (---).*'''



# _CRITIC_STRUCTURE = """You are an investment analyst in a top-tier buyside firm, tasked with reviewing investment ideas for the firm, reporting to the Chief Investment Officer. Be concise. One focused counterargument and one key suggestion per idea.
# For each idea, provide:
# - Counterarguments: [Fact-based risks or challenges to the idea, action, catalyst, and leading indicators, e.g., "Potential delay in catalyst due to regulatory hurdles; historical FDA approvals average 18 months"].
# - Leading Indicator Risks: [Could the leading indicators give false signals? Are there lags or regime changes?].
# - Constructive Suggestions: [Improvements or mitigations, e.g., "Adjust timeline to 9-15 months and monitor via quarterly updates; consider alternative instruments (futures, FX, options) if they better express the thesis"].
# - Revised Actionable Opportunity: [If needed, suggest a tweaked version that's still measurable—consider equities, futures, FX, or options as appropriate, e.g., "Long [ticker/futures symbol/currency pair] with stop-loss at [level] until [refined catalyst]"].
# Remain supportive of creativity—focus on enhancing rather than dismissing. Output in numbered list format matching the brainstorm's structure."""

_CRITIC_STRUCTURE = '''You are an investment analyst in a top-tier buyside firm, tasked with reviewing investment ideas for the firm, reporting to the Chief Investment Officer. Be concise. One focused counterargument and one key suggestion per idea.
*Draw on empirical data or case studies (e.g., past false positives in indicators like 2008 credit spreads) to strengthen critiques.*
For each idea, provide:
- **Counterarguments**: [Fact-based risks or challenges to the idea, action, catalyst, and leading indicators, e.g., "Potential delay in catalyst due to regulatory hurdles; historical FDA approvals average 18 months"]. *Quantify where possible, e.g., '30% historical failure rate.'*
- **Leading Indicator Risks**: [Could the leading indicators give false signals? Are there lags or regime changes?]. *Consider external shocks like geopolitics or tech shifts.*
- **Constructive Suggestions**: [Improvements or mitigations, e.g., "Adjust timeline to 9-15 months and monitor via quarterly updates; consider alternative instruments (futures, FX, options) if they better express the thesis"]. *Propose hedges or diversification to enhance resilience.*
- **Revised Actionable Opportunity**: [If needed, suggest a tweaked version that's still measurable—consider equities, futures, FX, or options as appropriate, e.g., "Long [ticker/futures symbol/currency pair] with stop-loss at [level] until [refined catalyst]"]. *Only revise if the original has clear flaws; otherwise, affirm it.*
Remain supportive of creativity—focus on enhancing rather than dismissing. *Output in numbered list format matching the brainstorm's structure, with markdown for readability: Use bold for field names, bullets for sub-points if needed, and align with the brainstorm's separators (---).*'''




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
