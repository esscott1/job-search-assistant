"""The dedup key: core's canonical_url must match the plugin's, so A and B dedup alike.

The plugin's `skills/job-search-assistant/job-tracker/canonical_url.py` is the source of truth,
and its own tests cover the rules. These tests read it from the repository checkout, which CI
always has.
"""

from pathlib import Path

from job_search_core import canonical_url

REPO = Path(__file__).resolve().parents[4]
PLUGIN_CANONICAL = REPO / "skills/job-search-assistant/job-tracker/canonical_url.py"


def _text(path: Path) -> bytes:
    # Compare content, not checkout line endings (a Windows checkout may use CRLF).
    return path.read_bytes().replace(b"\r\n", b"\n")


def test_canonical_url_matches_plugin_copy():
    assert _text(Path(canonical_url.__file__)) == _text(PLUGIN_CANONICAL), (
        "core's canonical_url differs from the plugin's: copy "
        "skills/job-search-assistant/job-tracker/canonical_url.py over "
        "orchestration/job-search/core/src/job_search_core/canonical_url.py"
    )


def test_tracking_variants_of_one_posting_share_a_key():
    a = canonical_url.canonical("https://www.linkedin.com/jobs/view/4000000002/?trk=eml&refId=x")
    b = canonical_url.canonical("https://www.linkedin.com/comm/jobs/view/4000000002?trackingId=y")
    assert a == b == "https://www.linkedin.com/jobs/view/4000000002/"


def test_links_that_are_not_postings_have_no_key():
    assert canonical_url.canonical("https://mail.google.com/mail/u/0/#all/abc") == ""
