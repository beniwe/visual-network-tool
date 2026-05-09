import json
import asyncio
from datetime import datetime
from otree.api import Page

from ..helpers import stamp, _get_async_client, _INTERVIEW_CONDITIONS
from ..constants import C


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
            from ..llm_prompts import INTERVIEW_OPENING_QUESTION
            conversation.append({
                "question": INTERVIEW_OPENING_QUESTION,
                "answer": "",
                "time_sent": datetime.utcnow().isoformat(),
                "time_received": None
            })
            player.conversation_json = json.dumps(conversation)

        return dict(
            conversation=conversation,
            current_turn=player.participant.vars["interview_turns"],
            max_turns=C.MAX_TURNS,
            progress_percentage=int(100 * player.participant.vars["interview_turns"] / C.MAX_TURNS)
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

        if current_turn < C.MAX_TURNS:
            qa_history = [
                UserAnswer(question=entry["question"], answer=entry["answer"])
                for entry in conversation if entry.get("answer") and entry["answer"].strip()
            ]
            llm_turn = generate_conversational_question(qa_history, C.MAX_TURNS)

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
            and player.participant.vars.get("interview_turns", 1) <= C.MAX_TURNS
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
        from ..llm_prompts import make_node_prompt, enrich_detected_stances

        async def call_and_parse(prompt, retries=3, delay=3):
            for attempt in range(retries):
                try:
                    completion = await _get_async_client().chat.completions.create(
                        model="gpt-4.1-2025-04-14",
                        messages=[{"role": "user", "content": prompt}],
                        stream=False,
                    )
                    raw = completion.choices[0].message.content.strip()

                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        cleaned = raw.replace("```json", "").replace("```", "").strip()
                        parsed = json.loads(cleaned)

                    if isinstance(parsed, dict) and "detected" in parsed:
                        return parsed["detected"]
                    elif isinstance(parsed, dict) and "results" in parsed:
                        return parsed["results"]
                    elif isinstance(parsed, list):
                        return parsed
                    else:
                        raise ValueError("Response not in expected JSON list format.")

                except Exception as e:
                    print(f"Attempt {attempt+1} failed:", e)
                    if attempt < retries - 1:
                        await asyncio.sleep(delay)
                    else:
                        raise

        try:
            conversation = json.loads(player.conversation_json or "[]")
            qa = {
                e["question"]: e["answer"]
                for e in conversation
                if e.get("answer") and str(e["answer"]).strip()
            }

            prompt = make_node_prompt(qa)
            player.prompt_used = prompt

            llm_nodes_list = await call_and_parse(prompt, retries=3, delay=2)
            llm_nodes_list = enrich_detected_stances(llm_nodes_list or [])

            player.llm_result = json.dumps({"detected": llm_nodes_list}, indent=2)
            player.generated_nodes = json.dumps(llm_nodes_list)
            player.num_nodes = len(llm_nodes_list)

            yield {player.id_in_group: {"done": True}}

        except Exception as e:
            print("LLM permanently failed:", e)
            yield {player.id_in_group: {"done": False}}

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, "conv_feedback:submit")
