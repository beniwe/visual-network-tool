import json
from otree.api import Page

from ..helpers import stamp, _CANVAS_CONDITIONS
from ..constants import C


class CanvasFeedback(Page):
    form_model = 'player'
    form_fields = [
        'canvas_difficulty_placement',
        'canvas_clarity_statements',
        'canvas_usability_comment',
        'canvas_edge_difficulty_json',
    ]

    @staticmethod
    def vars_for_template(player):
        from ..config_loader import get_config
        edge_types = get_config()["canvas"]["edges"]
        return dict(edge_types_json=json.dumps(edge_types))

    @staticmethod
    def is_displayed(player):
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
    def is_displayed(player):
        return player.consent_given

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, 'finalfeedback:submit')
