import json
from otree.api import Page

from ..helpers import (
    stamp, get_node_display_data, _node_color, _DEMO_NODES,
    _CANVAS_CONDITIONS, _INTERVIEW_CONDITIONS, _SHORT_LABEL_CONDITIONS,
    _NOPREFIX_CONDITIONS,
)
from ..constants import C


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
    def is_displayed(player):
        return (
            player.num_nodes >= C.NUM_NODES_THRESHOLD
            and player.consent_given
            and player.field_maybe_none('condition') in _CANVAS_CONDITIONS
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
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
