import json
import os

from starlette.concurrency import run_in_threadpool
from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

from otree import settings
from otree.common import AUTH_COOKIE_NAME, AUTH_COOKIE_VALUE

from .config_loader import get_config, save_config, validate_config

_EDITOR_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '_static', 'config_editor.html'
)

_MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
_ALLOWED_VIDEO_EXTS = {'.mp4', '.webm', '.ogg', '.mov', '.m4v'}
_MAX_VIDEO_BYTES = 50 * 1024 * 1024


def _is_logged_in(request):
    return request.session.get(AUTH_COOKIE_NAME) == AUTH_COOKIE_VALUE


def _needs_auth():
    return settings.AUTH_LEVEL in ('STUDY', 'DEMO')


def _read_editor_html():
    with open(_EDITOR_PATH, encoding='utf-8') as f:
        return f.read()


class ConfigPageEndpoint(HTTPEndpoint):

    async def dispatch(self):
        request = Request(self.scope, receive=self.receive)
        if _needs_auth() and not _is_logged_in(request):
            from starlette.responses import RedirectResponse
            response = RedirectResponse('/login')
            await response(self.scope, self.receive, self.send)
            return

        html = await run_in_threadpool(_read_editor_html)
        response = HTMLResponse(html)
        await response(self.scope, self.receive, self.send)


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


class NetworkImageExportEndpoint(HTTPEndpoint):

    async def dispatch(self):
        request = Request(self.scope, receive=self.receive)
        if _needs_auth() and not _is_logged_in(request):
            response = Response('Unauthorized', status_code=401)
            await response(self.scope, self.receive, self.send)
            return

        data = await run_in_threadpool(self._build_zip)
        response = Response(
            data,
            media_type='application/zip',
            headers={'Content-Disposition': 'attachment; filename="network_images.zip"'},
        )
        await response(self.scope, self.receive, self.send)

    def _build_zip(self):
        from otree.common import get_models_module
        from otree.database import session_scope, dbq
        from .data_export import build_image_zip

        Player = get_models_module('otreesurvey_app').Player
        images = []
        with session_scope():
            for player in dbq(Player):
                player._is_frozen = False
                img = player.field_maybe_none('network_image')
                if img:
                    images.append((f'{player.participant.code}.png', img))
        return build_image_zip(images)


class VideoUploadEndpoint(HTTPEndpoint):

    async def dispatch(self):
        request = Request(self.scope, receive=self.receive)
        if _needs_auth() and not _is_logged_in(request):
            await self._send(Response('Unauthorized', status_code=401))
            return

        try:
            form = await request.form()
        except Exception:
            await self._send(JSONResponse({'error': 'Invalid upload.'}, status_code=400))
            return

        upload = form.get('video')
        if upload is None or not getattr(upload, 'filename', ''):
            await self._send(JSONResponse({'error': 'No file provided.'}, status_code=400))
            return

        ext = os.path.splitext(upload.filename)[1].lower()
        if ext not in _ALLOWED_VIDEO_EXTS:
            await self._send(JSONResponse(
                {'error': f'Unsupported file type "{ext}". Use mp4, webm, ogg or mov.'},
                status_code=400,
            ))
            return

        data = await upload.read()
        if len(data) > _MAX_VIDEO_BYTES:
            await self._send(JSONResponse(
                {'error': 'File too large (max 50 MB).'}, status_code=400,
            ))
            return

        url = await run_in_threadpool(self._save, data, ext)
        await self._send(JSONResponse({'ok': True, 'url': url}))

    async def _send(self, response):
        await response(self.scope, self.receive, self.send)

    def _save(self, data, ext):
        os.makedirs(_MEDIA_DIR, exist_ok=True)
        # keep only one intro video
        for name in os.listdir(_MEDIA_DIR):
            if name.startswith('intro_video.'):
                try:
                    os.remove(os.path.join(_MEDIA_DIR, name))
                except OSError:
                    pass
        filename = 'intro_video' + ext
        with open(os.path.join(_MEDIA_DIR, filename), 'wb') as fp:
            fp.write(data)
        return '/media/' + filename


class MediaEndpoint(HTTPEndpoint):
    """Serves uploaded media (e.g. the intro video). Public - participants need it."""

    async def dispatch(self):
        from starlette.responses import FileResponse
        request = Request(self.scope, receive=self.receive)
        name = os.path.basename(request.path_params.get('filename', ''))
        path = os.path.join(_MEDIA_DIR, name)
        if name and os.path.isfile(path):
            response = FileResponse(path)
        else:
            response = Response('Not found', status_code=404)
        await response(self.scope, self.receive, self.send)


_NAV_INJECT_SCRIPT = b"""<script>
(function(){
  var ul = document.querySelector('#top_menu .navbar-nav');
  if (!ul) return;
  function addLink(href, label){
    var exists = Array.from(ul.querySelectorAll('a')).some(function(a){ return a.getAttribute('href') === href; });
    if (exists) return;
    var li = document.createElement('li');
    li.className = 'nav-item';
    var a = document.createElement('a');
    a.className = 'nav-link';
    a.href = href;
    a.textContent = label;
    li.appendChild(a);
    ul.appendChild(li);
  }
  addLink('/config', 'Study Config');
  addLink('/export-network-images', 'Network Images');
  var path = window.location.pathname.replace(/\\/$/, '') || '/';
  ul.querySelectorAll('a.nav-link').forEach(function(a){
    var href = a.getAttribute('href').replace(/\\/$/, '') || '/';
    if (href === path) a.classList.add('active');
  });
})();
</script>"""


class NavInjectMiddleware:

    def __init__(self, app):
        self.app = app

    def __getattr__(self, name):
        return getattr(self.app, name)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        path = scope.get('path', '')
        # only inject into admin pages, skip API / static / config editor
        if path.startswith('/static/') or path.startswith('/api/') or path.startswith('/config'):
            await self.app(scope, receive, send)
            return

        chunks = []
        initial_message = None

        async def capture_send(message):
            nonlocal initial_message
            if message['type'] == 'http.response.start':
                initial_message = message
            elif message['type'] == 'http.response.body':
                chunks.append(message.get('body', b''))
                if not message.get('more_body', False):
                    content_type = ''
                    headers = initial_message.get('headers', [])
                    for name, val in headers:
                        if name == b'content-type':
                            content_type = val.decode('latin-1', errors='replace')
                            break

                    body = b''.join(chunks)
                    if 'text/html' in content_type and b'id="top_menu"' in body:
                        body = body.replace(b'</body>', _NAV_INJECT_SCRIPT + b'</body>')
                        new_headers = []
                        for name, val in headers:
                            if name == b'content-length':
                                val = str(len(body)).encode()
                            new_headers.append((name, val))
                        initial_message['headers'] = new_headers

                    await send(initial_message)
                    await send({'type': 'http.response.body', 'body': body})

        await self.app(scope, receive, capture_send)
