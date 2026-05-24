from otree.api import *
import json

from .constants import C
from .pages import (
    Consent, ConditionSelector, LinkNoConsent, LinkCompletion, LinkFailedChecks,
    Information, InterviewMain, ConversationFeedback,
    DynamicBeliefRating,
    MapVideoIntro, MapIntro, MapNodePlacement, MapEdgePage,
    CanvasFeedback, Feedback,
)

doc = """
Visual Network Tool — configurable belief-network experiment.
"""


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

    # Legacy edge fields (kept for backward compat with existing sessions)
    positions_2 = models.LongStringField(blank=True)
    positions_3 = models.LongStringField(blank=True)
    edges_2 = models.LongStringField(blank=True)
    edges_3 = models.LongStringField(blank=True)

    # Generic edge page fields — temp fields overwritten each page,
    # then copied to indexed storage in before_next_page
    _edge_positions_tmp = models.LongStringField(blank=True)
    _edge_data_tmp = models.LongStringField(blank=True)

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

for i in range(C.MAX_EDGE_PAGES):
    setattr(Player, f"edge_positions_{i}", models.LongStringField(blank=True))
    setattr(Player, f"edge_data_{i}", models.LongStringField(blank=True))


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
    *[MapEdgePage for _ in range(C.MAX_EDGE_PAGES)],
    CanvasFeedback,
    Feedback,
    LinkCompletion,
]
