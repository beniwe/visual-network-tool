import json
import random
from otree.api import Page

from ..helpers import (
    stamp, _strip_prefix,
    _CANVAS_CONDITIONS, _INTERVIEW_CONDITIONS,
    _V2_CONDITIONS, _NOPREFIX_CONDITIONS, _TAG_CONDITIONS,
)
from ..config_loader import get_config


class DynamicBeliefRating(Page):
    form_model = 'player'
    form_fields = ['dynamic_belief_ratings_json']

    @staticmethod
    def vars_for_template(player):
        cfg = get_config()
        extraction_mode = cfg["node_extraction"].get("mode", "closed")
        dimensions = cfg["node_rating"]["dimensions"]
        condition = player.field_maybe_none('condition')

        if extraction_mode == "open" and condition in _INTERVIEW_CONDITIONS:
            # Open mode: use the extracted stances directly
            generated = json.loads(player.generated_nodes or '[]')
            source = [
                {
                    "id":        n.get("stance_id", f"open_{i}"),
                    "template":  n.get("statement", n.get("label", "")),
                    "labels":    {},
                    "anchor_lo": "",
                    "anchor_hi": "",
                    "short_label": n.get("short_label", ""),
                }
                for i, n in enumerate(generated)
            ]
            use_scale_token = False
        else:
            # Closed mode: use predefined items
            from ..dynamic_items import DYNAMIC_ITEMS

            if condition in _INTERVIEW_CONDITIONS:
                detected_ids = {
                    n.get('stance_id')
                    for n in json.loads(player.generated_nodes or '[]')
                    if n.get('stance_id')
                }
                source = [item for item in DYNAMIC_ITEMS if item['id'] in detected_ids]
                if not source:
                    source = list(DYNAMIC_ITEMS)
            else:
                source = list(DYNAMIC_ITEMS)

            use_v2 = condition in _V2_CONDITIONS
            source = [
                {
                    "id":        item["id"],
                    "template":  item.get("template_v2", item["template"]) if use_v2 else item["template"],
                    "labels":    item["labels"],
                    "anchor_lo": item["anchor_lo"],
                    "anchor_hi": item["anchor_hi"],
                    "short_label": item.get("short_label", ""),
                }
                for item in source
            ]
            use_scale_token = True

        rnd = random.Random(player.participant.code)
        rnd.shuffle(source)

        items = [dict(index=i, **s) for i, s in enumerate(source)]

        # Primary dimension (agreement) — drives the [SCALE] token
        primary_dim = dimensions[0] if dimensions else {}
        extra_dims = dimensions[1:] if len(dimensions) > 1 else []

        return dict(
            items_json=json.dumps(items),
            num_items=len(items),
            use_scale_token="true" if use_scale_token else "false",
            scale_min=primary_dim.get("scale_min", 1),
            scale_max=primary_dim.get("scale_max", 6),
            start_val=primary_dim.get("scale_min", 1),
            primary_anchor_lo=primary_dim.get("anchor_lo", ""),
            primary_anchor_hi=primary_dim.get("anchor_hi", ""),
            extra_dims_json=json.dumps(extra_dims),
        )

    @staticmethod
    def is_displayed(player):
        cond = player.field_maybe_none('condition')
        return player.consent_given and cond in _CANVAS_CONDITIONS and cond != 'demo'

    @staticmethod
    def before_next_page(player, timeout_happened):
        cfg = get_config()
        extraction_mode = cfg["node_extraction"].get("mode", "closed")
        dimensions = cfg["node_rating"]["dimensions"]

        raw = player.field_maybe_none('dynamic_belief_ratings_json') or '[]'
        try:
            ratings = json.loads(raw)
        except Exception:
            ratings = []

        cond = player.field_maybe_none('condition') or ''

        if extraction_mode == "open" and cond in _INTERVIEW_CONDITIONS:
            # Open mode: generated nodes already have statements
            generated = json.loads(player.generated_nodes or '[]')
            gen_lookup = {n.get("stance_id", f"open_{i}"): n for i, n in enumerate(generated)}

            final = []
            for entry in ratings:
                item_id = entry.get("id", "")
                gen = gen_lookup.get(item_id, {})
                v = entry.get("value", 0)
                simple_word = "disagree" if v <= 3 else "agree"
                statement = gen.get("statement", gen.get("label", ""))

                final.append({
                    "belief":                  simple_word,
                    "rating":                  v,
                    "relevance":               entry.get("importance", 4),
                    "dynamic_id":              item_id,
                    "dynamic_val":             v,
                    "dynamic_importance":      entry.get("importance"),
                    "dynamic_sentence_full":   entry.get("sentence", ""),
                    "dynamic_sentence_simple": f"{statement}: {simple_word}" if statement else simple_word,
                    "short_label":             gen.get("short_label", statement[:30] if statement else ""),
                    "dimensions":              entry.get("dimensions", {}),
                })
        else:
            # Closed mode: use predefined items for sentence building
            from ..dynamic_items import DYNAMIC_ITEMS
            use_v2 = cond in _V2_CONDITIONS
            use_noprefix = cond in _NOPREFIX_CONDITIONS
            use_tag = cond in _TAG_CONDITIONS
            item_lookup = {item["id"]: item for item in DYNAMIC_ITEMS}
            template_lookup = {
                item["id"]: item.get("template_v2", item["template"]) if use_v2 else item["template"]
                for item in DYNAMIC_ITEMS
            }

            final = []
            for entry in ratings:
                v = entry.get("value", 0)
                simple_word = "disagree" if v <= 3 else "agree"
                tmpl = template_lookup.get(entry.get("id", ""), "")
                if use_noprefix:
                    content = _strip_prefix(tmpl) if tmpl else ""
                    simple_sentence = f"{content}: {simple_word}" if use_tag else content
                else:
                    simple_sentence = tmpl.replace("[SCALE]", simple_word) if tmpl else simple_word
                item_meta = item_lookup.get(entry.get("id", ""), {})
                final.append({
                    "belief":                  simple_word,
                    "rating":                  v,
                    "relevance":               entry.get("importance", 4),
                    "dynamic_id":              entry.get("id", ""),
                    "dynamic_val":             v,
                    "dynamic_importance":      entry.get("importance"),
                    "dynamic_sentence_full":   entry.get("sentence", ""),
                    "dynamic_sentence_simple": simple_sentence,
                    "short_label":             item_meta.get("short_label", ""),
                    "dimensions":              entry.get("dimensions", {}),
                })

        player.final_nodes = json.dumps(final)
        player.num_nodes = len(final)
        stamp(player, 'dynamic_belief_rating:submit')
