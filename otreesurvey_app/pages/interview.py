import json
from datetime import datetime
from otree.api import Page

from ..helpers import stamp, _INTERVIEW_CONDITIONS


def _max_turns():
    from ..config_loader import get_config
    return get_config()["interview"].get("max_turns", 8)


class Information(Page):
    form_model = 'player'

    @staticmethod
    def is_displayed(player):
        return player.consent_given and player.field_maybe_none('condition') in _INTERVIEW_CONDITIONS

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, 'information:submit')


class InterviewMain(Page):
    form_model = 'player'
    form_fields = ['current_answer', 'voice_answer']

    @staticmethod
    def vars_for_template(player):
        conversation = json.loads(player.conversation_json)

        if "interview_turns" not in player.participant.vars:
            player.participant.vars["interview_turns"] = 1

        if not conversation:
            from ..llm_prompts import get_opening_question
            conversation.append({
                "question": get_opening_question(),
                "answer": "",
                "time_sent": datetime.utcnow().isoformat(),
                "time_received": None
            })
            player.conversation_json = json.dumps(conversation)

        return dict(
            conversation=conversation,
            current_turn=player.participant.vars["interview_turns"],
            max_turns=_max_turns(),
            progress_percentage=int(100 * player.participant.vars["interview_turns"] / _max_turns())
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        from ..llm_prompts import UserAnswer, generate_conversational_question

        conversation = json.loads(player.conversation_json)

        response = player.current_answer.strip() if player.current_answer else player.voice_answer.strip()
        input_mode = "text" if player.current_answer.strip() else "voice" if player.voice_answer.strip() else "unknown"

        if response:
            conversation[-1]["answer"] = response
            conversation[-1]["input_mode"] = input_mode
            conversation[-1]["time_received"] = datetime.utcnow().isoformat()
        else:
            conversation[-1]["answer"] = "[No response detected]"
            conversation[-1]["input_mode"] = "unknown"
            conversation[-1]["time_received"] = datetime.utcnow().isoformat()

        current_turn = player.participant.vars["interview_turns"]

        if current_turn < _max_turns():
            qa_history = [
                UserAnswer(question=entry["question"], answer=entry["answer"])
                for entry in conversation if entry.get("answer") and entry["answer"].strip()
            ]
            llm_turn = generate_conversational_question(qa_history, _max_turns())

            conversation.append({
                "question": llm_turn.interviewer_utterance,
                "answer": "",
                "time_sent": datetime.utcnow().isoformat()
            })

        player.conversation_json = json.dumps(conversation)
        player.participant.vars["interview_turns"] = current_turn + 1
        stamp(player, 'interviewmain:submit')

    @staticmethod
    def is_displayed(player):
        return (
            player.consent_given
            and player.field_maybe_none('condition') in _INTERVIEW_CONDITIONS
            and player.participant.vars.get("interview_turns", 1) <= _max_turns()
        )


class ConversationFeedback(Page):
    form_model = 'player'
    form_fields = [
        'conv_overall_0_100', 'conv_overall_cat',
        'conv_relevant_0_100', 'conv_relevant_cat',
        'conv_easy_chat_0_100', 'conv_easy_chat_cat',
        'conv_comfort_0_100', 'conv_comfort_cat',
        'conv_creepy_0_100', 'conv_creepy_cat',
        'conv_open_feedback',
    ]

    @staticmethod
    def is_displayed(player):
        return player.consent_given and player.field_maybe_none('condition') in _INTERVIEW_CONDITIONS

    @staticmethod
    async def live_method(player, data):
        from ..llm.node_extraction import async_extract_nodes

        try:
            conversation = json.loads(player.conversation_json or "[]")
            qa = {
                e["question"]: e["answer"]
                for e in conversation
                if e.get("answer") and str(e["answer"]).strip()
            }

            nodes_list, prompt = await async_extract_nodes(qa)
            player.prompt_used = prompt

            player.llm_result = json.dumps({"detected": nodes_list}, indent=2)
            player.generated_nodes = json.dumps(nodes_list)
            player.num_nodes = len(nodes_list)

            yield {player.id_in_group: {"done": True}}

        except Exception as e:
            print("LLM permanently failed:", e)
            yield {player.id_in_group: {"done": False}}

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, "conv_feedback:submit")
