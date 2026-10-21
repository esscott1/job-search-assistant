"""Checks for read_posting.py. Run with: python3 -m pytest -q skills/job-search-assistant/job-tracker

All pages here are synthetic; the company and job are made up. No test touches the network.
"""

import datetime as dt
import json
import urllib.error

import read_posting
from read_posting import html_to_text, main, read_page

TODAY = dt.date(2026, 10, 20)
BOILERPLATE = ("This posting will remain active until the position is filled, "
               "or a qualified pool of candidates is identified.")

JOB = {
    "title": "Program Manager, Cloud Operations",
    "location": "Columbus, Ohio, United States",
    "description": "<p><b>Job Description</b></p><p>Lead cloud migration programs.</p>"
                   f"<ul><li>Own the program plan</li><li>Manage vendors</li></ul><p>{BOILERPLATE}</p>",
    "requiredSkillsEducation": "<ul><li>8 years of program management</li></ul>",
    "preferredSkillsEducation": "<ul><li>PMP certification</li></ul>",
    "salaryMin": 150000, "salaryMax": 120000, "payRange": "150000 - 120000 USD per year",
    "physicalLocation": "Hybrid", "postedDate": "2026-10-19T09:00:00.000+0000",
}

# A career-platform page: the description lives in embedded JSON, and every job page carries a
# "filled" banner that the site's JavaScript hides while the job is open.
EMBEDDED_PAGE = f"""<html><head><title>Program Manager</title></head><body>
<h1>Program Manager, Cloud Operations</h1>
<h2><ppc-content key="ph-html-v1-job-expire-view-x" data-ph-at-id="job-completion-info">This position has been
filled and/or is no longer accepting applications.</ppc-content></h2>
<script>var phApp = phApp || {{}}; phApp.ddo = {json.dumps({"jobDetail": {"status": 200, "data": {"job": JOB}}})};
phApp.other = {{}};</script>
</body></html>"""


def json_ld_page(**extra) -> str:
    posting = {
        "@context": "https://schema.org", "@type": "JobPosting", "title": "IT Vendor Manager",
        "description": "<p>Run vendor selection and contracts.</p>", "datePosted": "2026-10-01",
        "jobLocation": {"@type": "Place", "address": {"addressLocality": "Austin", "addressRegion": "TX",
                                                      "addressCountry": "US"}},
        "baseSalary": {"currency": "USD", "value": {"minValue": 120000, "maxValue": 140000, "unitText": "YEAR"}},
        **extra,
    }
    return f'<html><head><script type="application/ld+json">{json.dumps(posting)}</script></head><body></body></html>'


def test_hidden_filled_banner_is_not_closed():
    result = read_page(EMBEDDED_PAGE, TODAY)
    assert result["status"] == "open"
    assert result["source"] == "embedded-data"
    assert "filled" not in result["status_evidence"]


def test_embedded_description_is_read_in_full():
    result = read_page(EMBEDDED_PAGE, TODAY)
    assert "Lead cloud migration programs." in result["jd_text"]
    assert "- Manage vendors" in result["jd_text"]
    assert "Required:\n- 8 years of program management" in result["jd_text"]
    assert "Preferred:\n- PMP certification" in result["jd_text"]
    assert result["title"] == "Program Manager, Cloud Operations"
    assert result["pay"] == "120,000-150,000 USD per year"
    assert result["posted"] == "2026-10-19"
    assert result["arrangement"] == "Hybrid"


def test_boilerplate_about_filling_the_position_stays_open():
    result = read_page(EMBEDDED_PAGE, TODAY)
    assert BOILERPLATE in result["jd_text"]
    assert result["status"] == "open"


def test_empty_embedded_job_is_unknown_not_closed():
    page = 'phApp.ddo = {"jobDetail": {"status": 200, "data": {"job": {"title": "X"}}}};'
    assert read_page(page, TODAY)["status"] == "unknown"


def test_json_ld_posting():
    result = read_page(json_ld_page(), TODAY)
    assert result["status"] == "open"
    assert result["source"] == "json-ld"
    assert result["location"] == "Austin, TX, US"
    assert result["pay"] == "120000-140000 USD per year"
    assert result["jd_text"] == "Run vendor selection and contracts."


