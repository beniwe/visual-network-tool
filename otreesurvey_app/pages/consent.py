import json
from otree.api import Page

from ..helpers import stamp, _DEMO_NODES, _INTERVIEW_CONDITIONS
from ..constants import C


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
        pid = participant.label or participant.vars.get('PROLIFIC_PID') or ''
        player.prolific_pid = pid
        player.prolific_study_id = (
            participant.vars.get('STUDY_ID')
            or participant.vars.get('study_id')
            or ''
        )
        player.prolific_session_id = (
            participant.vars.get('SESSION_ID')
            or participant.vars.get('session_id')
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
            player.final_nodes = json.dumps(_DEMO_NODES)
            player.num_nodes = len(_DEMO_NODES)


class LinkCompletion(Page):

    @staticmethod
    def is_displayed(player):
        return (
            player.consent_given
            and player.num_nodes >= C.NUM_NODES_THRESHOLD
        )

    @staticmethod
    def vars_for_template(player):
        player.exit_status = 'completed'
        player.last_page = 'LinkCompletion'
        player.exit_url = player.session.config['completionlink']
        stamp(player, 'exit:completed')
        return {}

    @staticmethod
    def js_vars(player):
        return dict(url=player.session.config['completionlink'])


class LinkFailedChecks(Page):

    @staticmethod
    def is_displayed(player):
        return (
            player.consent_given
            and player.num_nodes < C.NUM_NODES_THRESHOLD
        )

    @staticmethod
    def vars_for_template(player):
        player.exit_status = 'failed_checks'
        player.last_page = 'LinkFailedChecks'
        player.exit_url = player.session.config.get('returnlink', player.session.config['completionlink'])
        stamp(player, 'exit:failed_checks')
        return {}

    @staticmethod
    def js_vars(player):
        return dict(url=player.session.config.get('returnlink', player.session.config['completionlink']))


class LinkNoConsent(Page):

    @staticmethod
    def is_displayed(player):
        return not player.consent_given

    @staticmethod
    def vars_for_template(player):
        player.exit_status = 'no_consent'
        player.last_page = 'LinkNoConsent'
        player.exit_url = player.session.config['noconsentlink']
        stamp(player, 'exit:no_consent')
        return {}

    @staticmethod
    def js_vars(player):
        return dict(url=player.session.config['noconsentlink'])
