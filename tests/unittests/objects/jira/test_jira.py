import json

import pytest
from jira import Issue
from jira.exceptions import JIRAError
from unittest.mock import MagicMock, patch

from src.objects.jira_base import Jira
from tests.unittests.conftest import DEFAULT_JIRA_SERVER_URL


@pytest.fixture
def jira(patch_jira_api_requests, jira, caplog):
    jira.logger.handlers[0] = caplog.handler
    jira._caps = patch_jira_api_requests
    yield jira


@pytest.fixture
def fake_issue(fake_issue_id, jira) -> Issue:
    yield jira.get_issue_by_id_or_key(issue=fake_issue_id)


@pytest.fixture
def fake_attachment_path(tmp_path):
    path = tmp_path.joinpath("build_log.json")
    path.write_text("anything")
    yield path


class TestJiraApiRespondsWithSuccess:
    def test_get_issue_by_id_returns_jira_issue_from_jira_api_client_with_matching_issue_id(self, fake_issue_id, jira):
        issue = jira.get_issue_by_id_or_key(issue=fake_issue_id)
        assert isinstance(issue, Issue)
        assert issue.id == fake_issue_id

    def test_add_labels_to_issue_sends_content_type_json_for_cloud_compatibility(
        self, fake_issue_id, jira, patch_jira_api_requests
    ):
        """Adding labels uses PUT with Content-Type: application/json to avoid 415 from Jira Cloud."""
        labels = ["retrigger", "firewatch"]
        expected = {"update": {"labels": [{"add": "retrigger"}, {"add": "firewatch"}]}}
        issue, applied = jira.add_labels_to_issue(issue_id_or_key=fake_issue_id, labels=labels)
        assert issue is not None
        assert applied is True
        assert len(patch_jira_api_requests["put"]) == 1
        _url, (data, args, kwargs) = next(iter(patch_jira_api_requests["put"].items()))
        assert kwargs.get("headers", {}).get("Content-Type") == "application/json"
        assert kwargs.get("json") == expected
        assert data is None
        payload = kwargs["json"]
        assert "fields" not in payload
        assert payload == expected

    def test_remove_labels_from_issue_sends_content_type_json_for_cloud_compatibility(
        self, fake_issue_id, jira, patch_jira_api_requests
    ):
        labels = ["job_passed_since_ticket_created"]
        expected = {"update": {"labels": [{"remove": "job_passed_since_ticket_created"}]}}
        issue, applied = jira.remove_labels_from_issue(issue_id_or_key=fake_issue_id, labels=labels)
        assert issue is not None
        assert applied is True
        assert len(patch_jira_api_requests["put"]) == 1
        _url, (data, args, kwargs) = next(iter(patch_jira_api_requests["put"].items()))
        assert kwargs.get("headers", {}).get("Content-Type") == "application/json"
        assert kwargs.get("json") == expected
        assert data is None


class TestJiraAddLabelsHttp400:
    def test_add_labels_to_issue_returns_false_when_put_returns_http_400(self, fake_issue_id, jira, caplog):
        err_text = "Field 'labels' cannot be set. It is not on the appropriate screen, or unknown."
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.text = err_text
        mock_response.url = "https://example/rest/api/3/issue/1"

        with patch.object(jira.connection._session, "put", return_value=mock_response):
            issue, applied = jira.add_labels_to_issue(issue_id_or_key=fake_issue_id, labels=["x"])
        assert applied is False
        assert issue.id == fake_issue_id
        assert "Failed to add labels" in caplog.text


class TestJiraAddLabelsHttp403:
    def test_add_labels_to_issue_returns_false_when_put_returns_http_403(self, fake_issue_id, jira, caplog):
        err_text = "You do not have permission to edit this issue."
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 403
        mock_response.text = err_text
        mock_response.url = "https://example/rest/api/3/issue/1"

        with patch.object(jira.connection._session, "put", return_value=mock_response):
            issue, applied = jira.add_labels_to_issue(issue_id_or_key=fake_issue_id, labels=["x"])
        assert applied is False
        assert issue.id == fake_issue_id
        assert "Failed to add labels" in caplog.text
        assert "project configuration, missing permissions, or the Jira user" in caplog.text


class TestJiraApiRespondsWithPermissionFailure:
    @pytest.fixture
    def fake_issue_add_attachment_response(self, mock_jira_api_response):
        yield mock_jira_api_response(
            _content=b'{"errorMessages": ["You do not have permission to create attachments for this issue."], "errors": {}}',
            _status_code=403,
        )

    def test_add_file_attachment_with_permission_failure_logs_failure_without_raising_exception(
        self, fake_issue, jira, fake_attachment_path, caplog
    ):
        jira.add_attachment_to_issue(
            issue=fake_issue,
            attachment_path=fake_attachment_path.as_posix(),
        )
        assert "You do not have permission to create attachments for this issue" in caplog.text


