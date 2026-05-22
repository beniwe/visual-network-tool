import json
import re
import time


# -- Node visual encoding ----------------------------------------------------

def _get_canvas_config():
    from .config_loader import get_config
    return get_config()["canvas"]["nodes"]


def _get_dimension_value(node, dim_id):
    """Extract a dimension value from a final_nodes entry.

    Checks the generic ``dimensions`` dict first, then falls back to the
    legacy flat keys (``rating`` for agreement, ``relevance`` /
    ``dynamic_importance`` for importance).
    """
    if not dim_id:
        return None
    dims = node.get("dimensions", {})
    if dim_id in dims:
        return dims[dim_id]
    if dim_id == "agreement":
        return node.get("rating")
    if dim_id == "importance":
        return node.get("relevance") or node.get("dynamic_importance")
    return None


def _node_color(value):
    """Determine node color from a rating value using the canvas config."""
    canvas = _get_canvas_config()
    color_map = canvas.get("color_map", {})
    threshold = color_map.get("threshold", 3.5)
    low = color_map.get("low_color", "#d73027")
    high = color_map.get("high_color", "#006d2c")
    if value is None:
        return high
    return low if float(value) <= threshold else high


def _node_radius(value, dim_id=None):
    """Compute node radius via linear interpolation over the dimension scale.

    If *dim_id* is ``None`` the size dimension from the canvas config is
    used.  When no size dimension is configured (or the value is missing)
    the fixed radius from config is returned.
    """
    from .config_loader import get_config
    cfg = get_config()
    canvas = cfg["canvas"]["nodes"]
    dim_id = dim_id or canvas.get("size_dimension")
    if not dim_id or value is None:
        return canvas.get("fixed_radius", 14)
    dim_lookup = {d["id"]: d for d in cfg["node_rating"]["dimensions"]}
    dim_cfg = dim_lookup.get(dim_id, {})
    scale_min = dim_cfg.get("scale_min", 1)
    scale_max = dim_cfg.get("scale_max", 7)
    size_range = canvas.get("size_range", [10, 22])
    t = (float(value) - scale_min) / max(1, scale_max - scale_min)
    t = max(0.0, min(1.0, t))
    return round(size_range[0] + t * (size_range[1] - size_range[0]))


def get_node_display_data(player):
    """Return [{belief, short_label, radius, color}, ...] for every node in final_nodes."""
    canvas = _get_canvas_config()
    color_dim = canvas.get("color_dimension", "agreement")
    size_dim = canvas.get("size_dimension")

    nodes = json.loads(player.final_nodes or '[]')
    result = []
    for n in nodes:
        color_val = _get_dimension_value(n, color_dim)
        if size_dim:
            size_val = _get_dimension_value(n, size_dim)
            radius = _node_radius(size_val, size_dim)
        else:
            radius = canvas.get("fixed_radius", 14)
        result.append({
            "belief":      n.get("dynamic_sentence_simple") or n.get("belief", ""),
            "short_label": n.get("short_label", ""),
            "radius":      radius,
            "color":       _node_color(color_val),
        })
    return result


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

def get_demo_nodes():
    """Load demo nodes from the study config."""
    from .config_loader import get_config
    return get_config().get("demo_nodes", [])
