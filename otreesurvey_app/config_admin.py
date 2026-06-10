import json

from starlette.concurrency import run_in_threadpool
from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from otree import settings
from otree.common import AUTH_COOKIE_NAME, AUTH_COOKIE_VALUE

from .config_loader import get_config, save_config, validate_config


def _is_logged_in(request):
    return request.session.get(AUTH_COOKIE_NAME) == AUTH_COOKIE_VALUE


def _needs_auth():
    return settings.AUTH_LEVEL in ('STUDY', 'DEMO')


class ConfigAPIEndpoint(HTTPEndpoint):

    async def dispatch(self):
        request = Request(self.scope, receive=self.receive)
        if _needs_auth() and not _is_logged_in(request):
            response = Response('Unauthorized', status_code=401)
            await response(self.scope, self.receive, self.send)
            return

        if request.method == 'GET':
            response = await run_in_threadpool(self._handle_get)
        elif request.method == 'POST':
            body = await request.body()
            response = await run_in_threadpool(self._handle_post, body)
        else:
            response = Response('Method not allowed', status_code=405)

        await response(self.scope, self.receive, self.send)

    def _handle_get(self):
        config = get_config(force_reload=True)
        return JSONResponse(config)

    def _handle_post(self, body):
        try:
            config = json.loads(body)
        except json.JSONDecodeError as e:
            return JSONResponse({'errors': [f'Invalid JSON: {e}']}, status_code=400)

        errors = validate_config(config)
        if errors:
            return JSONResponse({'errors': errors}, status_code=400)

        try:
            save_config(config)
        except Exception as e:
            return JSONResponse({'errors': [str(e)]}, status_code=500)

        return JSONResponse({'ok': True})
