"""Google OAuth for a personal account: one-time browser consent, then silent refresh.

Requires the `google` extra. See docs/setup/job-search-langgraph.md for the Google Cloud
setup — in particular, publish the OAuth app to "In production", or Google expires the
refresh token after 7 days and the pipeline starts failing weekly.
"""

from __future__ import annotations

import os
from pathlib import Path

# Read-only on purpose: the pipeline never sends mail or edits Drive files.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


class GoogleAuthError(RuntimeError):
    pass


def _paths() -> tuple[Path, Path]:
    secrets = Path(os.environ.get("GOOGLE_CLIENT_SECRETS", "data/google/credentials.json"))
    token = Path(os.environ.get("GOOGLE_TOKEN_PATH", "data/google/token.json"))
    return secrets, token


def load_credentials(interactive: bool = False):
    """Return valid credentials, refreshing silently. Opens a browser only if interactive."""
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    secrets, token = _paths()
    creds = None
    if token.exists():
        creds = Credentials.from_authorized_user_file(str(token), SCOPES)

    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError as exc:
            if not interactive:
                raise GoogleAuthError(
                    "Google refresh token was rejected (expired or revoked). "
                    "Run `jobs auth google` to sign in again. If this happens about weekly, "
                    "your OAuth app is still in 'Testing' — publish it (setup guide, step 3)."
                ) from exc
            creds = None
        else:
            token.write_text(creds.to_json())
            return creds

    if not interactive:
        raise GoogleAuthError("No Google token yet. Run `jobs auth google` once to sign in.")
    if not secrets.exists():
        raise GoogleAuthError(f"OAuth client file not found at {secrets} (setup guide, step 3).")

    flow = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text(creds.to_json())
    try:
        token.chmod(0o600)
    except OSError:
        pass
    return creds


def verify() -> dict[str, str]:
    """Make one cheap read call to Gmail and Drive; return who we're signed in as."""
    from googleapiclient.discovery import build

    creds = load_credentials(interactive=False)
    gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    profile = gmail.users().getProfile(userId="me").execute()
    about = drive.about().get(fields="user(emailAddress)").execute()
    return {"gmail": profile["emailAddress"], "drive": about["user"]["emailAddress"]}
