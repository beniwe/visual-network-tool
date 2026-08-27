from os import environ

SESSION_CONFIGS = [
    dict(
        name='SURVEY',
        app_sequence=['otreesurvey_app'],
        num_demo_participants=1,
        completionlink=environ.get('PROLIFIC_COMPLETION_URL', 'https://app.prolific.com/submissions/complete?cc=C1NZTO0K'),
        noconsentlink=environ.get('PROLIFIC_NOCONSENT_URL', 'https://app.prolific.com/submissions/complete?cc=C17XO1J2'),
    ),
]

ROOMS = [
    dict(
        name='meat_beliefs_20260413',
        display_name='meat_beliefs_20260413'
    )
]

SESSION_CONFIG_DEFAULTS = dict(
    real_world_currency_per_point=1.00, participation_fee=0.00, doc=""
)

PARTICIPANT_FIELDS = ['link_code'] # TKTK new stuff here. 
SESSION_FIELDS = []

LANGUAGE_CODE = 'en'

# e.g. EUR, GBP, CNY, JPY
REAL_WORLD_CURRENCY_CODE = 'USD'
USE_POINTS = True

ADMIN_USERNAME = 'admin'

# for security, best to set admin password in an environment variable
ADMIN_PASSWORD = environ.get('OTREE_ADMIN_PASSWORD')

# Lock the admin down in production so survey participants (who reach the study
# only through their own participant links) cannot open the admin, the config
# editor, or the data exports. STUDY protects everything; DEMO would leave the
# session data views open, so we default to STUDY. Set OTREE_AUTH_LEVEL to
# override (e.g. 'DEMO', or '' to disable).
_in_production = environ.get('OTREE_PRODUCTION') not in (None, '', '0')
AUTH_LEVEL = environ.get('OTREE_AUTH_LEVEL') or ('STUDY' if _in_production else None)

DEMO_PAGE_INTRO_HTML = """ """

SECRET_KEY = environ.get('OTREE_SECRET_KEY', 'changeme')
