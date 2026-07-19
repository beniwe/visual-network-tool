"""
Thin wrapper — reads items from study_config.json.

Used by DynamicBeliefRating. The JSON stores label keys as strings
("1", "2", ...); this module converts them to int keys so existing
templates keep working.

Read through get_dynamic_items() rather than caching the result, so
config changes saved from the admin editor take effect without a
server restart.
"""

from .config_loader import get_config


def get_dynamic_items():
    items = get_config()["node_extraction"]["items"]
    result = []
    for item in items:
        labels = item.get("labels")
        if isinstance(labels, dict):
            item = dict(item, labels={int(k): v for k, v in labels.items()})
        result.append(item)
    return result
