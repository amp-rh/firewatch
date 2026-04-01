from unittest.mock import MagicMock


from src.objects.job import Job
from src.report.report import Report


def test_report_passes_job_to_add_retrigger_job_label_when_retriggered(monkeypatch, tmp_path):
    job = MagicMock(spec=Job)
    job.is_rehearsal = False
    job.is_retriggered = True
    job.failures = []
    job.name = "periodic-ci-example"
    job.build_id = "991"
    job.download_path = tmp_path / "dl"
    job.has_test_failures = False
    job.has_pod_failures = False

    jira_client = MagicMock()
    config = MagicMock()
    config.jira = jira_client
    config.keep_job_dir = True
    config.fail_with_test_failures = False
    config.fail_with_pod_failures = False
    config.success_rules = []
    config.verbose_test_failure_reporting = False

    get_open_calls = []

    def _get_open_bugs(self, job_name, jira):
        get_open_calls.append(job_name)
        if len(get_open_calls) == 1:
            return ["ISSUE-1"]
        return []

    monkeypatch.setattr(Report, "_get_open_bugs", _get_open_bugs)

    captured = []

    def _capture_retrigger(self, jira, issue_id, job):
        captured.append((jira, issue_id, job))

    monkeypatch.setattr(Report, "add_retrigger_job_label", _capture_retrigger)

    Report(firewatch_config=config, job=job)

    assert captured == [(jira_client, "ISSUE-1", job)]
    assert captured[0][2] is job
