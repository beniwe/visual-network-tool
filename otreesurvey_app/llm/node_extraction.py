"""
Node extraction from interview transcripts.

Two modes (set in study_config.json → node_extraction.mode):

  closed — match transcript against predefined stance items, score each on a
           Likert scale. Used when researchers define items up front.

  open   — extract arbitrary beliefs/stances from the transcript without a
           predefined list. Used for exploratory studies.

Both modes return a normalized list of dicts:
  {id, label, short_label, evidence, likert?, stance?, type?, category?, effect?}
"""

from pydantic import BaseModel
from typing import List

from .client import call_llm, async_call_llm, async_call_llm_raw
from ..config_loader import get_config

import json


# =============================================================================
# Pydantic models
# =============================================================================

class StanceScore(BaseModel):
    stance_id: str
    likert: int
    evidence: str

class StanceDetectionResult(BaseModel):
    detected: List[StanceScore]

class OpenNode(BaseModel):
    stance: str
    type: str       # PERSONAL | SOCIAL
    category: str   # BEHAVIOR | MOTIVATION
    effect: str     # INCREASE | DECREASE

class OpenNodeList(BaseModel):
    results: List[OpenNode]


# =============================================================================
# Closed-mode extraction
# =============================================================================

def _build_stance_block(items) -> str:
    lines = []
    for item in items:
        statement = item["template"].replace("[SCALE]", "agree")
        codebook = item.get("codebook", "")
        lines.append(f'[{item["id"]}] "{statement}"')
        if codebook:
            lines.append(f'  Guidance: {codebook}')
        lines.append("")
    return "\n".join(lines)


_CLOSED_PROMPT = """\
You are a social scientist analysing interview transcripts about {topic}.

You are given an interview transcript and a fixed list of predefined stances, \
each with coding guidance that describes what counts as evidence and how to \
calibrate the rating scale.

Your task:
1. Identify which stances are clearly evidenced in the transcript.
2. For each evidenced stance, assign a Likert score from 1 to 6 based on how \
strongly the participant agrees or disagrees with that statement.
3. Omit any stance for which there is no evidence in the transcript.

Agreement scale (6-point, no midpoint):
  1 = strongly disagree
  2 = disagree
  3 = somewhat disagree
  4 = somewhat agree
  5 = agree
  6 = strongly agree

Important:
- Score what the participant expresses, not whether they mentioned the topic. \
If they say "I rarely eat meat", score "I eat meat on most days" as 1-2 rather \
than omitting it.
- A low score (1-3) should only be assigned when the participant actively \
expresses disagreement or the opposite position — not simply because the topic \
was not mentioned.
- Follow the per-stance guidance carefully, especially for stances that may overlap.

=*=*=

Predefined stances with coding guidance:

{stance_block}

=*=*=

INTERVIEW TRANSCRIPT:
{transcript}
END TRANSCRIPT

Return ONLY the JSON object. For each detected stance provide:
  stance_id  — must exactly match one of the ids above
  likert     — integer 1-6
  evidence   — one sentence quoting or paraphrasing the relevant part of the transcript
"""


def _make_closed_prompt(questions_answers: dict) -> str:
    cfg = get_config()
    topic = cfg["interview"].get("topic", "the topic")
    items = cfg["node_extraction"]["items"]
    transcript = "\n".join(f"Q: {q}\nA: {a}" for q, a in questions_answers.items())
    return _CLOSED_PROMPT.format(
        topic=topic,
        stance_block=_build_stance_block(items),
        transcript=transcript,
    )


def detect_closed_stances(questions_answers: dict) -> List[dict]:
    """Sync closed-mode extraction. Returns list of enriched stance dicts."""
    prompt = _make_closed_prompt(questions_answers)
    result = call_llm(response_model=StanceDetectionResult, prompt=prompt, temp=0.1)
    return _enrich_closed(result.detected)


async def async_detect_closed_stances_raw(questions_answers: dict) -> tuple:
    """Async closed-mode extraction returning (enriched_list, prompt_used).
    Uses raw LLM call for backward compat with ConversationFeedback's manual parsing."""
    prompt = _make_closed_prompt(questions_answers)
    raw = await async_call_llm_raw(prompt, temp=0.1)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(cleaned)

    if isinstance(parsed, dict) and "detected" in parsed:
        raw_list = parsed["detected"]
    elif isinstance(parsed, dict) and "results" in parsed:
        raw_list = parsed["results"]
    elif isinstance(parsed, list):
        raw_list = parsed
    else:
        raise ValueError("Response not in expected JSON list format.")

    return _enrich_closed_raw(raw_list), prompt


def _enrich_closed(detected: List[StanceScore]) -> List[dict]:
    items = get_config()["node_extraction"]["items"]
    lookup = {item["id"]: item for item in items}
    return [
        {
            "stance_id": s.stance_id,
            "statement": lookup.get(s.stance_id, {}).get("template", s.stance_id).replace("[SCALE]", "agree"),
            "label":     lookup.get(s.stance_id, {}).get("label", s.stance_id),
            "short_label": lookup.get(s.stance_id, {}).get("short_label", ""),
            "direction": lookup.get(s.stance_id, {}).get("direction", ""),
            "likert":    s.likert,
            "evidence":  s.evidence,
        }
        for s in detected
    ]


