"""
Clean CSV export for the belief-network study.

oTree's built-in "all data" export dumps every field with cryptic column
names. This produces a tidy one-row-per-participant table with readable
columns: identity, condition, the network as compact JSON (statements with
their ratings and centrality, and the edges), feedback, and outcome.

The row-building here is plain and takes dicts, so it can be tested without
the database. `custom_export` in __init__.py adapts player objects to it.
"""

import base64
import io
import json
import zipfile


def build_image_zip(images):
    """images: list of (filename, data_url). Returns zip bytes of the PNGs."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data_url in images:
            png = _decode_data_url(data_url)
            if png:
                zf.writestr(name, png)
    return buf.getvalue()


def _decode_data_url(data_url):
    if not data_url or "," not in data_url:
        return None
    _, b64 = data_url.split(",", 1)
    try:
        return base64.b64decode(b64)
    except (ValueError, TypeError):
        return None


HEADER = [
    "participant_code", "participant_label", "session_code",
    "condition", "consent_given",
    "prolific_pid", "prolific_study_id", "prolific_session_id",
    "num_nodes", "num_edges",
    "top_degree_label", "top_degree_value",
    "top_eigenvector_label", "top_eigenvector_value",
    "conv_overall_0_100", "conv_relevant_0_100", "conv_easy_chat_0_100",
    "conv_comfort_0_100", "conv_creepy_0_100", "conv_open_feedback",
    "canvas_difficulty_placement", "canvas_clarity_statements",
    "canvas_usability_comment", "final_feedback",
    "exit_status",
    "statements_json", "edges_json", "final_network_responses_json",
]


def _loads(raw, default):
    try:
        value = json.loads(raw) if raw else default
        return value if value is not None else default
    except (ValueError, TypeError):
        return default


def clean_edges(edge_data_fields):
    """Merge the per-page edge fields, drop the duplicates carried forward by
    the prior-edge merge, and return tidy edge dicts."""
    edges = []
    seen = set()
    for raw in edge_data_fields:
        for edge in _loads(raw, []):
            a = edge.get("stance_1")
            b = edge.get("stance_2")
            if not a or not b:
                continue
            key = (frozenset((a, b)), edge.get("polarity"))
            if key in seen:
                continue
            seen.add(key)
            edges.append({
                "from": a,
                "to": b,
                "type": edge.get("polarity"),
                "strength": edge.get("strength"),
            })
    return edges


def clean_statements(final_nodes_raw, centrality):
    nodes = _loads(final_nodes_raw, [])
    cent_by_label = {n.get("label"): n for n in centrality.get("nodes", [])}
    result = []
    for node in nodes:
        label = node.get("dynamic_sentence_simple") or node.get("belief", "")
        cent = cent_by_label.get(label, {})
        result.append({
            "statement": label,
            "short_label": node.get("short_label", ""),
            "agreement": node.get("rating"),
            "importance": node.get("relevance"),
            "degree": cent.get("degree"),
            "eigenvector": cent.get("eigenvector"),
        })
    return result


def build_row(p):
    centrality = _loads(p.get("centrality_json"), {})
    statements = clean_statements(p.get("final_nodes"), centrality)
    edges = clean_edges(p.get("edge_data_fields", []))
    top_deg = centrality.get("top_degree") or {}
    top_eig = centrality.get("top_eigenvector") or {}

    return [
        p.get("participant_code", ""),
        p.get("participant_label", ""),
        p.get("session_code", ""),
        p.get("condition", ""),
        p.get("consent_given", ""),
        p.get("prolific_pid", ""),
        p.get("prolific_study_id", ""),
        p.get("prolific_session_id", ""),
        len(statements),
        len(edges),
        top_deg.get("label", ""),
        top_deg.get("value", ""),
        top_eig.get("label", ""),
        top_eig.get("value", ""),
        p.get("conv_overall_0_100"),
        p.get("conv_relevant_0_100"),
        p.get("conv_easy_chat_0_100"),
        p.get("conv_comfort_0_100"),
        p.get("conv_creepy_0_100"),
        p.get("conv_open_feedback", ""),
        p.get("canvas_difficulty_placement"),
        p.get("canvas_clarity_statements"),
        p.get("canvas_usability_comment", ""),
        p.get("final_feedback", ""),
        p.get("exit_status", ""),
        json.dumps(statements, ensure_ascii=False),
        json.dumps(edges, ensure_ascii=False),
        p.get("final_network_responses_json", ""),
    ]
