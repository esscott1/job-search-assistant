"""Checks for canonical_url.py. Run with: python3 -m pytest -q skills/job-search-assistant/job-tracker

All URLs here are synthetic; IDs and tokens are made up.
"""

from canonical_url import canonical

LINKEDIN_EMAIL_LINK = (
    "https://www.linkedin.com/comm/jobs/view/4000000001/?trackingId=abc%3D%3D&amp;refId=def"
    "&amp;lipi=urn%3Ali%3Apage&amp;midToken=AQ&amp;midSig=1x&amp;trk=eml-email_job_alert"
    "&amp;trkEmail=eml-x&amp;eid=9f&amp;otpToken=SECRET123"
)


def test_linkedin_email_link_reduces_to_job_id():
    assert canonical(LINKEDIN_EMAIL_LINK) == "https://www.linkedin.com/jobs/view/4000000001/"


def test_linkedin_one_time_token_never_survives():
    assert "otpToken" not in canonical(LINKEDIN_EMAIL_LINK)
    assert "SECRET123" not in canonical(LINKEDIN_EMAIL_LINK)


def test_same_linkedin_job_from_two_digests_matches():
    a = "https://www.linkedin.com/comm/jobs/view/4000000001/?trackingId=one&trk=digest_01"
    b = "https://linkedin.com/jobs/view/4000000001?refId=two"
    assert canonical(a) == canonical(b)


def test_linkedin_slug_and_current_job_id_forms():
    assert canonical("https://www.linkedin.com/jobs/view/senior-architect-at-acme-4000000002/") == (
        "https://www.linkedin.com/jobs/view/4000000002/"
    )
    assert canonical("https://www.linkedin.com/jobs/search/?currentJobId=4000000003&keywords=x") == (
        "https://www.linkedin.com/jobs/view/4000000003/"
    )


def test_linkedin_non_job_links_are_not_postings():
    assert canonical("https://www.linkedin.com/comm/jobs/search-results/?keywords=architect") == ""
    assert canonical("https://www.linkedin.com/job-alert-email-unsubscribe?x=1") == ""


def test_click_tracker_cannot_be_resolved():
    assert canonical("https://clicks.alerts.myjobhelper.com/f/a/abc~~/def~~/ghi") == ""


def test_gmail_message_link_is_not_a_posting():
    a = canonical("https://mail.google.com/mail/u/0/#all/1a00000000000001")
    b = canonical("https://mail.google.com/mail/u/0/#all/1a00000000000002")
    assert a == b == ""


def test_greenhouse_old_and_new_hosts_match():
    assert canonical("https://boards.greenhouse.io/acme/jobs/1234567?gh_src=email") == (
        canonical("https://job-boards.greenhouse.io/acme/jobs/1234567")
    )


def test_lever_apply_page_matches_posting():
    uuid = "0f0e0d0c-0b0a-0908-0706-050403020100"
    assert canonical(f"https://jobs.lever.co/acme/{uuid}/apply?lever-source=LinkedIn") == (
        f"https://jobs.lever.co/acme/{uuid}"
    )


def test_greenhouse_embed_link_matches_board_posting():
    assert canonical("https://boards.greenhouse.io/embed/job_app?for=acme&token=1234567") == (
        "https://job-boards.greenhouse.io/acme/jobs/1234567"
    )


def test_ashby_application_page_matches_posting():
    uuid = "0a0b0c0d-0e0f-1011-1213-141516171819"
    assert canonical(f"https://jobs.ashbyhq.com/acme/{uuid}/application?utm_source=x") == (
        f"https://jobs.ashbyhq.com/acme/{uuid}"
    )


def test_workday_locale_apply_and_query_are_dropped():
    base = "https://acme.wd1.myworkdayjobs.com"
    posting = f"{base}/External/job/Denver-CO/Senior-Architect_R0001234"
    assert canonical(f"{base}/en-US/External/job/Denver-CO/Senior-Architect_R0001234?source=Email") == posting
    assert canonical(f"{posting}/apply/applyManually") == posting
    assert canonical(f"{base}/External/details/Senior-Architect_R0001234") == (
        f"{base}/External/details/Senior-Architect_R0001234"
    )


def test_workday_listing_page_is_not_reduced_to_a_posting():
    assert canonical("https://acme.wd1.myworkdayjobs.com/External?q=architect") == (
        "https://acme.wd1.myworkdayjobs.com/External?q=architect"
    )


def test_icims_slug_and_iframe_params_are_dropped():
    assert canonical(
        "https://careers-acme.icims.com/jobs/12345/senior-architect/job?mobile=false&in_iframe=1"
    ) == "https://careers-acme.icims.com/jobs/12345/job"


def test_smartrecruiters_tracking_dropped():
    assert canonical(
        "https://jobs.smartrecruiters.com/Acme/743999000000001-senior-architect?trid=abc"
    ) == "https://jobs.smartrecruiters.com/Acme/743999000000001-senior-architect"


def test_generic_page_drops_tracking_but_keeps_meaningful_params():
    url = "http://Careers.Example.com/jobs/123/?utm_source=x&utm_medium=y&gh_jid=987&ref=mail#apply"
    assert canonical(url) == "https://careers.example.com/jobs/123?gh_jid=987"


def test_not_a_url():
    assert canonical("") == ""
    assert canonical("see email") == ""
    assert canonical("mailto:jobs@example.com") == ""
