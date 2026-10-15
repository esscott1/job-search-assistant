"""Gmail adapter (read-only). Used by the intake graph (roadmap M2).

Status: implemented against the Gmail v1 API but not yet exercised end-to-end — the
first M2 task is running it against a real inbox and adding a recorded-fixture test.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime

from ..ports import MailMessage
from .http_jd_fetcher import html_to_text


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")


def _body_text(payload: dict) -> str:
    """Prefer text/plain; fall back to stripped text/html; walk multipart trees."""
    plain, html = [], []

    def walk(part: dict) -> None:
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data and mime == "text/plain":
            plain.append(_decode(data))
        elif data and mime == "text/html":
            html.append(_decode(data))
        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)
    if plain:
        return "\n".join(plain)
    return "\n".join(html_to_text(h) for h in html)


class GmailMail:
    def __init__(self, service=None):
        self._service = service

    @property
    def service(self):
        if self._service is None:
            from googleapiclient.discovery import build

            from .google_auth import load_credentials

            self._service = build(
                "gmail", "v1", credentials=load_credentials(), cache_discovery=False
            )
        return self._service

    def search(self, query: str, max_results: int = 50) -> list[MailMessage]:
        users = self.service.users()
        refs, page_token = [], None
        while len(refs) < max_results:
            resp = (
                users.messages()
                .list(userId="me", q=query, pageToken=page_token, maxResults=min(100, max_results))
                .execute()
            )
            refs.extend(resp.get("messages", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        out = []
        for ref in refs[:max_results]:
            msg = users.messages().get(userId="me", id=ref["id"], format="full").execute()
            headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
            out.append(
                MailMessage(
                    id=msg["id"],
                    thread_id=msg["threadId"],
                    sender=headers.get("from", ""),
                    subject=headers.get("subject", ""),
                    received_at=datetime.fromtimestamp(int(msg["internalDate"]) / 1000, tz=UTC),
                    body_text=_body_text(msg["payload"]),
                )
            )
        return out