def _enrich_closed_raw(detected: list) -> list:
    """Same enrichment but from raw dicts (parsed JSON)."""
    items = get_config()["node_extraction"]["items"]
    lookup = {item["id"]: item for item in items}
    return [
        {
            "stance_id": d.get("stance_id", ""),
            "statement": lookup.get(d.get("stance_id", ""), {}).get("template", d.get("stance_id", "")).replace("[SCALE]", "agree"),
            "label":     lookup.get(d.get("stance_id", ""), {}).get("label", d.get("stance_id", "")),
            "short_label": lookup.get(d.get("stance_id", ""), {}).get("short_label", ""),
            "direction": lookup.get(d.get("stance_id", ""), {}).get("direction", ""),
            "likert":    d.get("likert"),
            "evidence":  d.get("evidence", ""),
        }
        for d in detected
    ]


# =============================================================================
# Open-mode extraction
# =============================================================================

_OPEN_PROMPT = """\
Context:
You are an expert analyst specializing in extracting key factors influencing \
{topic} from interview transcripts.

Interview Transcript:
{transcript}

=*=*=

Task description:
Analyze the interview transcript and extract factors that influence the \
participant's behavior regarding {topic}.
Extract both (1) factors that encourage the behavior, and (2) factors that \
discourage it.

For each factor, determine whether it relates to:
1) the personal behaviors and motivations of the interviewee, or
2) the behaviors and motivations of their social contacts

Only extract social-contact factors when they plausibly influence the \
interviewee's behavior.

=*=*=

Extraction rules:
1. Extract a maximum of {max_nodes} short statements (max 10 words each).
2. Extract at least 1 statement about the personal habits of the interviewee.
3. For each statement provide:
   - stance: concise summary of the attitude or behavior (no effects)
   - type: PERSONAL or SOCIAL
   - category: BEHAVIOR or MOTIVATION
   - effect: INCREASE or DECREASE
4. If you cannot reliably assign an effect, do not include the statement.

=*=*=

Extraction guidelines:
1. Only include relevant influences — exclude anything unimportant or unclear.
2. Differentiate behavior from motivation — each statement should describe one, \
not both. Split compound statements.
3. Each statement must be well-formed in isolation and something the interviewee \
would plausibly agree with.

=*=*=

Output Format (JSON ONLY):
{{
  "results": [
    {{
      "stance": "<concise summary>",
      "type": "<PERSONAL or SOCIAL>",
      "category": "<BEHAVIOR or MOTIVATION>",
      "effect": "<INCREASE or DECREASE>"
    }}
  ]
}}
Return ONLY the JSON object.
"""


def _make_open_prompt(questions_answers: dict) -> str:
    cfg = get_config()
    topic = cfg["interview"].get("topic", "the topic")
    max_nodes = cfg["canvas"].get("max_nodes", 10)
    transcript = "\n".join(f"Q: {q}\nA: {a}" for q, a in questions_answers.items())
    return _OPEN_PROMPT.format(
        topic=topic,
        max_nodes=max_nodes,
        transcript=transcript,
    )


def detect_open_stances(questions_answers: dict) -> List[dict]:
    """Sync open-mode extraction. Returns normalized node dicts."""
    prompt = _make_open_prompt(questions_answers)
    result = call_llm(response_model=OpenNodeList, prompt=prompt, temp=0.3)
    return _normalize_open(result.results)


async def async_detect_open_stances_raw(questions_answers: dict) -> tuple:
    """Async open-mode extraction returning (node_list, prompt_used)."""
    prompt = _make_open_prompt(questions_answers)
    raw = await async_call_llm_raw(prompt, temp=0.3)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(cleaned)

    if isinstance(parsed, dict) and "results" in parsed:
        raw_list = parsed["results"]
    elif isinstance(parsed, list):
        raw_list = parsed
    else:
        raise ValueError("Response not in expected JSON list format.")

    return _normalize_open_raw(raw_list), prompt


def _normalize_open(nodes: List[OpenNode]) -> List[dict]:
    return [
        {
            "stance_id":   f"open_{i}",
            "statement":   n.stance,
            "label":       n.stance,
            "short_label": n.stance[:30],
            "direction":   "pro" if n.effect == "INCREASE" else "anti",
            "likert":      5 if n.effect == "INCREASE" else 2,
            "evidence":    "",
            "type":        n.type,
            "category":    n.category,
            "effect":      n.effect,
        }
        for i, n in enumerate(nodes)
    ]


def _normalize_open_raw(nodes: list) -> list:
    return [
        {
            "stance_id":   f"open_{i}",
            "statement":   n.get("stance", ""),
            "label":       n.get("stance", ""),
            "short_label": n.get("stance", "")[:30],
            "direction":   "pro" if n.get("effect") == "INCREASE" else "anti",
            "likert":      5 if n.get("effect") == "INCREASE" else 2,
            "evidence":    "",
            "type":        n.get("type", ""),
            "category":    n.get("category", ""),
            "effect":      n.get("effect", ""),
        }
        for i, n in enumerate(nodes)
    ]


# =============================================================================
# Unified dispatcher
# =============================================================================

def extract_nodes(questions_answers: dict) -> List[dict]:
    """Sync extraction — dispatches based on config mode."""
    mode = get_config()["node_extraction"].get("mode", "closed")
    if mode == "open":
        return detect_open_stances(questions_answers)
    return detect_closed_stances(questions_answers)


async def async_extract_nodes(questions_answers: dict) -> tuple:
    """Async extraction — returns (node_list, prompt_used)."""
    mode = get_config()["node_extraction"].get("mode", "closed")
    if mode == "open":
        return await async_detect_open_stances_raw(questions_answers)
    return await async_detect_closed_stances_raw(questions_answers)