def test_json_ld_past_valid_through_is_closed():
    result = read_page(json_ld_page(validThrough="2026-09-30T23:59"), TODAY)
    assert result["status"] == "closed"
    assert "2026-09-30" in result["status_evidence"]


def test_json_ld_future_valid_through_is_open():
    assert read_page(json_ld_page(validThrough="2026-12-31"), TODAY)["status"] == "open"


def test_json_ld_inside_a_graph_and_remote():
    page = json_ld_page(jobLocationType="TELECOMMUTE").replace(
        '{"@context"', '{"@graph": [{"@type": "Organization"}, {"@context"').replace("</script>", "]}</script>")
    result = read_page(page, TODAY)
    assert result["source"] == "json-ld"
    assert result["arrangement"] == "remote"


def test_page_without_data_is_unknown_and_ignores_hidden_banner():
    page = """<body><div class="job-expired" hidden>This job is no longer available.</div>
    <main><h1>Data Engineer</h1><ul><li>Build pipelines<li>Own data quality</ul></main>
    <div style="display: none">This position has been filled.</div><p>Apply now.</p></body>"""
    result = read_page(page, TODAY)
    assert result["status"] == "unknown"
    assert result["source"] == "visible-text"
    assert "Build pipelines" in result["jd_text"] and "Apply now." in result["jd_text"]
    assert "filled" not in result["jd_text"] and "no longer" not in result["jd_text"]
    assert "hidden 'filled' template was ignored" in result["status_evidence"]


def test_visible_closure_text_is_reported_not_decided():
    result = read_page("<body><p>This job is no longer accepting applications.</p></body>", TODAY)
    assert result["status"] == "unknown"
    assert "visible text mentions closure" in result["status_evidence"]


def test_html_to_text_lines():
    assert html_to_text("<b>Title</b></br><p>One &amp; two</p><li>Item</li>") == "Title\nOne & two\n\n- Item"


class _Response:
    def __init__(self, url, body):
        self._url, self._body = url, body.encode()
        self.headers = self

    def get_content_charset(self):
        return "utf-8"

    def geturl(self):
        return self._url

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _serve(monkeypatch, final_url=None, body="", error=None):
    def urlopen(request, timeout):
        if error:
            raise error
        return _Response(final_url or request.full_url, body)

    monkeypatch.setattr(read_posting.urllib.request, "urlopen", urlopen)


def test_fetch_404_is_closed(monkeypatch):
    url = "https://careers.example.com/job/12345"
    _serve(monkeypatch, error=urllib.error.HTTPError(url, 404, "Not Found", {}, None))
    assert read_posting.fetch(url)["status"] == "closed"


def test_fetch_403_is_unreachable_not_closed(monkeypatch):
    url = "https://careers.example.com/job/12345"
    _serve(monkeypatch, error=urllib.error.HTTPError(url, 403, "Forbidden", {}, None))
    assert read_posting.fetch(url)["status"] == "unreachable"


def test_fetch_redirect_to_listing_is_closed(monkeypatch):
    _serve(monkeypatch, final_url="https://careers.example.com/search?error=true")
    result = read_posting.fetch("https://careers.example.com/job/12345/program-manager")
    assert result["status"] == "closed"
    assert "redirected away" in result["status_evidence"]


def test_fetch_redirect_that_keeps_the_job_id_is_read(monkeypatch):
    _serve(monkeypatch, final_url="https://careers.example.com/global/en/job/12345/Program-Manager", body=EMBEDDED_PAGE)
    result = read_posting.fetch("https://careers.example.com/job/12345")
    assert result["status"] == "open"


def test_cli_html_file_and_unreachable_exit_code(tmp_path, capsys, monkeypatch):
    page = tmp_path / "page.html"
    page.write_text(EMBEDDED_PAGE, encoding="utf-8")
    assert main(["--html", str(page), "https://careers.example.com/job/12345"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "open" and printed["final_url"].endswith("12345")

    _serve(monkeypatch, error=urllib.error.URLError("no network"))
    assert main(["https://careers.example.com/job/12345"]) == 3
    assert json.loads(capsys.readouterr().out)["status"] == "unreachable"
