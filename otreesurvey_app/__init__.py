from otree.api import *
import json, time, asyncio, re
import random
from .llm_prompts import *
from datetime import datetime
from otree.api import Page

from openai import AsyncOpenAI
from dotenv import load_dotenv
load_dotenv()

def _get_async_client():
    return AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

doc = """
Visual Network Tool — configurable belief-network experiment.
"""

# =============================================================================
# NODE VISUAL ENCODING
# =============================================================================
_AGREEMENT_COLORS = {
    1: '#d73027',
    2: '#d73027',
    3: '#d73027',
    4: '#006d2c',
    5: '#006d2c',
    6: '#006d2c',
}

def _node_radius(importance):
    v = max(1, min(7, importance or 4))
    return 10 + (v - 1) * 2

def _node_color(agreement):
    v = max(1, min(6, agreement or 4))
    return _AGREEMENT_COLORS[v]

def get_node_display_data(player):
    """Return [{belief, short_label, radius, color}, ...] for every node in final_nodes."""
    nodes = json.loads(player.final_nodes or '[]')
    return [
        {
            "belief":      n.get("dynamic_sentence_simple") or n.get("belief", ""),
            "short_label": n.get("short_label", ""),
            "radius":      14,
            "color":       _node_color(n.get("rating")),
        }
        for n in nodes
    ]


def stamp(player, label: str):
    """Append {'label': <string>, 'ts': <float>} to player's JSON log."""
    try:
        arr = json.loads(player.page_timings_json or '[]')
        if not isinstance(arr, list):
            arr = []
    except Exception:
        arr = []
    arr.append({'label': str(label), 'ts': time.time()})
    player.page_timings_json = json.dumps(arr)


def _strip_prefix(template):
    """Remove 'I [SCALE] that ' prefix."""
    return re.sub(r'^I \[SCALE\] that ', '', template)


# Condition helpers
_INTERVIEW_CONDITIONS   = {'interview', 'interview_short', 'interview_tag'}
_CANVAS_CONDITIONS      = {'direct', 'direct_short', 'direct_v2', 'direct_v2_short',
                           'direct_noprefix', 'color', 'color_tag',
                           'interview', 'interview_short', 'interview_tag', 'demo'}
_SHORT_LABEL_CONDITIONS = {'direct_short', 'interview_short', 'direct_v2_short'}
_V2_CONDITIONS          = {'direct_v2', 'direct_v2_short', 'color', 'color_tag',
                           'interview_tag'}
_NOPREFIX_CONDITIONS    = {'direct_noprefix', 'color', 'color_tag', 'interview_tag', 'demo'}
_TAG_CONDITIONS         = {'color_tag', 'interview_tag'}


class C(BaseConstants):
    NAME_IN_URL = 'survey'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1
    MAX_TURNS = 8
    MAX_BELIEF_ITEMS = 30
    NUM_NODES_THRESHOLD = 3
    NUM_NODES_MAX = 10


class Subsession(BaseSubsession):
    pass


def creating_session(subsession: Subsession):
    for player in subsession.get_players():
        player.condition = 'color_tag'


class Group(BaseGroup):
    pass


