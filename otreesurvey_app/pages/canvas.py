import json
from otree.api import Page

from ..helpers import (
    stamp, get_node_display_data, _node_color, get_demo_nodes,
    _CANVAS_CONDITIONS, _INTERVIEW_CONDITIONS, _SHORT_LABEL_CONDITIONS,
    _NOPREFIX_CONDITIONS,
)
from ..constants import C


class MapVideoIntro(Page):
    @staticmethod
    def vars_for_template(player):
        from ..config_loader import get_config
        edge_types = get_config()["canvas"]["edges"]
        demo_statements = [
            {
                "text":  n["dynamic_sentence_simple"],
                "color": _node_color(n.get("rating")),
            }
            for n in get_demo_nodes()
        ]
        edge_types_display = [
            dict(et, is_first=(i == 0))
            for i, et in enumerate(edge_types)
        ]
        return dict(
            demo_statements=demo_statements,
            own_statements_colored=demo_statements,
            edge_types=edge_types_display,
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
        stamp(player, 'map_video_intro:submit')


class MapIntro(Page):
    @staticmethod
    def vars_for_template(player):
        from ..config_loader import get_config
        edge_types = get_config()["canvas"]["edges"]
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

        # Build edge type chip HTML for the intro text
        chips = [
            '<span class="chip chip-edge" style="background:{c}22;border-color:{c};color:{c}">{l}</span>'.format(
                c=et["color"], l=et["label"],
            )
            for et in edge_types
        ]
        if len(chips) > 1:
            edge_chips_html = ', '.join(chips[:-1]) + ' and ' + chips[-1]
        else:
            edge_chips_html = chips[0] if chips else ''

        return dict(
            transcript=qa_pairs,
            show_transcript=show_transcript,
            own_statements=own_statements,
            own_statements_colored=own_statements_colored,
            noprefix=noprefix,
            is_demo=cond == 'demo',
            edge_chips_html=edge_chips_html,
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


class MapEdgePage(Page):
    """Generic edge-drawing page, repeated once per edge type in study_config.

    Uses ``participant.vars["_edge_page_counter"]`` to track which edge type
    is being shown.  Form data goes through temp fields and gets copied to
    indexed storage (``edge_positions_N`` / ``edge_data_N``) in
    ``before_next_page``.
    """
    form_model = 'player'
    form_fields = ['edge_positions_tmp', 'edge_data_tmp']
    template_name = 'otreesurvey_app/MapEdge.html'

    @staticmethod
    def vars_for_template(player):
        from ..config_loader import get_config
        edge_types = get_config()["canvas"]["edges"]
        idx = player.participant.vars.get('_edge_page_counter', 0)
        edge_cfg = dict(edge_types[idx])
        edge_cfg['label_lower'] = edge_cfg.get('label', '').lower()

        node_data = get_node_display_data(player)

        # Positions: from previous edge page, or from initial node placement
        if idx > 0:
            prev_pos = player.field_maybe_none(f'edge_positions_{idx - 1}') or ''
            positions = json.loads(prev_pos) if prev_pos else []
        else:
            positions = []
        if not positions:
            positions = json.loads(player.field_maybe_none('positions_1') or '[]')

        # Prior edges: gather from all preceding edge pages if configured
        prior_edges = []
        if edge_cfg.get('show_prior_edges', False):
            for prev_idx in range(idx):
                prev_data = player.field_maybe_none(f'edge_data_{prev_idx}') or ''
                if prev_data:
                    prior_edges.extend(json.loads(prev_data))

        pos_by_belief = {p.get('full_label', p['label']): p for p in positions}
        belief_points = [
            {
                "label":       nd["belief"],
                "short_label": nd.get("short_label", ""),
                "x":           pos_by_belief.get(nd["belief"], {}).get('x', 100),
                "y":           pos_by_belief.get(nd["belief"], {}).get('y', 100),
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
            edge_type=edge_cfg,
            edge_index=idx,
            total_edge_types=len(edge_types),
        )

    @staticmethod
    def is_displayed(player):
        from ..config_loader import get_config
        edge_types = get_config()["canvas"]["edges"]
        idx = player.participant.vars.get('_edge_page_counter', 0)
        return (
            idx < len(edge_types)
            and player.num_nodes >= C.NUM_NODES_THRESHOLD
            and player.consent_given
            and player.field_maybe_none('condition') in _CANVAS_CONDITIONS
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        from ..config_loader import get_config
        edge_types = get_config()["canvas"]["edges"]
        idx = player.participant.vars.get('_edge_page_counter', 0)
        edge_id = edge_types[idx]["id"] if idx < len(edge_types) else str(idx)

        # Copy temp data to persistent indexed fields
        pos_tmp = player.field_maybe_none('edge_positions_tmp') or ''
        data_tmp = player.field_maybe_none('edge_data_tmp') or ''
        setattr(player, f'edge_positions_{idx}', pos_tmp)
        setattr(player, f'edge_data_{idx}', data_tmp)
        player.edge_positions_tmp = ''
        player.edge_data_tmp = ''

        stamp(player, f'edge_{edge_id}:submit')
        player.participant.vars['_edge_page_counter'] = idx + 1


class FinalNetworkView(Page):
    """Read-only view of the completed network with configurable questions."""
    form_model = 'player'
    form_fields = ['final_network_responses_json']

    @staticmethod
    def vars_for_template(player):
        from ..config_loader import get_config
        cfg = get_config()
        edge_types = cfg["canvas"]["edges"]
        final_cfg = cfg.get("final_network", {})
        questions = final_cfg.get("questions", [])

        node_data = get_node_display_data(player)

        # Get final positions from the last edge page
        num_edge_types = len(edge_types)
        positions = []
        for idx in range(num_edge_types - 1, -1, -1):
            pos_raw = player.field_maybe_none(f'edge_positions_{idx}') or ''
            if pos_raw:
                positions = json.loads(pos_raw)
                break
        if not positions:
            positions = json.loads(player.field_maybe_none('positions_1') or '[]')

        # Gather all edges from all edge pages
        all_edges = []
        for idx in range(num_edge_types):
            data_raw = player.field_maybe_none(f'edge_data_{idx}') or ''
            if data_raw:
                all_edges.extend(json.loads(data_raw))

        # Build positioned nodes with final coordinates
        pos_by_belief = {p.get('full_label', p['label']): p for p in positions}
        belief_points = [
            {
                "label":       nd["belief"],
                "short_label": nd.get("short_label", ""),
                "x":           pos_by_belief.get(nd["belief"], {}).get('x', 100),
                "y":           pos_by_belief.get(nd["belief"], {}).get('y', 100),
                "radius":      nd["radius"],
                "color":       nd["color"],
            }
            for nd in node_data
        ]

        # Build edge legend from config
        edge_legend = [
            {"label": et["label"], "color": et["color"]}
            for et in edge_types
        ]

        cond = player.field_maybe_none('condition') or ''
        show_transcript = cond in _INTERVIEW_CONDITIONS
        qa_pairs = json.loads(player.conversation_json or "[]") if show_transcript else []

        return dict(
            belief_points=belief_points,
            all_edges_json=json.dumps(all_edges),
            short_labels="true" if cond in _SHORT_LABEL_CONDITIONS else "false",
            edge_legend=edge_legend,
            questions_json=json.dumps(questions),
            transcript=qa_pairs,
            show_transcript=show_transcript,
        )

    @staticmethod
    def is_displayed(player):
        from ..config_loader import get_config
        final_cfg = get_config().get("final_network", {})
        return (
            final_cfg.get("enabled", False)
            and player.num_nodes >= C.NUM_NODES_THRESHOLD
            and player.consent_given
            and player.field_maybe_none('condition') in _CANVAS_CONDITIONS
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, 'final_network:submit')
