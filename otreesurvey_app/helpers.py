import json
import re
import time


# -- Node visual encoding ----------------------------------------------------

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


# -- Timing helper ------------------------------------------------------------

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


# -- Template helpers ---------------------------------------------------------

def _strip_prefix(template):
    """Remove 'I [SCALE] that ' prefix."""
    return re.sub(r'^I \[SCALE\] that ', '', template)


# -- Condition sets -----------------------------------------------------------

_INTERVIEW_CONDITIONS   = {'interview', 'interview_short', 'interview_tag'}
_CANVAS_CONDITIONS      = {'direct', 'direct_short', 'direct_v2', 'direct_v2_short',
                           'direct_noprefix', 'color', 'color_tag',
                           'interview', 'interview_short', 'interview_tag', 'demo'}
_SHORT_LABEL_CONDITIONS = {'direct_short', 'interview_short', 'direct_v2_short'}
_V2_CONDITIONS          = {'direct_v2', 'direct_v2_short', 'color', 'color_tag',
                           'interview_tag'}
_NOPREFIX_CONDITIONS    = {'direct_noprefix', 'color', 'color_tag', 'interview_tag', 'demo'}
_TAG_CONDITIONS         = {'color_tag', 'interview_tag'}


# -- Demo data ----------------------------------------------------------------

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