class Player(BasePlayer):

    consent_given = models.BooleanField(
        choices=[[True, 'I consent'], [False, 'I do not consent']],
        widget=widgets.RadioSelect,
        label=''
    )

    prompt_used = models.LongStringField(blank=True)
    llm_result = models.LongStringField(blank=True)

    generated_nodes = models.LongStringField(blank=True)
    generated_nodes_accuracy = models.LongStringField(blank=True)
    generated_nodes_relevance = models.LongStringField(blank=True)
    final_nodes = models.LongStringField(blank=True)
    num_nodes = models.IntegerField(initial=0)

    positions_1 = models.LongStringField(blank=True)
    positions_2 = models.LongStringField(blank=True)
    positions_3 = models.LongStringField(blank=True)
    edges_2 = models.LongStringField(blank=True)
    edges_3 = models.LongStringField(blank=True)

    conversation_json = models.LongStringField(initial="[]")
    current_answer = models.LongStringField(blank=True)
    voice_answer = models.LongStringField(blank=True)
    interview_feedback = models.LongStringField(label="", blank=True)

    page_timings_json = models.LongStringField(initial='[]')

    final_feedback = models.LongStringField(label='', blank=True)

    llm_edge_prompt = models.LongStringField(blank=True)
    llm_edges = models.LongStringField(blank=True)

    conv_overall_0_100 = models.IntegerField(min=0, max=100)
    conv_overall_cat = models.IntegerField(
        choices=[
            (1, 'Terrible'), (2, 'Not good'), (3, 'Average / Neutral'),
            (4, 'Good'), (5, 'Excellent'),
        ]
    )
    conv_relevant_0_100 = models.IntegerField(min=0, max=100)
    conv_relevant_cat = models.IntegerField(
        choices=[
            (1, 'Strongly disagree'), (2, 'Somewhat disagree'),
            (3, 'Neither agree nor disagree'), (4, 'Somewhat agree'),
            (5, 'Strongly agree'),
        ]
    )
    conv_easy_chat_0_100 = models.IntegerField(min=0, max=100)
    conv_easy_chat_cat = models.IntegerField(
        choices=[
            (1, 'Strongly disagree'), (2, 'Somewhat disagree'),
            (3, 'Neither agree nor disagree'), (4, 'Somewhat agree'),
            (5, 'Strongly agree'),
        ]
    )
    conv_comfort_0_100 = models.IntegerField(min=0, max=100)
    conv_comfort_cat = models.IntegerField(
        choices=[
            (1, 'Strongly disagree'), (2, 'Somewhat disagree'),
            (3, 'Neither agree nor disagree'), (4, 'Somewhat agree'),
            (5, 'Strongly agree'),
        ]
    )
    conv_creepy_0_100 = models.IntegerField(min=0, max=100)
    conv_creepy_cat = models.IntegerField(
        choices=[
            (1, 'Strongly disagree'), (2, 'Somewhat disagree'),
            (3, 'Neither agree nor disagree'), (4, 'Somewhat agree'),
            (5, 'Strongly agree'),
        ]
    )
    conv_open_feedback = models.LongStringField(blank=True)

    prolific_pid = models.StringField(blank=True)
    prolific_study_id = models.StringField(blank=True)
    prolific_session_id = models.StringField(blank=True)

    exit_status = models.StringField(blank=True)
    last_page = models.StringField(blank=True)
    exit_url = models.StringField(blank=True)

    canvas_difficulty_placement = models.IntegerField(blank=True)
    canvas_difficulty_pos = models.IntegerField(blank=True)
    canvas_difficulty_neg = models.IntegerField(blank=True)
    canvas_clarity_statements = models.IntegerField(blank=True)
    canvas_usability_comment = models.LongStringField(blank=True)

    condition = models.StringField(
        choices=[
            ['interview_tag', 'With interview'],
            ['color_tag', 'Without interview'],
            ['demo', 'Demo (recording only)'],
        ],
        widget=widgets.RadioSelect,
        blank=True,
    )

    dynamic_belief_ratings_json = models.LongStringField(blank=True)


for i in range(C.MAX_BELIEF_ITEMS):
    setattr(Player, f"belief_accuracy_{i}", models.IntegerField(blank=True))
    setattr(Player, f"belief_relevance_{i}", models.IntegerField(blank=True))


_DEMO_NODES = [
    {"dynamic_sentence_simple": "I want to become fluent in Spanish: agree",
     "short_label": "Fluency goal", "rating": 5},
    {"dynamic_sentence_simple": "I practice Spanish for 20 minutes every day: agree",
     "short_label": "Daily practice", "rating": 5},
    {"dynamic_sentence_simple": "A colleague has invited me to join a Spanish conversation group: agree",
     "short_label": "Conversation group", "rating": 5},
    {"dynamic_sentence_simple": "I enjoy practicing Spanish: disagree",
     "short_label": "Enjoy practicing", "rating": 2},
    {"dynamic_sentence_simple": "I feel self-conscious when speaking Spanish in front of others: agree",
     "short_label": "Self-conscious", "rating": 5},
]


# =============================================================================
# PAGES
# =============================================================================

class Consent(Page):
    form_model = 'player'
    form_fields = ['consent_given']

    @staticmethod
    def vars_for_template(player: Player):
        from .study_config import CONSENT_INTRO, CONSENT_HIGHLIGHT
        stamp(player, 'consent:render')
        return dict(
            consent_intro=CONSENT_INTRO,
            consent_highlight=CONSENT_HIGHLIGHT,
        )

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        participant = player.participant
        pid = participant.label or participant.vars.get('PROLIFIC_PID') or ''
        player.prolific_pid = pid
        player.prolific_study_id = (
            participant.vars.get('STUDY_ID')
            or participant.vars.get('study_id')
            or ''
        )
        player.prolific_session_id = (
            participant.vars.get('SESSION_ID')
            or participant.vars.get('session_id')
            or ''
        )
        stamp(player, 'consent:submit')

    def error_message(self, values):
        if values['consent_given'] is None:
            return "Please indicate whether you consent to participate."


