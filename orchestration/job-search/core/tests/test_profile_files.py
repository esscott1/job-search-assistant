"""The profile names the full resume, and the resume sits in the profile's folder."""

import pytest
from job_search_core import profile
from job_search_core.adapters.fakes import SYNTHETIC_PROFILE
from job_search_core.adapters.files import FileProfileSource, ProfileResumeSource


def test_full_resume_name_comes_from_the_candidate_section():
    assert profile.full_resume_name(SYNTHETIC_PROFILE) == "Full-Resume.md"


def test_a_blank_full_resume_setting_is_an_error():
    blank = SYNTHETIC_PROFILE.replace("- Full resume: Full-Resume.md", "- Full resume:")
    with pytest.raises(profile.ProfileError, match="Full resume"):
        profile.full_resume_name(blank)


def test_resume_is_read_from_the_profiles_folder(tmp_path):
    (tmp_path / "job-search-profile.md").write_text(SYNTHETIC_PROFILE, encoding="utf-8")
    (tmp_path / "Full-Resume.md").write_text("# Jordan Example\nWhole career", encoding="utf-8")
    resume = ProfileResumeSource(FileProfileSource(tmp_path / "job-search-profile.md"))
    assert resume.path == tmp_path / "Full-Resume.md"
    assert resume.read().startswith("# Jordan Example")
    assert len(resume.content_hash()) == 16


def test_missing_resume_names_the_file_and_folder(tmp_path):
    (tmp_path / "job-search-profile.md").write_text(SYNTHETIC_PROFILE, encoding="utf-8")
    resume = ProfileResumeSource(FileProfileSource(tmp_path / "job-search-profile.md"))
    with pytest.raises(FileNotFoundError, match="Full-Resume.md") as err:
        resume.read()
    assert str(tmp_path) in str(err.value)


def test_missing_profile_says_how_to_fix_it(tmp_path):
    resume = ProfileResumeSource(FileProfileSource(tmp_path / "job-search-profile.md"))
    with pytest.raises(FileNotFoundError, match="JOBS_PROFILE"):
        resume.read()
