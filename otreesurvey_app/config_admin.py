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


def _collect_images():
    """Returns list of (session_code, participant_code, participant_label,
    data_url) for every player that has a saved network image."""
    from otree.common import get_models_module
    from otree.database import session_scope, dbq

    Player = get_models_module('otreesurvey_app').Player
    rows = []
    with session_scope():
        for player in dbq(Player):
            player._is_frozen = False
            img = player.field_maybe_none('network_image')
            if not img:
                continue
            rows.append((
                player.session.code,
                player.participant.code,
                player.participant.label or '',
                img,
            ))
    return rows


_GALLERY_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Network Images</title>
  <link rel="stylesheet" href="/static/bootstrap5/css/bootstrap.min.css">
  <style>
    body { background: #f5f5f5; }
    .wrap { max-width: 1100px; margin: 0 auto; padding: 20px 16px 60px; }
    .toolbar { position: sticky; top: 0; z-index: 5; background: #f5f5f5;
      display: flex; align-items: center; gap: 12px; padding: 12px 0;
      border-bottom: 1px solid #ddd; margin-bottom: 16px; }
    .toolbar .count { color: #555; margin-left: auto; }
    .session-block { margin-bottom: 28px; }
    .session-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
    .session-head h5 { margin: 0; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 14px; }
    .card2 { background: #fff; border: 1px solid #e2e2e2; border-radius: 8px;
      padding: 10px; box-shadow: 0 1px 2px rgba(0,0,0,.05); }
    .card2 img { width: 100%; border-radius: 6px; background: #fafafa; display: block; }
    .card2 .cap { display: flex; align-items: center; gap: 8px; margin-top: 8px; font-size: 13px; }
    .card2 .cap .code { color: #333; font-weight: 600; }
    .card2 .cap .label { color: #888; }
    .empty { color: #777; padding: 40px 0; text-align: center; }
  </style>
</head>
<body>
<nav class="navbar navbar-expand-sm navbar-dark bg-dark" id="top_menu">
  <div class="container-fluid">
    <a class="navbar-brand" href="/">oTree</a>
    <div class="navbar-collapse collapse">
      <ul class="navbar-nav">
        <li class="nav-item"><a class="nav-link" href="/demo">Demo</a></li>
        <li class="nav-item"><a class="nav-link" href="/sessions">Sessions</a></li>
        <li class="nav-item"><a class="nav-link" href="/export">Data</a></li>
        <li class="nav-item"><a class="nav-link" href="/config">Study Config</a></li>
        <li class="nav-item"><a class="nav-link active" href="/export-network-images">Network Images</a></li>
      </ul>
    </div>
  </div>
</nav>

<div class="wrap">
  <div class="toolbar">
    <button class="btn btn-primary btn-sm" id="saveSelected">Save selected</button>
    <button class="btn btn-outline-secondary btn-sm" id="saveAll">Save all</button>
    <span class="count" id="count"></span>
  </div>
  <div id="gallery"></div>
</div>

<script>
  var DATA = __DATA__;

  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }

  function allCodes(){
    var out = [];
    DATA.forEach(function(s){ s.items.forEach(function(it){ out.push(it.code); }); });
    return out;
  }

  function selectedCodes(){
    return Array.from(document.querySelectorAll('.img-check:checked')).map(function(c){ return c.value; });
  }

  function updateCount(){
    document.getElementById('count').textContent =
      selectedCodes().length + ' of ' + allCodes().length + ' selected';
  }

  function render(){
    var g = document.getElementById('gallery');
    if (!DATA.length){ g.innerHTML = '<div class="empty">No network images have been saved yet.</div>'; return; }
    g.innerHTML = DATA.map(function(s){
      var cards = s.items.map(function(it){
        return '<div class="card2">' +
          '<img loading="lazy" src="/network-image/' + encodeURIComponent(it.code) + '" alt="network">' +
          '<div class="cap"><input type="checkbox" class="img-check" value="' + esc(it.code) + '">' +
          '<span class="code">' + esc(it.code) + '</span>' +
          (it.label ? '<span class="label">' + esc(it.label) + '</span>' : '') +
          '</div></div>';
      }).join('');
      return '<div class="session-block">' +
        '<div class="session-head"><input type="checkbox" class="session-check" data-session="' + esc(s.session) + '">' +
        '<h5>Session ' + esc(s.session) + ' <small class="text-muted">(' + s.items.length + ')</small></h5></div>' +
        '<div class="grid">' + cards + '</div></div>';
    }).join('');

    g.querySelectorAll('.img-check').forEach(function(c){ c.addEventListener('change', updateCount); });
    g.querySelectorAll('.session-check').forEach(function(sc){
      sc.addEventListener('change', function(){
        var block = sc.closest('.session-block');
        block.querySelectorAll('.img-check').forEach(function(c){ c.checked = sc.checked; });
        updateCount();
      });
    });
    updateCount();
  }

  function download(codes){
    if (!codes.length){ alert('No images selected.'); return; }
    fetch('/export-network-images', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codes: codes })
    }).then(function(r){ return r.blob(); }).then(function(blob){
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url; a.download = 'network_images.zip';
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    });
  }

  document.getElementById('saveSelected').addEventListener('click', function(){ download(selectedCodes()); });
  document.getElementById('saveAll').addEventListener('click', function(){ download(allCodes()); });
  render();
</script>
</body>
</html>"""


class NetworkImageExportEndpoint(HTTPEndpoint):

    async def dispatch(self):
        request = Request(self.scope, receive=self.receive)
        if _needs_auth() and not _is_logged_in(request):
            response = Response('Unauthorized', status_code=401)
            await response(self.scope, self.receive, self.send)
            return

        if request.method == 'POST':
            body = await request.body()
            data = await run_in_threadpool(self._build_zip, body)
            response = Response(
                data,
                media_type='application/zip',
                headers={'Content-Disposition': 'attachment; filename="network_images.zip"'},
            )
        else:
            html = await run_in_threadpool(self._build_page)
            response = HTMLResponse(html)
        await response(self.scope, self.receive, self.send)

    def _build_page(self):
        sessions = {}
        for session_code, code, label, _ in _collect_images():
            sessions.setdefault(session_code, []).append({'code': code, 'label': label})
        data = [
            {'session': sc, 'items': items}
            for sc, items in sorted(sessions.items())
        ]
        return _GALLERY_HTML.replace('__DATA__', json.dumps(data))

    def _build_zip(self, body):
        from .data_export import build_image_zip

        try:
            codes = set(json.loads(body).get('codes', []))
        except (ValueError, TypeError, AttributeError):
            codes = set()
        images = [
            (f'{code}.png', data_url)
            for _, code, _, data_url in _collect_images()
            if code in codes
        ]
        return build_image_zip(images)


class NetworkImageEndpoint(HTTPEndpoint):
    """Serves a single participant's network image. Admin-gated."""

    async def dispatch(self):
        request = Request(self.scope, receive=self.receive)
        if _needs_auth() and not _is_logged_in(request):
            response = Response('Unauthorized', status_code=401)
            await response(self.scope, self.receive, self.send)
            return

        code = request.path_params.get('code', '')
        png = await run_in_threadpool(self._load, code)
        if png:
            response = Response(png, media_type='image/png')
        else:
            response = Response('Not found', status_code=404)
        await response(self.scope, self.receive, self.send)

    def _load(self, code):
        from .data_export import _decode_data_url

        for _, c, _, data_url in _collect_images():
            if c == code:
                return _decode_data_url(data_url)
        return None


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