class ConditionSelector(Page):
    form_model = 'player'
    form_fields = ['condition']

    @staticmethod
    def is_displayed(player: Player):
        return False

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        if not player.field_maybe_none('condition'):
            player.condition = 'color_tag'
        if player.field_maybe_none('condition') == 'demo':
            player.final_nodes = json.dumps(_DEMO_NODES)
            player.num_nodes = len(_DEMO_NODES)


class Information(Page):
    form_model = 'player'

    @staticmethod
    def is_displayed(player: Player):
        return player.consent_given and player.field_maybe_none('condition') in _INTERVIEW_CONDITIONS

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        stamp(player, 'information:submit')


class InterviewMain(Page):
    form_model = 'player'
    form_fields = ['current_answer', 'voice_answer']

    @staticmethod
    def vars_for_template(player: Player):
        conversation = json.loads(player.conversation_json)

        if "interview_turns" not in player.participant.vars:
            player.participant.vars["interview_turns"] = 1

        if not conversation:
            from .llm_prompts import INTERVIEW_OPENING_QUESTION
            conversation.append({
                "question": INTERVIEW_OPENING_QUESTION,
                "answer": "",
                "time_sent": datetime.utcnow().isoformat(),
                "time_received": None
            })
            player.conversation_json = json.dumps(conversation)

        return dict(
            conversation=conversation,
            current_turn=player.participant.vars["interview_turns"],
            max_turns=C.MAX_TURNS,
            progress_percentage=int(100 * player.participant.vars["interview_turns"] / C.MAX_TURNS)
        )

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        conversation = json.loads(player.conversation_json)

        response = player.current_answer.strip() if player.current_answer else player.voice_answer.strip()
        input_mode = "text" if player.current_answer.strip() else "voice" if player.voice_answer.strip() else "unknown"

        if response:
            conversation[-1]["answer"] = response
            conversation[-1]["input_mode"] = input_mode
            conversation[-1]["time_received"] = datetime.utcnow().isoformat()
        else:
            conversation[-1]["answer"] = "[No response detected]"
            conversation[-1]["input_mode"] = "unknown"
            conversation[-1]["time_received"] = datetime.utcnow().isoformat()

        current_turn = player.participant.vars["interview_turns"]

        if current_turn < C.MAX_TURNS:
            qa_history = [
                UserAnswer(question=entry["question"], answer=entry["answer"])
                for entry in conversation if entry.get("answer") and entry["answer"].strip()
            ]
            llm_turn = generate_conversational_question(qa_history, C.MAX_TURNS)

            conversation.append({
                "question": llm_turn.interviewer_utterance,
                "answer": "",
                "time_sent": datetime.utcnow().isoformat()
            })

        player.conversation_json = json.dumps(conversation)
        player.participant.vars["interview_turns"] = current_turn + 1
        stamp(player, 'interviewmain:submit')

    @staticmethod
    def is_displayed(player: Player):
        return (
            player.consent_given
            and player.field_maybe_none('condition') in _INTERVIEW_CONDITIONS
            and player.participant.vars.get("interview_turns", 1) <= C.MAX_TURNS
        )