def _minimal_adf_doc(plain_text: str) -> dict:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": plain_text}],
            }
        ],
    }


class TestCreateIssueDirectPost:
    @pytest.fixture
    def mock_jira(self, monkeypatch):
        monkeypatch.setattr(Jira, "__init__", lambda self, jira_config_path=None: None)
        jira = Jira()
        jira.url = DEFAULT_JIRA_SERVER_URL
        jira.connection = MagicMock()
        jira.connection._options = {}
        jira.connection._get_url.return_value = "https://example/rest/api/3/issue"
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "id": "10001",
            "key": "TEST-1",
            "self": "https://example/rest/api/3/issue/10001",
        }
        jira.connection._session.post = MagicMock(return_value=mock_response)
        return jira

    def test_create_issue_posts_json_fields_with_content_type_header(self, mock_jira):
        result = mock_jira.create_issue(
            project="TEST",
            summary="test",
            description="desc",
            issue_type="Bug",
        )
        mock_jira.connection._get_url.assert_called_once_with("issue")
        mock_jira.connection._session.post.assert_called_once()
        call_args = mock_jira.connection._session.post.call_args
        assert call_args[0][0] == "https://example/rest/api/3/issue"
        kwargs = call_args[1]
        assert kwargs["headers"] == {"Content-Type": "application/json"}
        assert "fields" in kwargs["json"]
        fields = kwargs["json"]["fields"]
        assert fields["project"] == {"key": "TEST"}
        assert fields["summary"] == "test"
        assert fields["issuetype"] == {"name": "Bug"}
        assert fields["description"] == _minimal_adf_doc("desc")
        assert isinstance(result, Issue)
        assert result.key == "TEST-1"


class TestCreateIssueHttpError:
    @pytest.fixture
    def mock_jira(self, monkeypatch):
        monkeypatch.setattr(Jira, "__init__", lambda self, jira_config_path=None: None)
        jira = Jira()
        jira.url = DEFAULT_JIRA_SERVER_URL
        jira.connection = MagicMock()
        jira.connection._options = {}
        jira.connection._get_url.return_value = "https://example/rest/api/3/issue"
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 405
        mock_response.text = '{"detail":"Method \'GET\' is not supported."}'
        mock_response.url = "https://example/rest/api/3/issue"
        jira.connection._session.post = MagicMock(return_value=mock_response)
        return jira

    def test_create_issue_raises_jira_error_when_post_returns_non_ok(self, mock_jira):
        with pytest.raises(JIRAError) as exc_info:
            mock_jira.create_issue(
                project="TEST",
                summary="test",
                description="desc",
                issue_type="Bug",
            )
        assert exc_info.value.status_code == 405
        assert "GET" in (exc_info.value.text or "")


class TestCreateIssueAdfDescription:
    @pytest.fixture
    def mock_jira(self, monkeypatch):
        monkeypatch.setattr(Jira, "__init__", lambda self, jira_config_path=None: None)
        jira = Jira()
        jira.url = DEFAULT_JIRA_SERVER_URL
        jira.connection = MagicMock()
        jira.connection._options = {}
        jira.connection._get_url.return_value = "https://example/rest/api/3/issue"
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "id": "10001",
            "key": "TEST-1",
            "self": "https://example/rest/api/3/issue/10001",
        }
        jira.connection._session.post = MagicMock(return_value=mock_response)
        return jira

    def test_create_issue_passes_adf_description_for_jira_cloud_rest_v3(self, mock_jira):
        plain = "Line one\nLine two"
        mock_jira.create_issue(
            project="TEST",
            summary="Summary",
            description=plain,
            issue_type="Bug",
        )
        mock_jira.connection._session.post.assert_called_once()
        fields = mock_jira.connection._session.post.call_args[1]["json"]["fields"]
        assert fields["description"] == _minimal_adf_doc(plain)

    def test_create_issue_sanitizes_empty_description_text_node(self, mock_jira):
        mock_jira.create_issue(
            project="TEST",
            summary="Summary",
            description="",
            issue_type="Bug",
        )
        fields = mock_jira.connection._session.post.call_args[1]["json"]["fields"]
        assert fields["description"]["content"][0]["content"][0]["text"] == " "


