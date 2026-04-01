from unittest.mock import MagicMock

import pytest
from jira.exceptions import JIRAError

from src.objects.job import Job
from src.report.report import Report


@pytest.fixture
def report_instance():
    report = Report.__new__(Report)
    report.logger = MagicMock()
    yield report


@pytest.fixture
def sample_job():
    job = MagicMock(spec=Job)
    job.name = "periodic-ci-example"
    job.build_id = "12345"
    return job


def test_add_retrigger_job_label_posts_fallback_comment_when_labels_not_applied(
    report_instance,
    sample_job,
):
    jira = MagicMock()
    jira.add_labels_to_issue.return_value = (MagicMock(), False)

    report_instance.add_retrigger_job_label(
        jira=jira,
        issue_id="ROX-1",
        job=sample_job,
    )

    jira.add_labels_to_issue.assert_called_once()
    jira.comment.assert_called_once()
    body = jira.comment.call_args.kwargs["comment"]
    assert jira.comment.call_args.kwargs["issue_id"] == "ROX-1"
    assert "retrigger" in body.lower()
    assert sample_job.name in body
    assert sample_job.build_id in body


def test_add_retrigger_job_label_swallows_fallback_comment_jira_error(
    report_instance,
    sample_job,
):
    jira = MagicMock()
    jira.add_labels_to_issue.return_value = (MagicMock(), False)
    jira.comment.side_effect = JIRAError("bad", 400, "https://jira/x")

    report_instance.add_retrigger_job_label(
        jira=jira,
        issue_id="ROX-1",
        job=sample_job,
    )

    jira.comment.assert_called_once()
    report_instance.logger.warning.assert_any_call(
        "Could not add %s to %s: %s",
        "fallback retrigger comment",
        "ROX-1",
        "bad",
    )


def test_add_passing_job_comment_logs_warning_on_jira_error(report_instance, sample_job):
    jira = MagicMock()
    jira.comment.side_effect = JIRAError("Comment body is not valid!", 400, "https://jira/x")

    report_instance.add_passing_job_comment(
        job=sample_job,
        jira=jira,
        issue_id="ROX-1",
    )

    jira.comment.assert_called_once()
    report_instance.logger.warning.assert_called_once_with(
        "Could not add %s to %s: %s",
        "passing-job comment",
        "ROX-1",
        "Comment body is not valid!",
    )


def test_add_passing_job_label_logs_warning_when_labels_not_applied(report_instance):
    jira = MagicMock()
    jira.add_labels_to_issue.return_value = (MagicMock(), False)

    report_instance.add_passing_job_label(jira=jira, issue_id="ROX-1")

    jira.add_labels_to_issue.assert_called_once()
    report_instance.logger.warning.assert_called()


def test_add_passing_job_label_logs_warning_on_jira_error(report_instance):
    jira = MagicMock()
    jira.add_labels_to_issue.side_effect = JIRAError("no", 403, "https://jira/x")

    report_instance.add_passing_job_label(jira=jira, issue_id="ROX-1")

    report_instance.logger.warning.assert_called()