class ConversationFeedback(Page):
    form_model = 'player'
    form_fields = [
        'conv_overall_0_100', 'conv_overall_cat',
        'conv_relevant_0_100', 'conv_relevant_cat',
        'conv_easy_chat_0_100', 'conv_easy_chat_cat',
        'conv_comfort_0_100', 'conv_comfort_cat',
        'conv_creepy_0_100', 'conv_creepy_cat',
        'conv_open_feedback',
    ]

    @staticmethod
    def is_displayed(player):
        return player.consent_given and player.field_maybe_none('condition') in _INTERVIEW_CONDITIONS

    @staticmethod
    async def live_method(player, data):
        async def call_and_parse(prompt, retries=3, delay=3):
            for attempt in range(retries):
                try:
                    completion = await _get_async_client().chat.completions.create(
                        model="gpt-4.1-2025-04-14",
                        messages=[{"role": "user", "content": prompt}],
                        stream=False,
                    )
                    raw = completion.choices[0].message.content.strip()

                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        cleaned = raw.replace("```json", "").replace("```", "").strip()
                        parsed = json.loads(cleaned)

                    if isinstance(parsed, dict) and "detected" in parsed:
                        return parsed["detected"]
                    elif isinstance(parsed, dict) and "results" in parsed:
                        return parsed["results"]
                    elif isinstance(parsed, list):
                        return parsed
                    else:
                        raise ValueError("Response not in expected JSON list format.")

                except Exception as e:
                    print(f"Attempt {attempt+1} failed:", e)
                    if attempt < retries - 1:
                        await asyncio.sleep(delay)
                    else:
                        raise

        try:
            conversation = json.loads(player.conversation_json or "[]")
            qa = {
                e["question"]: e["answer"]
                for e in conversation
                if e.get("answer") and str(e["answer"]).strip()
            }

            prompt = make_node_prompt(qa)
            player.prompt_used = prompt

            llm_nodes_list = await call_and_parse(prompt, retries=3, delay=2)
            llm_nodes_list = enrich_detected_stances(llm_nodes_list or [])

            player.llm_result = json.dumps({"detected": llm_nodes_list}, indent=2)
            player.generated_nodes = json.dumps(llm_nodes_list)
            player.num_nodes = len(llm_nodes_list)

            yield {player.id_in_group: {"done": True}}

        except Exception as e:
            print("LLM permanently failed:", e)
            yield {player.id_in_group: {"done": False}}

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, "conv_feedback:submit")


class DynamicBeliefRating(Page):
    form_model = 'player'
    form_fields = ['dynamic_belief_ratings_json']

    @staticmethod
    def vars_for_template(player: Player):
        from .dynamic_items import DYNAMIC_ITEMS
        condition = player.field_maybe_none('condition')

        if condition in _INTERVIEW_CONDITIONS:
            detected_ids = {
                n.get('stance_id')
                for n in json.loads(player.generated_nodes or '[]')
                if n.get('stance_id')
            }
            source = [item for item in DYNAMIC_ITEMS if item['id'] in detected_ids]
            if not source:
                source = list(DYNAMIC_ITEMS)
        else:
            source = list(DYNAMIC_ITEMS)

        rnd = random.Random(player.participant.code)
        rnd.shuffle(source)

        use_v2 = condition in _V2_CONDITIONS
        items = [
            {
                "index":     i,
                "id":        item["id"],
                "template":  item.get("template_v2", item["template"]) if use_v2 else item["template"],
                "labels":    item["labels"],
                "anchor_lo": item["anchor_lo"],
                "anchor_hi": item["anchor_hi"],
            }
            for i, item in enumerate(source)
        ]
        return dict(items_json=json.dumps(items), num_items=len(items),
                    show_importance="true", scale_max=6, start_val=1)

    @staticmethod
    def is_displayed(player: Player):
        cond = player.field_maybe_none('condition')
        return player.consent_given and cond in _CANVAS_CONDITIONS and cond != 'demo'

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        raw = player.field_maybe_none('dynamic_belief_ratings_json') or '[]'
        try:
            ratings = json.loads(raw)
        except Exception:
            ratings = []

        from .dynamic_items import DYNAMIC_ITEMS
        cond = player.field_maybe_none('condition') or ''
        use_v2 = cond in _V2_CONDITIONS
        use_noprefix = cond in _NOPREFIX_CONDITIONS
        use_tag = cond in _TAG_CONDITIONS
        item_lookup = {item["id"]: item for item in DYNAMIC_ITEMS}
        template_lookup = {
            item["id"]: item.get("template_v2", item["template"]) if use_v2 else item["template"]
            for item in DYNAMIC_ITEMS
        }

        final = []
        for entry in ratings:
            v = entry.get("value", 0)
            simple_word = "disagree" if v <= 3 else "agree"
            tmpl = template_lookup.get(entry.get("id", ""), "")
            if use_noprefix:
                content = _strip_prefix(tmpl) if tmpl else ""
                simple_sentence = f"{content}: {simple_word}" if use_tag else content
            else:
                simple_sentence = tmpl.replace("[SCALE]", simple_word) if tmpl else simple_word
            item_meta = item_lookup.get(entry.get("id", ""), {})
            final.append({
                "belief":                  simple_word,
                "rating":                  v,
                "relevance":               entry.get("importance", 4),
                "dynamic_id":              entry.get("id", ""),
                "dynamic_val":             v,
                "dynamic_importance":      entry.get("importance"),
                "dynamic_sentence_full":   entry.get("sentence", ""),
                "dynamic_sentence_simple": simple_sentence,
                "short_label":             item_meta.get("short_label", ""),
            })
        player.final_nodes = json.dumps(final)
        player.num_nodes = len(final)
        stamp(player, 'dynamic_belief_rating:submit')


