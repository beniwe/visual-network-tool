"""
Thin wrapper — reads items from study_config.json.

DYNAMIC_ITEMS is used by DynamicBeliefRating and canvas pages.
The JSON stores label keys as strings ("1", "2", ...); this module
converts them to int keys so existing templates keep working.
"""

from .config_loader import get_config


def _load_items():
    items = get_config()["node_extraction"]["items"]
    for item in items:
        if "labels" in item and isinstance(item["labels"], dict):
            item["labels"] = {int(k): v for k, v in item["labels"].items()}
    return items


DYNAMIC_ITEMS = _load_items()