class TestCreateIssueEpicSearch:
    @pytest.fixture
    def mock_jira(self, monkeypatch):
        monkeypatch.setattr(Jira, "__init__", lambda self, jira_config_path=None: None)
        jira = Jira()
        jira.url = DEFAULT_JIRA_SERVER_URL
        jira.connection = MagicMock()
        jira.connection._options = {}
        jira.connection._get_url.return_value = "https://example/rest/api/3/issue"
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "id": "10001",
            "key": "TEST-1",
            "self": "https://example/rest/api/3/issue/10001",
        }
        jira.connection._session.post = MagicMock(return_value=mock_response)
        return jira

    def test_epic_lookup_uses_unquoted_issue_key_for_cloud_compatibility(self, mock_jira):
        epic_issue = MagicMock()
        epic_issue.id = "20001"
        mock_jira.connection.search_issues.return_value = [epic_issue]

        mock_jira.create_issue(
            project="TEST",
            summary="Test issue",
            description="Description",
            issue_type="Bug",
            epic="INTEROP-1234",
        )

        mock_jira.connection.search_issues.assert_called_once_with(
            "issue=INTEROP-1234",
            maxResults=False,
        )
        mock_jira.connection.add_issues_to_epic.assert_called_once_with(
            epic_id="20001",
            issue_keys="TEST-1",
        )


class TestJiraInitAuth:
    @pytest.fixture
    def cloud_config(self, tmp_path):
        path = tmp_path / "cloud.json"
        path.write_text(
            json.dumps({
                "url": DEFAULT_JIRA_SERVER_URL,
                "token": "fake-token",
                "email": "user@redhat.com",
            })
        )
        return path

    @pytest.fixture
    def server_config(self, tmp_path):
        path = tmp_path / "server.json"
        path.write_text(
            json.dumps({
                "url": DEFAULT_JIRA_SERVER_URL,
                "token": "fake-token",
            })
        )
        return path

    @patch("src.objects.jira_base.JIRA")
    def test_uses_basic_auth_when_email_configured(self, mock_jira_class, cloud_config):
        Jira(jira_config_path=cloud_config.as_posix())

        call_kwargs = mock_jira_class.call_args.kwargs
        assert call_kwargs["basic_auth"] == ("user@redhat.com", "fake-token")
        assert "token_auth" not in call_kwargs

    @patch("src.objects.jira_base.JIRA")
    def test_uses_token_auth_when_email_not_configured(self, mock_jira_class, server_config):
        Jira(jira_config_path=server_config.as_posix())

        call_kwargs = mock_jira_class.call_args.kwargs
        assert call_kwargs["token_auth"] == "fake-token"
        assert "basic_auth" not in call_kwargs

    @patch("src.objects.jira_base.JIRA")
    def test_sets_rest_api_version_3(self, mock_jira_class, cloud_config):
        Jira(jira_config_path=cloud_config.as_posix())

        call_kwargs = mock_jira_class.call_args.kwargs
        assert call_kwargs["options"] == {"rest_api_version": "3"}


def _post_request_json(kwargs: dict) -> dict:
    raw = kwargs.get("data")
    if raw is None:
        return kwargs.get("json") or {}
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode()
    return json.loads(raw) if isinstance(raw, str) else raw


def _assert_adf_doc(value: object) -> None:
    assert isinstance(value, dict), f"expected ADF doc dict, got {type(value).__name__}"
    assert value.get("type") == "doc"
    assert value.get("version") == 1


class TestJiraCommentPostAdfPayload:
    def test_comment_post_json_uses_adf_doc_body_not_string(self, patch_jira_api_requests, fake_issue_key, jira):
        text = "hello from test"
        jira.comment(fake_issue_key, text)
        comment_urls = [u for u in patch_jira_api_requests["post"] if u.endswith("/comment")]
        assert len(comment_urls) == 1
        _args, kwargs = patch_jira_api_requests["post"][comment_urls[0]]
        payload = _post_request_json(kwargs)
        assert "body" in payload
        assert not isinstance(payload["body"], str), (
            "Jira Cloud REST v3 expects comment body as ADF, not a plain string"
        )
        _assert_adf_doc(payload["body"])
        assert payload["body"]["content"][0]["content"][0]["text"] == text

    def test_comment_post_sanitizes_empty_text_in_adf_dict(self, patch_jira_api_requests, fake_issue_key, jira):
        raw = {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": ""}]},
            ],
        }
        jira.comment(fake_issue_key, raw)
        comment_urls = [u for u in patch_jira_api_requests["post"] if u.endswith("/comment")]
        assert len(comment_urls) == 1
        _args, kwargs = patch_jira_api_requests["post"][comment_urls[0]]
        payload = _post_request_json(kwargs)
        assert payload["body"]["content"][0]["content"][0]["text"] == " "
