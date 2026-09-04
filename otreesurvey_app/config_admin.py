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


_DOCS_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Study Config Guide</title>
  <link rel="stylesheet" href="/static/bootstrap5/css/bootstrap.min.css">
  <style>
    body { background: #f5f5f5; color: #212529; }
    .layout { display: flex; align-items: flex-start; }
    .toc { width: 220px; flex-shrink: 0; position: sticky; top: 56px; height: calc(100vh - 56px);
      overflow-y: auto; padding: 18px 0; border-right: 1px solid #dee2e6; background: #fff; }
    .toc a { display: block; padding: 6px 20px; color: #555; text-decoration: none; font-size: 14px; border-left: 3px solid transparent; }
    .toc a:hover { background: #f0f0f0; }
    .toc a.section { font-weight: 600; color: #212529; margin-top: 6px; }
    .doc { max-width: 780px; padding: 28px 34px 80px; line-height: 1.6; }
    .doc h1 { font-size: 26px; margin: 0 0 6px; }
    .doc h2 { font-size: 20px; margin: 34px 0 10px; padding-top: 10px; border-top: 1px solid #e6e6e6; }
    .doc h1 + p.lead { color: #555; margin-bottom: 8px; }
    .doc p, .doc li { font-size: 15px; }
    .doc ul { padding-left: 20px; }
    .doc li { margin: 5px 0; }
    .doc code { background: #eef1f4; padding: 1px 5px; border-radius: 3px; font-size: 13px; word-break: break-word; }
    .doc .field { font-weight: 600; }
    .callout { background: #fff8e1; border: 1px solid #ffe082; border-left: 4px solid #ff9800;
      border-radius: 6px; padding: 10px 14px; margin: 12px 0; font-size: 14px; color: #5f4300; }
    .note { background: #eef4fb; border: 1px solid #cfe0f3; border-left: 4px solid #4a90d9;
      border-radius: 6px; padding: 10px 14px; margin: 12px 0; font-size: 14px; color: #234; }
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
        <li class="nav-item"><a class="nav-link" href="/rooms">Rooms</a></li>
        <li class="nav-item"><a class="nav-link" href="/export">Data</a></li>
        <li class="nav-item"><a class="nav-link" href="/server_check">Server Check</a></li>
        <li class="nav-item"><a class="nav-link" href="/config">Study Config</a></li>
        <li class="nav-item"><a class="nav-link" href="/export-network-images">Network Images</a></li>
        <li class="nav-item"><a class="nav-link active" href="/docs">Guide</a></li>
      </ul>
    </div>
  </div>
</nav>

<div class="layout">
  <nav class="toc">
    <a class="section" href="#overview">Overview</a>
    <a class="section" href="#editing">Editing and saving</a>
    <a class="section" href="#study">Study</a>
    <a class="section" href="#recruitment">Recruitment</a>
    <a class="section" href="#ai-model">AI Model</a>
    <a class="section" href="#interview">Interview</a>
    <a class="section" href="#extraction">Node Extraction</a>
    <a class="section" href="#rating">Node Rating</a>
    <a class="section" href="#canvas">Canvas</a>
    <a class="section" href="#final">Final Network</a>
  </nav>

  <div class="doc">
    <h1 id="overview">Study Config Guide</h1>
    <p class="lead">How to set up and run a study from the Study Config page. You do not need to touch any code - everything here is set through the admin pages.</p>

    <p><b>How a run works.</b> A participant opens your study link and reads the consent page. If they decline, they leave right away. If they agree, they go through the task: rating statements about your topic and arranging them into a visual map of how they relate, and (in the interview version) a short AI-led conversation first. When they finish, they are sent back to your recruitment platform. Everything they do is saved, and you can download it from the <a href="/export">Data</a> page and the <a href="/export-network-images">Network Images</a> page.</p>

    <h2 id="editing">Editing and saving</h2>
    <ul>
      <li>Open <a href="/config">Study Config</a>, pick a section on the left, change the values, then click <b>Save Config</b>.</li>
      <li>Changes take effect for the next participant who starts. You do not need to restart anything.</li>
      <li>Use <b>Download</b> to save a backup of your settings, and <b>Upload</b> to load one back in.</li>
      <li>Most fields have a small grey note underneath explaining what they do.</li>
    </ul>

    <h2 id="study">Study</h2>
    <ul>
      <li><span class="field">Study label</span> - an internal name for this run (e.g. <code>pilot_june_2026</code>). Participants never see it; it just helps you tell runs apart.</li>
      <li><span class="field">Consent intro text</span> - the main text on the consent page.</li>
      <li><span class="field">Consent highlight text</span> - a short highlighted line under the intro, usually the time estimate and payment.</li>
    </ul>

    <h2 id="recruitment">Recruitment</h2>
    <p>The links that send participants back to Prolific or CloudResearch. These are required for a real study - without them the platform never learns the participant finished, so they cannot be paid.</p>
    <ul>
      <li><span class="field">Completion link</span> - where a participant goes after finishing successfully. On Prolific this is the completion URL for your "Completed" code (<code>https://app.prolific.com/submissions/complete?cc=...</code>); on CloudResearch it is the study Redirect URL.</li>
      <li><span class="field">Screen-out link</span> - where a participant goes if they are screened out (they did not place enough statements to be usable). On Prolific, make a separate "Screen out" code so these are not approved as full completions. Leave blank to send them to the completion link instead.</li>
      <li><span class="field">No-consent link</span> - where a participant goes if they decline consent.</li>
    </ul>
    <div class="callout"><b>Passing the participant ID.</b> Add <code>participant_label</code> to your study link so the platform fills in each person's ID, e.g. <code>https://YOUR-HOST/join/YOUR-ROOM?participant_label={{%PROLIFIC_PID%}}</code> on Prolific (use CloudResearch's <code>participantId</code> placeholder on CloudResearch). The ID is then saved with the participant's data automatically - no other setup needed.</div>

    <h2 id="ai-model">AI Model</h2>
    <p>Which AI model runs the interview and pulls beliefs out of it.</p>
    <ul>
      <li><span class="field">Provider</span> and <span class="field">Model</span> - normally set once during setup.</li>
      <li><span class="field">Technical settings</span> (hidden until you click "technical settings") - the API key variable, temperature, and retry behaviour. Leave these as they are unless you know what they do.</li>
    </ul>

    <h2 id="interview">Interview</h2>
    <p>Settings for the AI conversation, used in the interview version of the study.</p>
    <ul>
      <li><span class="field">Topic</span> - the subject of the interview (e.g. meat-eating). Write <code>{topic}</code> in the interviewer fields below to insert it.</li>
      <li><span class="field">Maximum conversation length</span> - how many back-and-forth turns before the interview ends.</li>
      <li><span class="field">Participant input</span> - whether people answer by typing, speaking, or either.</li>
      <li><span class="field">Show interview rating page</span> - off: participants see a short loading screen while their answers are analysed, then continue automatically. On: they first rate the interview on a few sliders.</li>
      <li><span class="field">Opening question</span> and <span class="field">Closing question</span> - the first and last things the interviewer asks.</li>
      <li><span class="field">AI Interviewer</span> (style, what to explore, extra instructions) - shape the interviewer's manner and what it tries to draw out. The core interview logic (pacing, follow-ups, wrap-up) is fixed, so these fields cannot break the interview.</li>
    </ul>
    <div class="note">Whether a given participant does the interview at all is decided by their assigned study condition, not by a single switch on this tab.</div>

    <h2 id="extraction">Node Extraction</h2>
    <p>How the statements that participants rate and map are decided.</p>
    <ul>
      <li><span class="field">Mode</span> - <b>Closed</b>: participants rate a fixed set of statements you write below. <b>Open</b>: the AI reads the interview and pulls out each person's own beliefs.</li>
      <li><span class="field">Items</span> (Closed mode) - each item is one belief statement, with its scale wording and guidance for the AI. Add or remove items here.</li>
      <li><span class="field">Open Extraction Settings</span> (Open mode) - the most beliefs the AI will pull from one interview, plus optional extra guidance.</li>
    </ul>

    <h2 id="rating">Node Rating</h2>
    <p>How each statement gets rated before it goes on the map.</p>
    <ul>
      <li><span class="field">Agreement</span> (fixed) - every statement is rated on a built-in 6-point agreement scale (Strongly disagree to Strongly agree). This scale is fixed and cannot be edited.</li>
      <li><span class="field">Extra dimensions</span> - add your own extra rating scales (e.g. personal importance), each with its own label and endpoint wording.</li>
    </ul>

    <h2 id="canvas">Canvas</h2>
    <p>The map-building task and the tutorial video shown before it.</p>
    <p><b>Intro Video.</b> Upload your own tutorial video or keep the built-in demo. Use <b>Upload video</b> to replace it and <b>Use built-in video</b> to go back.</p>
    <ul>
      <li>Supported files: mp4, webm, ogg, or mov, up to 50 MB, one video at a time. A YouTube link will not work - it must be a direct video file.</li>
      <li>If you upload your own video, update the two text boxes below it <b>and</b> the example statements in the video texts so they describe what your video actually shows. The built-in texts describe the demo video's example.</li>
    </ul>
    <div class="callout"><b>Hosting note.</b> An uploaded video is stored on the server. On some hosting setups the server's files are reset when it restarts, so you may need to re-upload the video after a restart. If in doubt, check that the video still plays after deploying.</div>
    <p><b>Canvas.</b></p>
    <ul>
      <li><span class="field">Minimum / maximum statements on map</span> - how many statements a participant must place. Someone who places fewer than the minimum is screened out (sent to the screen-out link).</li>
      <li><span class="field">Appearance settings</span> (hidden until you click "appearance settings") - which rating drives node colour, the colour range, and node size.</li>
    </ul>
    <p><b>Relationship Types.</b> The kinds of connections participants can draw between statements (e.g. Supporting, Conflicting). Each has a label, a colour, and the wording shown to participants.</p>
    <p><b>Mutually Exclusive Relationships.</b> Put relationship types in a group if a pair of statements should only ever have one of them - for example, group Supporting and Conflicting so a pair can be one or the other, not both. Leave empty to allow any combination.</p>

    <h2 id="final">Final Network</h2>
    <ul>
      <li><span class="field">Show final network to participants</span> - when on, participants see their finished map and answer a few follow-up questions about it.</li>
      <li><span class="field">Follow-up questions</span> - the questions shown on that final page.</li>
    </ul>
  </div>
</div>
</body>
</html>"""


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


class DocsPageEndpoint(HTTPEndpoint):

    async def dispatch(self):
        request = Request(self.scope, receive=self.receive)
        if _needs_auth() and not _is_logged_in(request):
            from starlette.responses import RedirectResponse
            response = RedirectResponse('/login')
            await response(self.scope, self.receive, self.send)
            return
        response = HTMLResponse(_DOCS_HTML)
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
    .card2 img { width: 100%; border-radius: 6px; background: #fafafa; display: block; cursor: zoom-in; }
    .card2 .cap { display: flex; align-items: center; gap: 8px; margin-top: 8px; font-size: 13px; }
    .card2 .cap .code { color: #333; font-weight: 600; }
    .card2 .cap .label { color: #888; }
    .empty { color: #777; padding: 40px 0; text-align: center; }
    .lightbox { position: fixed; inset: 0; background: rgba(0,0,0,.82); display: none;
      align-items: center; justify-content: center; z-index: 50; padding: 30px; }
    .lightbox.open { display: flex; }
    .lightbox img { max-width: 95vw; max-height: 86vh; border-radius: 8px; background: #fff;
      box-shadow: 0 10px 40px rgba(0,0,0,.5); }
    .lightbox .lb-cap { position: absolute; bottom: 16px; left: 0; right: 0; text-align: center;
      color: #fff; font-size: 14px; }
    .lightbox .lb-close { position: absolute; top: 12px; right: 20px; color: #fff; font-size: 34px;
      line-height: 1; cursor: pointer; background: none; border: none; }
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
        <li class="nav-item"><a class="nav-link" href="/rooms">Rooms</a></li>
        <li class="nav-item"><a class="nav-link" href="/export">Data</a></li>
        <li class="nav-item"><a class="nav-link" href="/server_check">Server Check</a></li>
        <li class="nav-item"><a class="nav-link" href="/config">Study Config</a></li>
        <li class="nav-item"><a class="nav-link active" href="/export-network-images">Network Images</a></li>
        <li class="nav-item"><a class="nav-link" href="/docs">Guide</a></li>
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

<div class="lightbox" id="lightbox">
  <button class="lb-close" id="lbClose" aria-label="Close">&times;</button>
  <img id="lbImg" src="" alt="network">
  <div class="lb-cap" id="lbCap"></div>
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
          '<img loading="lazy" src="/network-image/' + encodeURIComponent(it.code) + '" alt="network"' +
          ' data-code="' + esc(it.code) + '" data-label="' + esc(it.label || '') + '">' +
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

    g.querySelectorAll('.card2 img').forEach(function(img){
      img.addEventListener('click', function(){
        openLightbox(img.getAttribute('src'), img.dataset.code, img.dataset.label);
      });
    });
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

  var lightbox = document.getElementById('lightbox');
  function openLightbox(src, code, label){
    document.getElementById('lbImg').src = src;
    document.getElementById('lbCap').textContent = code + (label ? ' - ' + label : '');
    lightbox.classList.add('open');
  }
  function closeLightbox(){
    lightbox.classList.remove('open');
    document.getElementById('lbImg').src = '';
  }
  lightbox.addEventListener('click', function(e){ if (e.target === lightbox) closeLightbox(); });
  document.getElementById('lbClose').addEventListener('click', closeLightbox);
  document.addEventListener('keydown', function(e){ if (e.key === 'Escape') closeLightbox(); });

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
  addLink('/docs', 'Guide');
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
