"""Google OAuth for a personal account: one-time browser consent, then silent refresh.

Requires the `google` extra. The pipeline asks for `drive.file`, which reaches only the files
you pick in the Google Picker (your tracker) and the files the pipeline creates (its shadow
spreadsheet), nothing else in your Drive. `gmail.readonly` is added only when you ask for it
(`jobs auth google --gmail`), for B's own intake. See docs/setup/job-search-langgraph.md,
step 3, for the Google Cloud setup.

The files live in one folder, `data/google/` by default:
- `credentials.json`: the OAuth client (a Desktop client);
- `token.json`: your refresh token, written here after sign-in. It is a credential;
- `picker.json` and `sheets.json`: see `google_picker` and `google_sheets`.
"""

from __future__ import annotations

import os
from pathlib import Path

SIGN_IN = ["openid", "https://www.googleapis.com/auth/userinfo.email"]
DRIVE_FILE = "https://www.googleapis.com/auth/drive.file"
GMAIL_READONLY = "https://www.googleapis.com/auth/gmail.readonly"


class GoogleAuthError(RuntimeError):
    pass


def use_os_certificates() -> None:
    """Trust the operating system's certificates, not only Python's bundle. Without this,
    sign-in fails on machines whose antivirus or network inspects TLS."""
    import truststore

    truststore.inject_into_ssl()


def missing_scopes(granted: list[str] | None, needed: list[str]) -> list[str]:
    """Google's consent screen lets people untick a permission; this says which are missing."""
    return [s for s in needed if s not in set(granted or [])]


def _paths(folder: Path) -> tuple[Path, Path]:
    return folder / "credentials.json", folder / "token.json"


def _fix(scope: str) -> str:
    return "`jobs auth google --gmail`" if scope == GMAIL_READONLY else "`jobs auth google`"


def load_credentials(folder: Path, needs: str = DRIVE_FILE):
    """Return valid credentials that include `needs`, refreshing silently. Never opens a browser."""
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    _, token = _paths(folder)
    if not token.exists():
        raise GoogleAuthError(f"No Google token yet. Run {_fix(needs)} once to sign in.")
    creds = Credentials.from_authorized_user_file(str(token))
    if missing_scopes(creds.scopes, [needs]):
        raise GoogleAuthError(f"Google access to {needs} wasn't granted. Run {_fix(needs)}.")
    use_os_certificates()  # every Google call made with these credentials needs it, not just refresh
    if creds.valid:
        return creds
    try:
        creds.refresh(Request())
    except RefreshError as exc:
        raise GoogleAuthError(
            "Google refresh token was rejected (expired or revoked). Run `jobs auth google` to "
            "sign in again. If this happens about weekly, your OAuth app is still in 'Testing' "
            "(setup guide, step 3)."
        ) from exc
    token.write_text(creds.to_json())
    return creds


def sign_in(folder: Path, gmail: bool = False):
    """Open the browser for consent and save the token. Raises if a needed box was unticked."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    secrets, token = _paths(folder)
    if not secrets.exists():
        raise GoogleAuthError(f"OAuth client file not found at {secrets} (setup guide, step 3).")
    use_os_certificates()
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"  # a partial grant is reported below, not raised
    needed = SIGN_IN + [DRIVE_FILE] + ([GMAIL_READONLY] if gmail else [])
    flow = InstalledAppFlow.from_client_secrets_file(str(secrets), needed)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    missing = missing_scopes(creds.granted_scopes, needed)
    if missing:
        raise GoogleAuthError(
            "Sign-in didn't grant " + ", ".join(missing) + ". Run it again and tick every box "
            "on Google's permissions screen."
        )
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text(creds.to_json())
    try:
        token.chmod(0o600)
    except OSError:
        pass
    return creds


def signed_in_as(creds) -> str:
    """The Google account the token belongs to (one cheap Drive call)."""
    from googleapiclient.discovery import build

    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    return drive.about().get(fields="user(emailAddress)").execute()["user"]["emailAddress"]
