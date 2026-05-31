# Visual Network Tool

A configurable oTree experiment for measuring belief systems through
LLM-guided interviews and visual network mapping.

## Project layout

```
otreesurvey_app/
├── __init__.py              ← models, page imports, page_sequence
├── constants.py             ← BaseConstants (MAX_TURNS, thresholds, etc.)
├── helpers.py               ← node display, timing, condition sets
├── config_loader.py         ← loads and caches study_config.json
├── study_config.json        ← all study settings in one place
├── dynamic_items.py         ← thin wrapper loading items from config
├── llm_prompts.py           ← interview prompt generation
├── llm/
│   ├── client.py            ← unified LLM client (OpenAI, Aqueduct, etc.)
│   └── node_extraction.py   ← closed + open stance detection
├── pages/
│   ├── consent.py           ← consent, condition selector, exit pages
│   ├── interview.py         ← interview + conversation feedback
│   ├── belief_rating.py     ← dynamic belief rating
│   ├── canvas.py            ← node placement, edge pages, intro pages
│   └── feedback.py          ← canvas feedback, final feedback
├── templates/otreesurvey_app/
│   ├── Consent.html, ConditionSelector.html, ...
│   ├── InterviewMain.html
│   ├── DynamicBeliefRating.html
│   ├── MapNodePlacement.html
│   ├── MapEdge.html         ← generic template for all edge types
│   └── ...
└── static/otreesurvey_app/
    └── canvasflex.js        ← canvas drawing library
```

## Configuration

Everything is driven by `study_config.json`. Key sections:

- **study** — consent text, completion URLs
- **llm** — provider, model, API key env var, temperature, retries
- **interview** — max turns, input mode (voice/text/both), topic, prompts
- **node_extraction** — mode (`closed` or `open`), predefined items with codebooks
- **node_rating** — rating dimensions (agreement, importance, etc.) with scales and anchors
- **canvas.nodes** — which dimension maps to color/size, color thresholds, radius range
- **canvas.edges** — array of edge types with label, color, verb, visibility of prior edges
- **demo_nodes** — demo statements for the training video page

## Page sequence

```python
page_sequence = [
    Consent, LinkNoConsent, ConditionSelector,
    Information,
    *[InterviewMain for _ in range(C.MAX_TURNS)],  # 20 slots, actual turns from config
    ConversationFeedback,
    DynamicBeliefRating,
    MapVideoIntro, MapIntro, MapNodePlacement,
    *[MapEdgePage for _ in range(C.MAX_EDGE_PAGES)],  # 10 slots, actual types from config
    CanvasFeedback, Feedback,
    LinkCompletion,
]
```

Pages use `is_displayed()` to gate themselves based on condition and config.
Interview pages only show for interview conditions. Edge page slots only
show for as many edge types as defined in config.

## LLM client

`llm/client.py` provides `call_llm()` (sync) and `async_call_llm()` for
structured output via the `instructor` library. Supports OpenAI, Aqueduct
(TU Wien), or any OpenAI-compatible API by setting `provider`, `api_key_env`,
and `base_url_env` in config. Includes rate limiting (50 req/min).

## Node extraction modes

- **Closed** — matches interview transcript against predefined stances from
  config, each with a codebook. Returns Likert scores and evidence quotes.
- **Open** — extracts arbitrary beliefs/stances from the transcript without
  a predefined list. Returns stance, type, category, and effect.

## Running locally

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
otree devserver
```

Create an `.env` file in `otreesurvey_app/` with your API key:
```
OPENAI_API_KEY=sk-...
```

## Conditions

- `interview_tag` — full flow with LLM interview
- `color_tag` — skip interview, rate all predefined stances directly
- `demo` — uses demo nodes from config, no interview or rating
