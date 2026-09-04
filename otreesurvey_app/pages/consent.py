import json
from otree.api import Page

from ..helpers import stamp, get_demo_nodes, get_min_nodes, _INTERVIEW_CONDITIONS


def _exit_url(player, kind):
    """The link a participant is redirected to on exit. Read from the study
    config (what the researcher edits), falling back to the session config /
    env links. Screen-outs fall back to the completion link when unset."""
    from ..config_loader import get_config
    study = get_config().get("study", {})
    cfg = player.session.config
    if kind == "completion":
        return study.get("completion_url") or cfg["completionlink"]
    if kind == "screenout":
        return (
            study.get("screenout_url")
            or study.get("completion_url")
            or cfg.get("returnlink", cfg["completionlink"])
        )
    return study.get("no_consent_url") or cfg["noconsentlink"]


class Consent(Page):
    form_model = 'player'
    form_fields = ['consent_given']

    @staticmethod
    def vars_for_template(player):
        from ..config_loader import get_config
        cfg = get_config()["study"]
        stamp(player, 'consent:render')
        return dict(
            consent_intro=cfg["consent_intro"],
            consent_highlight=cfg["consent_highlight"],
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        participant = player.participant
        pid = (
            participant.label
            or participant.vars.get('PROLIFIC_PID')
            or participant.vars.get('participantId')
            or ''
        )
        player.prolific_pid = pid
        player.prolific_study_id = (
            participant.vars.get('STUDY_ID')
            or participant.vars.get('study_id')
            or participant.vars.get('projectId')
            or ''
        )
        player.prolific_session_id = (
            participant.vars.get('SESSION_ID')
            or participant.vars.get('session_id')
            or participant.vars.get('assignmentId')
            or ''
        )
        stamp(player, 'consent:submit')

    def error_message(self, values):
        if values['consent_given'] is None:
            return "Please indicate whether you consent to participate."


class ConditionSelector(Page):
    form_model = 'player'
    form_fields = ['condition']

    @staticmethod
    def is_displayed(player):
        return player.consent_given

    @staticmethod
    def before_next_page(player, timeout_happened):
        if not player.field_maybe_none('condition'):
            player.condition = 'color_tag'
        if player.field_maybe_none('condition') == 'demo':
            demo = get_demo_nodes()
            player.final_nodes = json.dumps(demo)
            player.num_nodes = len(demo)


class LinkCompletion(Page):

    @staticmethod
    def is_displayed(player):
        return (
            player.consent_given
            and player.num_nodes >= get_min_nodes()
        )

    @staticmethod
    def vars_for_template(player):
        player.exit_status = 'completed'
        player.last_page = 'LinkCompletion'
        player.exit_url = _exit_url(player, 'completion')
        stamp(player, 'exit:completed')
        return {}

    @staticmethod
    def js_vars(player):
        return dict(url=_exit_url(player, 'completion'))


class LinkFailedChecks(Page):

    @staticmethod
    def is_displayed(player):
        return (
            player.consent_given
            and player.num_nodes < get_min_nodes()
        )

    @staticmethod
    def vars_for_template(player):
        player.exit_status = 'failed_checks'
        player.last_page = 'LinkFailedChecks'
        player.exit_url = _exit_url(player, 'screenout')
        stamp(player, 'exit:failed_checks')
        return {}

    @staticmethod
    def js_vars(player):
        return dict(url=_exit_url(player, 'screenout'))


class LinkNoConsent(Page):

    @staticmethod
    def is_displayed(player):
        return not player.consent_given

    @staticmethod
    def vars_for_template(player):
        player.exit_status = 'no_consent'
        player.last_page = 'LinkNoConsent'
        player.exit_url = _exit_url(player, 'no_consent')
        stamp(player, 'exit:no_consent')
        return {}

    @staticmethod
    def js_vars(player):
        return dict(url=_exit_url(player, 'no_consent'))