class MapVideoIntro(Page):
    @staticmethod
    def vars_for_template(player):
        demo_statements = [
            {
                "text":  n["dynamic_sentence_simple"],
                "color": _node_color(n["rating"]),
            }
            for n in _DEMO_NODES
        ]
        return dict(demo_statements=demo_statements, own_statements_colored=demo_statements)

    @staticmethod
    def is_displayed(player):
        return (
            player.num_nodes >= C.NUM_NODES_THRESHOLD
            and player.consent_given
            and player.field_maybe_none('condition') in _CANVAS_CONDITIONS
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, 'map_video_intro:submit')


class MapIntro(Page):
    @staticmethod
    def vars_for_template(player):
        nodes = json.loads(player.final_nodes or "[]")
        cond = player.field_maybe_none('condition') or ''
        noprefix = cond in _NOPREFIX_CONDITIONS

        own_statements = [
            n.get("dynamic_sentence_simple") or n.get("dynamic_sentence_full") or n["belief"]
            for n in nodes
            if n.get("belief") or n.get("dynamic_sentence_simple")
        ]

        own_statements_colored = [
            {
                "text":  n.get("dynamic_sentence_simple") or n.get("dynamic_sentence_full") or n["belief"],
                "color": _node_color(n.get("rating")),
                "word":  n.get("belief", ""),
            }
            for n in nodes
            if n.get("belief") or n.get("dynamic_sentence_simple")
        ]

        show_transcript = cond in _INTERVIEW_CONDITIONS
        qa_pairs = json.loads(player.conversation_json or "[]") if show_transcript else []

        return dict(
            transcript=qa_pairs,
            show_transcript=show_transcript,
            own_statements=own_statements,
            own_statements_colored=own_statements_colored,
            noprefix=noprefix,
            is_demo=cond == 'demo',
        )

    @staticmethod
    def is_displayed(player):
        return (
            player.num_nodes >= C.NUM_NODES_THRESHOLD
            and player.consent_given
            and player.field_maybe_none('condition') in _CANVAS_CONDITIONS
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, 'map_intro:submit')


class MapNodePlacement(Page):
    form_model = 'player'
    form_fields = ['positions_1']

    @staticmethod
    def vars_for_template(player):
        node_data = get_node_display_data(player)
        cond = player.field_maybe_none('condition') or ''
        show_transcript = cond in _INTERVIEW_CONDITIONS
        qa_pairs = json.loads(player.conversation_json or "[]") if show_transcript else []
        return dict(
            node_data_json=json.dumps(node_data),
            short_labels="true" if cond in _SHORT_LABEL_CONDITIONS else "false",
            transcript=qa_pairs,
            show_transcript=show_transcript,
        )

    @staticmethod
    def is_displayed(player: Player):
        return (
            player.num_nodes >= C.NUM_NODES_THRESHOLD
            and player.consent_given
            and player.field_maybe_none('condition') in _CANVAS_CONDITIONS
        )

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        stamp(player, 'self_map:submit')


class MapEdgePos(Page):
    form_model = 'player'
    form_fields = ['positions_2', 'edges_2']

    @staticmethod
    def vars_for_template(player):
        node_data = get_node_display_data(player)
        positions = json.loads(player.positions_1 or '[]')
        pos_by_belief = {p.get('full_label', p['label']): p for p in positions}
        belief_points = [
            {
                "label":       nd["belief"],
                "short_label": nd.get("short_label", ""),
                "x":           pos_by_belief[nd["belief"]]['x'],
                "y":           pos_by_belief[nd["belief"]]['y'],
                "radius":      nd["radius"],
                "color":       nd["color"],
            }
            for nd in node_data
        ]
        cond = player.field_maybe_none('condition') or ''
        show_transcript = cond in _INTERVIEW_CONDITIONS
        qa_pairs = json.loads(player.conversation_json or "[]") if show_transcript else []
        return dict(
            belief_points=belief_points,
            short_labels="true" if cond in _SHORT_LABEL_CONDITIONS else "false",
            belief_edges_json=json.dumps([]),
            transcript=qa_pairs,
            show_transcript=show_transcript,
        )

    @staticmethod
    def is_displayed(player):
        return (
            player.num_nodes >= C.NUM_NODES_THRESHOLD
            and player.consent_given
            and player.field_maybe_none('condition') in _CANVAS_CONDITIONS
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, 'self_edge_pos:submit')


