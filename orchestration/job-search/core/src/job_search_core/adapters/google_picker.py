"""The Google Picker, served from a local page, so you choose which file the pipeline may open.

With the `drive.file` scope, the pipeline reaches only files you pick here and files it creates.
The Picker needs two values from the Google Cloud project that owns the OAuth client, kept in
`data/google/picker.json`:

    {"api_key": "<an API key, ideally restricted to the Google Picker API>",
     "project_number": "<the project's number, not its ID>"}

Requires the `google` extra (for the token) and a browser.
"""

from __future__ import annotations

import html
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .google_auth import GoogleAuthError

PORT = 8765

_PAGE = """<!doctype html><meta charset="utf-8"><title>Pick a spreadsheet</title>
<body style="font-family:system-ui,sans-serif;margin:2em">
<p id="s">%(prompt)s</p>
<script>
function report(path, body) { return fetch(path, {method: 'POST', body: body}); }
window.onerror = (m) => { report('/error', String(m)); };
function start() {
  gapi.load('picker', () => {
    const view = new google.picker.DocsView(google.picker.ViewId.SPREADSHEETS)
      .setMode(google.picker.DocsViewMode.LIST);
    const only = %(only)s;
    if (only) view.setFileIds(only);
    new google.picker.PickerBuilder()
      .addView(view)
      .setOAuthToken(%(token)s)
      .setDeveloperKey(%(key)s)
      .setAppId(%(app)s)
      .setCallback((d) => {
        if (d.action === google.picker.Action.PICKED) {
          report('/picked', d.docs[0].id).then(() => s.textContent = 'Done. You can close this tab.');
        } else if (d.action === google.picker.Action.CANCEL) {
          report('/picked', '').then(() => s.textContent = 'Cancelled. You can close this tab.');
        }
      })
      .build().setVisible(true);
  });
}
</script>
<script src="https://apis.google.com/js/api.js" onload="start()"
  onerror="report('/error', 'could not load the Google Picker script')"></script>
"""


def _config(google_dir: Path) -> dict:
    path = google_dir / "picker.json"
    if not path.exists():
        raise GoogleAuthError(f"Picker settings not found at {path} (setup guide, step 3).")
    config = json.loads(path.read_text(encoding="utf-8"))
    if not config.get("api_key") or not str(config.get("project_number", "")).isdigit():
        raise GoogleAuthError(f"{path} needs an api_key and a numeric project_number.")
    return config


def pick_spreadsheet(
    creds, google_dir: Path, prompt: str, only: str | None = None, timeout: int = 600
) -> str:
    """Open the Picker in the browser and return the ID of the spreadsheet picked.

    With `only`, the Picker shows just that spreadsheet, and picking anything else is refused:
    the pick then approves access to a file chosen elsewhere (the profile), it doesn't choose.
    """
    config = _config(google_dir)
    page = _PAGE % {
        "prompt": html.escape(prompt),
        "token": json.dumps(creds.token),
        "key": json.dumps(config["api_key"]),
        "app": json.dumps(str(config["project_number"])),
        "only": json.dumps(only or ""),
    }
    picked: list[str] = []
    errors: list[str] = []
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(page.encode())

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
            self.send_response(204)
            self.end_headers()
            if self.path == "/error":
                errors.append(body)
            else:
                picked.append(body)
                done.set()

        def log_message(self, *args):
            pass

    server = HTTPServer(("localhost", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://localhost:{PORT}/"
    print(f"Opening the Google Picker at {url}")
    webbrowser.open(url)
    try:
        if not done.wait(timeout):
            raise GoogleAuthError("Nothing was picked. " + " ".join(errors))
    finally:
        server.shutdown()
    if not picked[0]:
        raise GoogleAuthError("The Picker was cancelled.")
    if only and picked[0] != only:
        raise GoogleAuthError("A different spreadsheet was picked from the one asked for.")
    return picked[0]
