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
Structure each idea as:
- Idea: [Brief description, including 1st-order (direct) and 2nd-order (indirect, e.g., supply chain impacts, sector disruptions, market regime shifts, new demands, participant consolidations) effects etc.].
- Actionable Opportunity: [Specific investment action, e.g., "Long [ticker/symbol] equity for [duration, e.g., 6-12 months], until [event/catalyst] happens"].
- Underwritten Catalyst/Event: [Articulate the key event or catalyst being bet on, making it measurable/trackable, e.g., "Q3 2026 earnings report showing >20% YoY growth in EV sales, verifiable via SEC filings or yfinance data"].
- Supporting Arguments: [Fact-based, logical reasons why this could realize, with creative but grounded insights].
Generate 3-5 ideas, covering a mix of sectors/industries. Keep fact-based but allow creativity in 2nd-order effects. Output in numbered list format for easy parsing.'''

critic_prompt_template = '''Act as a constructive investment critic reviewing the following brainstormed ideas: "{brainstorm_text}".
For each idea, provide:
- Counterarguments: [Fact-based risks or challenges to the idea, action, and catalyst, e.g., "Potential delay in catalyst due to regulatory hurdles; historical FDA approvals average 18 months"].
- Constructive Suggestions: [Improvements or mitigations, e.g., "Adjust timeline to 9-15 months and monitor via quarterly updates; consider shorting competitors if catalyst fails"].
- Revised Actionable Opportunity: [If needed, suggest a tweaked version that's still measurable, e.g., "Long [ticker] with stop-loss at [level] until [refined catalyst]"].
Remain supportive of creativity—focus on enhancing rather than dismissing. Output in numbered list format matching the brainstorm's structure.'''