class MapEdgeNeg(Page):
    form_model = 'player'
    form_fields = ['positions_3', 'edges_3']

    @staticmethod
    def vars_for_template(player):
        node_data = get_node_display_data(player)
        positions = json.loads(player.positions_2 or '[]')
        if not positions:
            positions = json.loads(player.positions_1 or '[]')
        prior_edges = json.loads(player.edges_2 or '[]')
        pos_by_belief = {p.get('full_label', p['label']): p for p in positions}
        belief_points = [
            {
                "label":       nd["belief"],
                "short_label": nd.get("short_label", ""),
                "x":           pos_by_belief[nd["belief"]]['x'],
                "y":           pos_by_belief[nd["belief"]]['y'],
                "radius":      nd["radius"],
                "color":       nd["color"],
            }
            for nd in node_data
        ]
        cond = player.field_maybe_none('condition') or ''
        show_transcript = cond in _INTERVIEW_CONDITIONS
        qa_pairs = json.loads(player.conversation_json or "[]") if show_transcript else []
        return dict(
            belief_points=belief_points,
            short_labels="true" if cond in _SHORT_LABEL_CONDITIONS else "false",
            belief_edges_json=json.dumps(prior_edges),
            transcript=qa_pairs,
            show_transcript=show_transcript,
        )

    @staticmethod
    def is_displayed(player):
        return (
            player.num_nodes >= C.NUM_NODES_THRESHOLD
            and player.consent_given
            and player.field_maybe_none('condition') in _CANVAS_CONDITIONS
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, 'self_edge_neg:submit')


class CanvasFeedback(Page):
    form_model = 'player'
    form_fields = [
        'canvas_difficulty_placement',
        'canvas_difficulty_pos',
        'canvas_difficulty_neg',
        'canvas_clarity_statements',
        'canvas_usability_comment',
    ]

    @staticmethod
    def is_displayed(player: Player):
        return (
            player.consent_given
            and player.field_maybe_none('condition') in _CANVAS_CONDITIONS
            and player.num_nodes >= C.NUM_NODES_THRESHOLD
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, 'canvas_feedback:submit')


class Feedback(Page):
    form_model = 'player'
    form_fields = ['final_feedback']

    @staticmethod
    def is_displayed(player: Player):
        return player.consent_given

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, 'finalfeedback:submit')


class LinkCompletion(Page):

    @staticmethod
    def is_displayed(player: Player):
        return (
            player.consent_given
            and player.num_nodes >= C.NUM_NODES_THRESHOLD
        )

    @staticmethod
    def vars_for_template(player: Player):
        player.exit_status = 'completed'
        player.last_page = 'LinkCompletion'
        player.exit_url = player.session.config['completionlink']
        stamp(player, 'exit:completed')
        return {}

    @staticmethod
    def js_vars(player: Player):
        return dict(url=player.session.config['completionlink'])


class LinkFailedChecks(Page):

    @staticmethod
    def is_displayed(player: Player):
        return (
            player.consent_given
            and player.num_nodes < C.NUM_NODES_THRESHOLD
        )

    @staticmethod
    def vars_for_template(player: Player):
        player.exit_status = 'failed_checks'
        player.last_page = 'LinkFailedChecks'
        player.exit_url = player.session.config.get('returnlink', player.session.config['completionlink'])
        stamp(player, 'exit:failed_checks')
        return {}

    @staticmethod
    def js_vars(player: Player):
        return dict(url=player.session.config.get('returnlink', player.session.config['completionlink']))


class LinkNoConsent(Page):

    @staticmethod
    def is_displayed(player: Player):
        return not player.consent_given

    @staticmethod
    def vars_for_template(player: Player):
        player.exit_status = 'no_consent'
        player.last_page = 'LinkNoConsent'
        player.exit_url = player.session.config['noconsentlink']
        stamp(player, 'exit:no_consent')
        return {}

    @staticmethod
    def js_vars(player: Player):
        return dict(url=player.session.config['noconsentlink'])


page_sequence = [
    Consent,
    LinkNoConsent,
    ConditionSelector,
    Information,
    *[InterviewMain for _ in range(C.MAX_TURNS)],
    ConversationFeedback,
    DynamicBeliefRating,
    MapVideoIntro,
    MapIntro,
    MapNodePlacement,
    MapEdgePos,
    MapEdgeNeg,
    CanvasFeedback,
    Feedback,
    LinkCompletion,
]
