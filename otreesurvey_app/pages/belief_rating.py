import json
import random
from otree.api import Page

from ..helpers import (
    stamp, _strip_prefix,
    _CANVAS_CONDITIONS, _INTERVIEW_CONDITIONS,
    _V2_CONDITIONS, _NOPREFIX_CONDITIONS, _TAG_CONDITIONS,
)


class DynamicBeliefRating(Page):
    form_model = 'player'
    form_fields = ['dynamic_belief_ratings_json']

    @staticmethod
    def vars_for_template(player):
        from ..dynamic_items import DYNAMIC_ITEMS
        condition = player.field_maybe_none('condition')

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

        rnd = random.Random(player.participant.code)
        rnd.shuffle(source)

        use_v2 = condition in _V2_CONDITIONS
        items = [
            {
                "index":     i,
                "id":        item["id"],
                "template":  item.get("template_v2", item["template"]) if use_v2 else item["template"],
                "labels":    item["labels"],
                "anchor_lo": item["anchor_lo"],
                "anchor_hi": item["anchor_hi"],
            }
            for i, item in enumerate(source)
        ]
        return dict(items_json=json.dumps(items), num_items=len(items),
                    show_importance="true", scale_max=6, start_val=1)

    @staticmethod
    def is_displayed(player):
        cond = player.field_maybe_none('condition')
        return player.consent_given and cond in _CANVAS_CONDITIONS and cond != 'demo'

    @staticmethod
    def before_next_page(player, timeout_happened):
        raw = player.field_maybe_none('dynamic_belief_ratings_json') or '[]'
        try:
            ratings = json.loads(raw)
        except Exception:
            ratings = []

        from ..dynamic_items import DYNAMIC_ITEMS
        cond = player.field_maybe_none('condition') or ''
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
            })
        player.final_nodes = json.dumps(final)
        player.num_nodes = len(final)
        stamp(player, 'dynamic_belief_rating:submit')
