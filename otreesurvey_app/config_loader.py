import json
import os
from pathlib import Path

_config_cache = None
_config_path = None


def _resolve_path():
    """Return the path to study_config.json, checking env override first."""
    env_path = os.environ.get("STUDY_CONFIG_PATH")
    if env_path:
        return Path(env_path)
    return Path(__file__).parent / "study_config.json"


def get_config(force_reload=False):
    """Load and cache the study config. Returns a plain dict."""
    global _config_cache, _config_path
    path = _resolve_path()
    if _config_cache is not None and not force_reload and path == _config_path:
        return _config_cache
    with open(path, "r", encoding="utf-8") as f:
        _config_cache = json.load(f)
    _config_path = path
    return _config_cache


def validate_config(config=None):
    """
    Check the config for common problems.
    Returns a list of error strings (empty = valid).
    """
    if config is None:
        config = get_config()

    errors = []

    # -- study section --------------------------------------------------------
    study = config.get("study")
    if not study:
        errors.append("Missing 'study' section.")
    else:
        for key in ("label", "consent_intro", "consent_highlight"):
            if not study.get(key):
                errors.append(f"study.{key} is required.")

    # -- llm section ----------------------------------------------------------
    llm = config.get("llm")
    if not llm:
        errors.append("Missing 'llm' section.")
    else:
        if not llm.get("model"):
            errors.append("llm.model is required.")
        if not llm.get("api_key_env"):
            errors.append("llm.api_key_env is required.")

    # -- interview section ----------------------------------------------------
    interview = config.get("interview")
    if not interview:
        errors.append("Missing 'interview' section.")
    else:
        if not interview.get("opening_question"):
            errors.append("interview.opening_question is required.")
        turns = interview.get("max_turns")
        if not isinstance(turns, int) or turns < 1:
            errors.append("interview.max_turns must be a positive integer.")

    # -- node_extraction section ----------------------------------------------
    extraction = config.get("node_extraction")
    if not extraction:
        errors.append("Missing 'node_extraction' section.")
    else:
        mode = extraction.get("mode")
        if mode not in ("closed", "open"):
            errors.append("node_extraction.mode must be 'closed' or 'open'.")
        if mode == "closed":
            items = extraction.get("items", [])
            if not items:
                errors.append("node_extraction.items is empty (closed mode requires items).")
            ids = [it.get("id") for it in items]
            if len(ids) != len(set(ids)):
                errors.append("node_extraction.items has duplicate ids.")
            for i, item in enumerate(items):
                if not item.get("id"):
                    errors.append(f"node_extraction.items[{i}] missing 'id'.")
                if not item.get("template"):
                    errors.append(f"node_extraction.items[{i}] missing 'template'.")

    # -- canvas section -------------------------------------------------------
    canvas = config.get("canvas")
    if not canvas:
        errors.append("Missing 'canvas' section.")
    else:
        edges = canvas.get("edges", [])
        edge_ids = [e.get("id") for e in edges]
        if len(edge_ids) != len(set(edge_ids)):
            errors.append("canvas.edges has duplicate ids.")

    return errors


def save_config(config, path=None):
    """Validate then write config to disk."""
    errors = validate_config(config)
    if errors:
        raise ValueError(f"Invalid config: {'; '.join(errors)}")
    target = Path(path) if path else _resolve_path()
    with open(target, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    # bust the cache
    global _config_cache
    _config_cache = None
