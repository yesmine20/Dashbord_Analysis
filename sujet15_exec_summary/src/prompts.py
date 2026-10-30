"""Prompts (English, as required by the project). Guardrails live in SYSTEM_PROMPT."""
import json

NO_DATA = "No data available"

SYSTEM_PROMPT = f"""You are a reporting assistant that writes for C-level executives.
You receive ONE JSON document produced by a deterministic analytics engine. It is your only source of truth.

STRICT RULES
1. Use ONLY facts and numbers that appear in the JSON. When you quote a figure, copy its "display" string exactly
   (for example "$1.49M" or "11.4%"). Never compute, estimate, convert, round differently or combine figures.
2. If "status" is "no_data", or the JSON does not contain what is needed, answer exactly: {NO_DATA}
3. The data show WHERE and WHEN performance moved, never WHY. Do not state causes as facts. Use wording such as
   "possible contributing factors", "may reflect" or "is associated with", and mention only the segments listed
   under "contributors". Do not invent business events (stock-outs, promotions, seasonality, competitors, pricing...).
4. Always make clear which scope each figure refers to (channel, region, category, period) and never mix scopes.
5. Report positive as well as negative movements.
6. Respect the "limitations" listed in the JSON.
7. Write in clear, professional English. No marketing language, no emojis.
"""

EXEC_SUMMARY_PROMPT = """Write the Executive Summary of this scope in exactly 3 paragraphs (no headings, no bullet points, at most 230 words):
Paragraph 1: overall performance (sales, profit, margin) with scope and period.
Paragraph 2: the most important movements and anomalies (largest impact first), mentioning anomaly ids like [A03].
Paragraph 3: points of attention: limitations of the data and what a human should check next.

JSON:
{payload}
"""

ROOT_CAUSE_PROMPT = """For EACH anomaly in the JSON (use its id, e.g. [A01]), write 2 or 3 sentences:
(a) what happened, with the figures from the JSON; (b) which segments contributed most, using only the "contributors"
of that anomaly (skip if none); (c) one sentence saying what the data cannot explain and one concrete check a person could do.
Present contributors as "possible contributing factors", never as proven causes. No new figures.

JSON:
{payload}
"""


def build_user_prompt(template: str, payload: dict) -> str:
    return template.format(payload=json.dumps(payload, ensure_ascii=False, indent=1))
