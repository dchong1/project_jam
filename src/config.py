"""Configuration for the investment idea generation app."""

import os

from dotenv import load_dotenv

load_dotenv()

GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_BASE_URL = "https://api.x.ai/v1"
GROK_MODEL = "grok-4"

if not GROK_API_KEY:
    raise ValueError(
        "GROK_API_KEY is not set. Create a .env file with GROK_API_KEY=your_xai_api_key"
    )

brainstorm_prompt_template = '''Act as an investment analyst brainstorming specific, actionable opportunities for the theme: "{theme}".
Consider leading indicators (e.g., PMI, shipping indices, credit spreads, inventory, order flows) that precede or confirm catalysts, and use inference chains to connect signals to outcomes.
Structure each idea as:
- Idea: [Brief description, including 1st-order (direct) and 2nd-order (indirect, e.g., supply chain impacts, sector disruptions, market regime shifts, new demands, participant consolidations) effects].
- Leading Indicators: [Data series that precede or confirm the catalyst; how to monitor; thresholds that strengthen or weaken the thesis].
- Inference Chain: [Logical chain: leading indicator → intermediate signal → catalyst].
- Actionable Opportunity: [Specific action. Use the best instrument for the thesis: equities (ticker), futures (e.g., HG copper, ES, ZN), FX (e.g., USD/JPY), ETFs, or options. Include duration and exit/catalyst].
- Underwritten Catalyst/Event: [Articulate the key event or catalyst being bet on, making it measurable/trackable, e.g., "Q3 2026 earnings report showing >20% YoY growth in EV sales, verifiable via SEC filings or yfinance data"].
- Supporting Arguments: [Fact-based, logical reasons why this could realize, with creative but grounded insights].
Generate 3-5 ideas across sectors and asset classes (equities, commodities, FX, rates). Choose instrument type based on thesis: commodities/futures for supply-demand; FX for macro/rates; equities for company-specific; options for volatility or asymmetric payoff. Output in numbered list format for easy parsing.'''

critic_prompt_template = '''Act as a constructive investment critic reviewing the following brainstormed ideas: "{brainstorm_text}".
For each idea, provide:
- Counterarguments: [Fact-based risks or challenges to the idea, action, catalyst, and leading indicators, e.g., "Potential delay in catalyst due to regulatory hurdles; historical FDA approvals average 18 months"].
- Leading Indicator Risks: [Could the leading indicators give false signals? Are there lags or regime changes?].
- Constructive Suggestions: [Improvements or mitigations, e.g., "Adjust timeline to 9-15 months and monitor via quarterly updates; consider alternative instruments (futures, FX, options) if they better express the thesis"].
- Revised Actionable Opportunity: [If needed, suggest a tweaked version that's still measurable—consider equities, futures, FX, or options as appropriate, e.g., "Long [ticker/futures symbol/currency pair] with stop-loss at [level] until [refined catalyst]"].
Remain supportive of creativity—focus on enhancing rather than dismissing. Output in numbered list format matching the brainstorm's structure.'''
